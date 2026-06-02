"""Vex type checker."""
from __future__ import annotations
from .ast import *
from dataclasses import dataclass


class TypeError(Exception):
    pass


# ---- Resolved types (used internally) ----

@dataclass(frozen=True)
class TInt:
    bits: int; signed: bool
    def __str__(self): return f"{'i' if self.signed else 'u'}{self.bits}"

@dataclass(frozen=True)
class TFloat:
    bits: int
    def __str__(self): return f"f{self.bits}"

@dataclass(frozen=True)
class TBool:
    def __str__(self): return 'bool'

@dataclass(frozen=True)
class TStr:
    def __str__(self): return 'str'

@dataclass(frozen=True)
class TVoid:
    def __str__(self): return 'void'

@dataclass(frozen=True)
class TPtr:
    inner: object; mutable: bool
    def __str__(self): return f"ptr<{'mut ' if self.mutable else ''}{self.inner}>"

@dataclass(frozen=True)
class TSlice:
    inner: object
    def __str__(self): return f"slice<{self.inner}>"

@dataclass(frozen=True)
class TArray:
    inner: object; size: int
    def __str__(self): return f"[{self.inner}; {self.size}]"

@dataclass(frozen=True)
class TStruct:
    name: str
    def __str__(self): return self.name

@dataclass(frozen=True)
class TFn:
    params: tuple; ret: object
    def __str__(self): return f"fn({', '.join(str(p) for p in self.params)}) -> {self.ret}"

@dataclass(frozen=True)
class TNil:
    def __str__(self): return 'nil'

RType = TInt | TFloat | TBool | TStr | TVoid | TPtr | TSlice | TArray | TStruct | TFn | TNil

I8  = TInt(8,  True);  I16 = TInt(16, True)
I32 = TInt(32, True);  I64 = TInt(64, True)
U8  = TInt(8,  False); U16 = TInt(16, False)
U32 = TInt(32, False); U64 = TInt(64, False)
F32 = TFloat(32);      F64 = TFloat(64)
BOOL= TBool();         STR = TStr()
VOID= TVoid();         NIL = TNil()

PRIM_MAP = {
    'i8':I8,'i16':I16,'i32':I32,'i64':I64,
    'u8':U8,'u16':U16,'u32':U32,'u64':U64,
    'f32':F32,'f64':F64,'bool':BOOL,'str':STR,'void':VOID,
}


def resolve_type(node: TypeNode, structs: dict[str, StructDecl]) -> RType:
    if isinstance(node, PrimType):
        return PRIM_MAP[node.name]
    if isinstance(node, PtrType):
        return TPtr(resolve_type(node.inner, structs), node.mutable)
    if isinstance(node, SliceType):
        return TSlice(resolve_type(node.inner, structs))
    if isinstance(node, ArrayType):
        return TArray(resolve_type(node.inner, structs), node.size)
    if isinstance(node, NamedType):
        if node.name not in structs:
            raise TypeError(f"unknown type '{node.name}'")
        return TStruct(node.name)
    if isinstance(node, FnType):
        ps = tuple(resolve_type(p, structs) for p in node.params)
        r  = resolve_type(node.ret, structs)
        return TFn(ps, r)
    raise TypeError(f"cannot resolve type node {node!r}")


class Scope:
    def __init__(self, parent: 'Scope | None' = None):
        self.vars: dict[str, tuple[RType, bool]] = {}  # name -> (type, mutable)
        self.parent = parent

    def get(self, name: str) -> tuple[RType, bool] | None:
        if name in self.vars: return self.vars[name]
        if self.parent: return self.parent.get(name)
        return None

    def set(self, name: str, typ: RType, mutable: bool = False):
        self.vars[name] = (typ, mutable)

    def child(self) -> 'Scope':
        return Scope(self)


class TypeChecker:
    def __init__(self, module: Module):
        self.module = module
        self.structs: dict[str, StructDecl] = {s.name: s for s in module.structs}
        self.struct_fields: dict[str, dict[str, RType]] = {}
        self.fns: dict[str, TFn] = {}
        self.current_ret: RType = VOID
        self.types: dict[int, RType] = {}  # id(expr) -> RType

    def check(self):
        # register struct field types
        for s in self.module.structs:
            self.struct_fields[s.name] = {
                fname: resolve_type(ftyp, self.structs)
                for fname, ftyp in s.fields
            }

        # built-in variadic functions — represented as TFn with empty params
        # (we skip arity check for variadics in _infer/Call)
        self.variadics = {'print', 'println', 'printf', 'fprintf', 'sprintf'}
        for name in self.variadics:
            self.fns[name] = TFn((), VOID)

        # register function signatures
        for fn in self.module.fns:
            pts = tuple(resolve_type(p.typ, self.structs) for p in fn.params)
            ret = resolve_type(fn.ret, self.structs)
            self.fns[fn.name] = TFn(pts, ret)

        # check function bodies
        for fn in self.module.fns:
            if fn.body is None: continue
            scope = Scope()
            for p in fn.params:
                scope.set(p.name, resolve_type(p.typ, self.structs), p.mutable)
            self.current_ret = resolve_type(fn.ret, self.structs)
            self.check_block(fn.body, scope)

    def record(self, expr: Expr, typ: RType) -> RType:
        self.types[id(expr)] = typ
        return typ

    def type_of(self, expr: Expr) -> RType:
        return self.types[id(expr)]

    def check_block(self, block: Block, scope: Scope):
        inner = scope.child()
        for stmt in block.stmts:
            self.check_stmt(stmt, inner)

    def check_stmt(self, stmt: Stmt, scope: Scope):
        if isinstance(stmt, Let):
            vt = self.check_expr(stmt.value, scope)
            if stmt.typ is not None:
                declared = resolve_type(stmt.typ, self.structs)
                if not self._compat(vt, declared):
                    raise TypeError(
                        f"line {stmt.line}: let '{stmt.name}': "
                        f"expected {declared}, got {vt}"
                    )
                vt = declared
            scope.set(stmt.name, vt, stmt.mutable)

        elif isinstance(stmt, Assign):
            tv = self.check_expr(stmt.value, scope)
            tt = self.check_expr(stmt.target, scope)
            if not self._compat(tv, tt):
                raise TypeError(f"line {stmt.line}: assign type mismatch {tt} = {tv}")

        elif isinstance(stmt, Return):
            if stmt.value is None:
                if self.current_ret != VOID:
                    raise TypeError(f"line {stmt.line}: return void in non-void fn")
            else:
                rt = self.check_expr(stmt.value, scope)
                if not self._compat(rt, self.current_ret):
                    raise TypeError(
                        f"line {stmt.line}: return {rt}, expected {self.current_ret}"
                    )

        elif isinstance(stmt, If):
            self.check_expr(stmt.cond, scope)
            self.check_block(stmt.then, scope)
            if stmt.els:
                if isinstance(stmt.els, Block):
                    self.check_block(stmt.els, scope)
                else:
                    self.check_stmt(stmt.els, scope)

        elif isinstance(stmt, While):
            self.check_expr(stmt.cond, scope)
            self.check_block(stmt.body, scope)

        elif isinstance(stmt, For):
            it = self.check_expr(stmt.iter, scope)
            elem_t: RType
            if isinstance(it, TSlice): elem_t = it.inner
            elif isinstance(it, TArray): elem_t = it.inner
            else:
                raise TypeError(f"line {stmt.line}: for-in requires slice/array, got {it}")
            inner = scope.child()
            inner.set(stmt.var, elem_t, False)
            self.check_block(stmt.body, inner)

        elif isinstance(stmt, FreeStmt):
            t = self.check_expr(stmt.expr, scope)
            if not isinstance(t, TPtr):
                raise TypeError(f"line {stmt.line}: free requires ptr, got {t}")

        elif isinstance(stmt, ExprStmt):
            self.check_expr(stmt.expr, scope)

        elif isinstance(stmt, Block):
            self.check_block(stmt, scope)

    def check_expr(self, expr: Expr, scope: Scope) -> RType:
        t = self._infer(expr, scope)
        return self.record(expr, t)

    def _infer(self, expr: Expr, scope: Scope) -> RType:
        if isinstance(expr, IntLit):
            v = expr.value
            if 0 <= v < 2**31:  return I32   # default small int is i32
            if -(2**63) <= v < 2**63: return I64
            if 0 <= v < 2**64:  return U64   # large positive → u64
            return I64
        if isinstance(expr, FloatLit): return F64
        if isinstance(expr, StrLit):   return STR
        if isinstance(expr, BoolLit):  return BOOL
        if isinstance(expr, NilLit):   return NIL

        if isinstance(expr, Ident):
            entry = scope.get(expr.name)
            if entry: return entry[0]
            if expr.name in self.fns: return self.fns[expr.name]
            raise TypeError(f"line {expr.line}: undefined '{expr.name}'")

        if isinstance(expr, Cast):
            self.check_expr(expr.expr, scope)
            return resolve_type(expr.typ, self.structs)

        if isinstance(expr, Alloc):
            inner = resolve_type(expr.typ, self.structs)
            if expr.count is not None:
                self.check_expr(expr.count, scope)
                return TSlice(inner)
            return TPtr(inner, True)

        if isinstance(expr, AddrOf):
            inner = self.check_expr(expr.expr, scope)
            return TPtr(inner, False)

        if isinstance(expr, Deref):
            t = self.check_expr(expr.expr, scope)
            if not isinstance(t, TPtr):
                raise TypeError(f"line {expr.line}: deref of non-ptr {t}")
            return t.inner

        if isinstance(expr, Field):
            ot = self.check_expr(expr.obj, scope)
            sname = ot.name if isinstance(ot, TStruct) else None
            if sname and sname in self.struct_fields:
                fields = self.struct_fields[sname]
                if expr.name not in fields:
                    raise TypeError(f"line {expr.line}: struct {sname} has no field '{expr.name}'")
                return fields[expr.name]
            raise TypeError(f"line {expr.line}: field access on non-struct {ot}")

        if isinstance(expr, Index):
            ot = self.check_expr(expr.obj, scope)
            self.check_expr(expr.idx, scope)
            if isinstance(ot, (TSlice, TArray)): return ot.inner
            if isinstance(ot, TPtr): return ot.inner  # pointer indexing
            raise TypeError(f"line {expr.line}: index on non-indexable {ot}")

        if isinstance(expr, Call):
            ft = self.check_expr(expr.callee, scope)
            if not isinstance(ft, TFn):
                raise TypeError(f"line {expr.line}: call of non-function {ft}")
            # variadic built-ins have empty params tuple — skip arity/type check
            is_variadic = (
                isinstance(expr.callee, Ident) and expr.callee.name in self.variadics
            )
            if not is_variadic:
                if len(expr.args) != len(ft.params):
                    raise TypeError(
                        f"line {expr.line}: {len(ft.params)} params, {len(expr.args)} given"
                    )
                for a, p in zip(expr.args, ft.params):
                    at = self.check_expr(a, scope)
                    if not self._compat(at, p):
                        raise TypeError(f"line {expr.line}: arg {at} incompatible with {p}")
            else:
                for a in expr.args:
                    self.check_expr(a, scope)
            return ft.ret

        if isinstance(expr, BinOp):
            lt = self.check_expr(expr.left, scope)
            rt = self.check_expr(expr.right, scope)
            if expr.op in ('==','!=','<','>','<=','>=','&&','||'): return BOOL
            # pointer arithmetic: ptr + int or ptr - int → ptr
            if expr.op in ('+', '-') and isinstance(lt, (TPtr, TSlice)) and isinstance(rt, TInt):
                return lt
            if not self._compat(lt, rt):
                raise TypeError(f"line {expr.line}: binop {expr.op} {lt} {rt}")
            return lt

        if isinstance(expr, UnOp):
            return self.check_expr(expr.operand, scope)

        if isinstance(expr, StructLit):
            if expr.name not in self.struct_fields:
                raise TypeError(f"line {expr.line}: unknown struct '{expr.name}'")
            fields = self.struct_fields[expr.name]
            for fname, fval in expr.fields:
                if fname not in fields:
                    raise TypeError(f"line {expr.line}: no field '{fname}' in {expr.name}")
                ft = self.check_expr(fval, scope)
                if not self._compat(ft, fields[fname]):
                    raise TypeError(f"line {expr.line}: field '{fname}' type mismatch")
            return TStruct(expr.name)

        if isinstance(expr, ArrayLit):
            if not expr.elements:
                return TArray(VOID, 0)
            et = self.check_expr(expr.elements[0], scope)
            for e in expr.elements[1:]:
                self.check_expr(e, scope)
            return TArray(et, len(expr.elements))

        raise TypeError(f"cannot type-check {type(expr).__name__}")

    def _compat(self, got: RType, expected: RType) -> bool:
        if got == expected: return True
        if isinstance(got, TNil) and isinstance(expected, (TPtr, TSlice)): return True
        if isinstance(got, TInt) and isinstance(expected, TInt): return True
        if isinstance(got, TFloat) and isinstance(expected, TFloat): return True
        if isinstance(got, TInt) and isinstance(expected, TFloat): return True
        # slice<T> and ptr<T> are both T* in C — interchangeable
        if isinstance(got, TSlice) and isinstance(expected, TPtr): return True
        if isinstance(got, TPtr)   and isinstance(expected, TSlice): return True
        # any pointer/slice is compat with void* (ptr<u8> used as generic buffer)
        if isinstance(got, (TPtr, TSlice)) and isinstance(expected, (TPtr, TSlice)): return True
        return False


def typecheck(module: Module) -> TypeChecker:
    tc = TypeChecker(module)
    tc.check()
    return tc
