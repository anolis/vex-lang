"""Vex -> C code generator."""
from __future__ import annotations
from .ast import *
from .typeck import TypeChecker, RType, TInt, TFloat, TBool, TStr, TVoid, TPtr, TSlice, TArray, TStruct, TFn, TNil


C_TYPES = {
    'i8':'int8_t','i16':'int16_t','i32':'int32_t','i64':'int64_t',
    'u8':'uint8_t','u16':'uint16_t','u32':'uint32_t','u64':'uint64_t',
    'f32':'float','f64':'double','bool':'int','str':'const char*','void':'void',
}


def rtype_to_c(t: RType) -> str:
    if isinstance(t, TInt):
        return ('int' if t.signed else 'uint') + f'{t.bits}_t'
    if isinstance(t, TFloat):
        return 'float' if t.bits == 32 else 'double'
    if isinstance(t, TBool):   return 'int'
    if isinstance(t, TStr):    return 'const char*'
    if isinstance(t, TVoid):   return 'void'
    if isinstance(t, TNil):    return 'void*'
    if isinstance(t, TPtr):
        # ptr<T> = const T*, ptr<mut T> = T*
        qual = '' if t.mutable else 'const '
        return f'{qual}{rtype_to_c(t.inner)}*'
    if isinstance(t, TSlice):
        return f'{rtype_to_c(t.inner)}*'
    if isinstance(t, TArray):
        return f'{rtype_to_c(t.inner)}*'
    if isinstance(t, TStruct): return t.name
    if isinstance(t, TFn):
        ret = rtype_to_c(t.ret)
        ps  = ', '.join(rtype_to_c(p) for p in t.params)
        return f'{ret} (*)({ps})'
    return 'void*'


def type_to_c(node: TypeNode, structs: dict) -> str:
    from .typeck import resolve_type
    return rtype_to_c(resolve_type(node, structs))


class CodeGen:
    def __init__(self, module: Module, tc: TypeChecker):
        self.module = module
        self.tc = tc
        self.out: list[str] = []
        self.indent = 0

    def emit(self, line: str = ''):
        self.out.append('    ' * self.indent + line)

    def generate(self) -> str:
        self._preamble()
        for imp in self.module.imports:
            self.emit(f'#include "{imp.path}"')
        self.emit()
        # forward-declare all structs so self-referential fields work
        for s in self.module.structs:
            self.emit(f'typedef struct {s.name} {s.name};')
        if self.module.structs:
            self.emit()
        for s in self.module.structs:
            self._gen_struct(s)
        # forward-declare all functions
        for fn in self.module.fns:
            self.emit(self._fn_sig(fn) + ';')
        self.emit()
        for fn in self.module.fns:
            if fn.body is not None:
                self._gen_fn(fn)
        # emit C main if module defines main
        if any(fn.name == 'main' for fn in self.module.fns):
            self.emit('int main(int argc, char **argv) { return (int)vex_main(); }')
        return '\n'.join(self.out)

    def _preamble(self):
        self.emit('#include <stdint.h>')
        self.emit('#include <stddef.h>')
        self.emit('#include <stdlib.h>')
        self.emit('#include <string.h>')
        self.emit('#include <stdio.h>')
        self.emit()

    def _gen_struct(self, s: StructDecl):
        self.emit(f'typedef struct {s.name} {{')
        self.indent += 1
        for fname, ftyp in s.fields:
            ct = type_to_c(ftyp, self.tc.structs)
            # arrays need special notation
            from .ast import ArrayType
            if isinstance(ftyp, ArrayType):
                inner_ct = type_to_c(ftyp.inner, self.tc.structs)
                self.emit(f'{inner_ct} {fname}[{ftyp.size}];')
            else:
                self.emit(f'{ct} {fname};')
        self.indent -= 1
        self.emit(f'}} {s.name};')
        self.emit()

    def _fn_sig(self, fn: FnDecl) -> str:
        attrs = []
        if fn.inline: attrs.append('static inline')
        if fn.extern: attrs.append('extern')
        prefix = ' '.join(attrs) + ' ' if attrs else ''
        ret = type_to_c(fn.ret, self.tc.structs)
        params = ', '.join(
            f"{type_to_c(p.typ, self.tc.structs)} {p.name}"
            for p in fn.params
        ) or 'void'
        return f'{prefix}{ret} vex_{fn.name}({params})'

    def _gen_fn(self, fn: FnDecl):
        self.emit(self._fn_sig(fn) + ' {')
        self.indent += 1
        self._gen_block(fn.body)
        self.indent -= 1
        self.emit('}')
        self.emit()

    def _gen_block(self, block: Block):
        for stmt in block.stmts:
            self._gen_stmt(stmt)

    def _gen_stmt(self, stmt: Stmt):
        if isinstance(stmt, Let):
            t = self.tc.types.get(id(stmt.value))
            if t:
                ct = rtype_to_c(t)
            else:
                ct = 'auto'  # fallback
            val = self._gen_expr(stmt.value)
            self.emit(f'{ct} {stmt.name} = {val};')

        elif isinstance(stmt, Assign):
            target = self._gen_expr(stmt.target)
            val    = self._gen_expr(stmt.value)
            self.emit(f'{target} {stmt.op} {val};')

        elif isinstance(stmt, Return):
            if stmt.value is None:
                self.emit('return;')
            else:
                self.emit(f'return {self._gen_expr(stmt.value)};')

        elif isinstance(stmt, If):
            self.emit(f'if ({self._gen_expr(stmt.cond)}) {{')
            self.indent += 1
            self._gen_block(stmt.then)
            self.indent -= 1
            if stmt.els is None:
                self.emit('}')
            elif isinstance(stmt.els, Block):
                self.emit('} else {')
                self.indent += 1
                self._gen_block(stmt.els)
                self.indent -= 1
                self.emit('}')
            else:
                self.emit('} else ')
                self._gen_stmt(stmt.els)

        elif isinstance(stmt, While):
            self.emit(f'while ({self._gen_expr(stmt.cond)}) {{')
            self.indent += 1
            self._gen_block(stmt.body)
            self.indent -= 1
            self.emit('}')

        elif isinstance(stmt, For):
            # Only supports range-over array/slice (emit as C for-loop with index)
            iter_c = self._gen_expr(stmt.iter)
            # We need the length — for now emit with sizeof trick or __len
            # Use a temp var for the iterator pointer
            self.emit(f'for (size_t _i = 0; _i < sizeof({iter_c})/sizeof({iter_c}[0]); _i++) {{')
            self.indent += 1
            t = self.tc.types.get(id(stmt.iter))
            if t:
                from .typeck import TArray, TSlice
                if isinstance(t, TArray):
                    inner_ct = rtype_to_c(t.inner)
                else:
                    inner_ct = 'void*'
            else:
                inner_ct = 'void*'
            self.emit(f'{inner_ct} {stmt.var} = {iter_c}[_i];')
            self._gen_block(stmt.body)
            self.indent -= 1
            self.emit('}')

        elif isinstance(stmt, FreeStmt):
            self.emit(f'free({self._gen_expr(stmt.expr)});')

        elif isinstance(stmt, ExprStmt):
            self.emit(f'{self._gen_expr(stmt.expr)};')

        elif isinstance(stmt, Block):
            self.emit('{')
            self.indent += 1
            self._gen_block(stmt)
            self.indent -= 1
            self.emit('}')

    def _gen_expr(self, expr: Expr) -> str:
        if isinstance(expr, IntLit):   return str(expr.value)
        if isinstance(expr, FloatLit): return repr(expr.value)
        if isinstance(expr, BoolLit):  return '1' if expr.value else '0'
        if isinstance(expr, NilLit):   return 'NULL'
        if isinstance(expr, StrLit):
            escaped = expr.value.replace('\\','\\\\').replace('"','\\"').replace('\n','\\n').replace('\t','\\t')
            return f'"{escaped}"'

        if isinstance(expr, Ident):
            builtins = {'print': 'printf', 'println': 'printf'}
            if expr.name in builtins:
                return builtins[expr.name]
            # only global function names get the vex_ prefix
            if expr.name in self.tc.fns:
                return f'vex_{expr.name}'
            return expr.name

        if isinstance(expr, Cast):
            t = type_to_c(expr.typ, self.tc.structs)
            return f'(({t}){self._gen_expr(expr.expr)})'

        if isinstance(expr, Alloc):
            inner_t = type_to_c(expr.typ, self.tc.structs)
            if expr.count is not None:
                cnt = self._gen_expr(expr.count)
                return f'(({inner_t}*)malloc(sizeof({inner_t}) * ({cnt})))'
            return f'(({inner_t}*)malloc(sizeof({inner_t})))'

        if isinstance(expr, AddrOf):
            return f'(&{self._gen_expr(expr.expr)})'

        if isinstance(expr, Deref):
            return f'(*{self._gen_expr(expr.expr)})'

        if isinstance(expr, Field):
            obj = self._gen_expr(expr.obj)
            t = self.tc.types.get(id(expr.obj))
            if isinstance(t, TPtr):
                return f'{obj}->{expr.name}'
            return f'{obj}.{expr.name}'

        if isinstance(expr, Index):
            return f'{self._gen_expr(expr.obj)}[{self._gen_expr(expr.idx)}]'

        if isinstance(expr, Call):
            callee = self._gen_expr(expr.callee)
            args = ', '.join(self._gen_expr(a) for a in expr.args)
            return f'{callee}({args})'

        if isinstance(expr, BinOp):
            l = self._gen_expr(expr.left)
            r = self._gen_expr(expr.right)
            return f'({l} {expr.op} {r})'

        if isinstance(expr, UnOp):
            return f'({expr.op}{self._gen_expr(expr.operand)})'

        if isinstance(expr, StructLit):
            fields = ', '.join(
                f'.{name} = {self._gen_expr(val)}'
                for name, val in expr.fields
            )
            return f'({expr.name}){{{fields}}}'

        if isinstance(expr, ArrayLit):
            elems = ', '.join(self._gen_expr(e) for e in expr.elements)
            return f'{{{elems}}}'

        raise NotImplementedError(f"codegen: {type(expr).__name__}")


def generate(module: Module, tc: TypeChecker) -> str:
    return CodeGen(module, tc).generate()
