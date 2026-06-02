"""Vex parser: tokens -> AST."""
from __future__ import annotations
from .lexer import Token, TK, tokenize
from .ast import *


class ParseError(Exception):
    pass


class Parser:
    def __init__(self, tokens: list[Token], filename: str = '<input>'):
        self.tokens = tokens
        self.pos = 0
        self.filename = filename

    def peek(self) -> Token:
        return self.tokens[self.pos]

    def advance(self) -> Token:
        t = self.tokens[self.pos]
        if t.kind != TK.EOF:
            self.pos += 1
        return t

    def check(self, *kinds: TK) -> bool:
        return self.peek().kind in kinds

    def match(self, *kinds: TK) -> Token | None:
        if self.check(*kinds):
            return self.advance()
        return None

    def expect(self, kind: TK) -> Token:
        t = self.peek()
        if t.kind != kind:
            raise ParseError(
                f"{self.filename}:{t.line}:{t.col}: "
                f"expected {kind.name}, got {t.kind.name} ({t.value!r})"
            )
        return self.advance()

    def error(self, msg: str) -> ParseError:
        t = self.peek()
        return ParseError(f"{self.filename}:{t.line}:{t.col}: {msg}")

    # ---- Type parsing ----

    def parse_type(self) -> TypeNode:
        t = self.peek()
        prim_map = {
            TK.I8:'i8', TK.I16:'i16', TK.I32:'i32', TK.I64:'i64',
            TK.U8:'u8', TK.U16:'u16', TK.U32:'u32', TK.U64:'u64',
            TK.F32:'f32', TK.F64:'f64', TK.BOOL_T:'bool',
            TK.STR_T:'str', TK.VOID:'void',
        }
        if t.kind in prim_map:
            self.advance()
            return PrimType(prim_map[t.kind])

        if t.kind == TK.PTR:
            self.advance()
            self.expect(TK.LT)
            is_mut = bool(self.match(TK.MUT))
            inner = self.parse_type()
            self.expect(TK.GT)
            return PtrType(inner, is_mut)

        if t.kind == TK.SLICE:
            self.advance()
            self.expect(TK.LT)
            inner = self.parse_type()
            self.expect(TK.GT)
            return SliceType(inner)

        if t.kind == TK.LBRACKET:
            self.advance()
            inner = self.parse_type()
            self.expect(TK.SEMICOLON)
            size_tok = self.expect(TK.INT)
            self.expect(TK.RBRACKET)
            return ArrayType(inner, size_tok.value)

        if t.kind == TK.FN:
            self.advance()
            self.expect(TK.LPAREN)
            params = []
            while not self.check(TK.RPAREN, TK.EOF):
                params.append(self.parse_type())
                if not self.match(TK.COMMA): break
            self.expect(TK.RPAREN)
            self.expect(TK.ARROW)
            ret = self.parse_type()
            return FnType(params, ret)

        if t.kind == TK.IDENT:
            self.advance()
            return NamedType(t.value)

        raise self.error(f"expected type, got {t.kind.name}")

    # ---- Expression parsing (Pratt) ----

    UNARY_OPS = {TK.MINUS: '-', TK.NOT: '!', TK.TILDE: '~', TK.STAR: '*', TK.AMP: '&'}

    BINOP_PREC: dict[TK, tuple[int, str]] = {
        TK.OR:     (1,  '||'),
        TK.AND:    (2,  '&&'),
        TK.PIPE:   (3,  '|'),
        TK.CARET:  (4,  '^'),
        TK.AMP:    (5,  '&'),
        TK.EQ:     (6,  '=='),
        TK.NEQ:    (6,  '!='),
        TK.LT:     (7,  '<'),
        TK.GT:     (7,  '>'),
        TK.LE:     (7,  '<='),
        TK.GE:     (7,  '>='),
        TK.LSHIFT: (8,  '<<'),
        TK.RSHIFT: (8,  '>>'),
        TK.PLUS:   (9,  '+'),
        TK.MINUS:  (9,  '-'),
        TK.STAR:   (10, '*'),
        TK.SLASH:  (10, '/'),
        TK.PERCENT:(10, '%'),
    }

    def parse_expr(self, min_prec: int = 0) -> Expr:
        left = self.parse_unary()
        while True:
            t = self.peek()
            entry = self.BINOP_PREC.get(t.kind)
            if entry is None or entry[0] <= min_prec:
                break
            prec, op = entry
            self.advance()
            right = self.parse_expr(prec)
            left = BinOp(op, left, right, line=t.line)
        return left

    def parse_unary(self) -> Expr:
        t = self.peek()
        # alloc is handled here (not in postfix) so the `()` arg isn't confused
        # with a function call from the next line
        if t.kind == TK.ALLOC:
            self.advance()
            self.expect(TK.LT)
            typ = self.parse_type()
            self.expect(TK.GT)
            self.expect(TK.LPAREN)
            count = None
            if not self.check(TK.RPAREN):
                count = self.parse_expr()
            self.expect(TK.RPAREN)
            return Alloc(typ, count, line=t.line)
        if t.kind in self.UNARY_OPS:
            self.advance()
            op = self.UNARY_OPS[t.kind]
            if op == '&':
                operand = self.parse_postfix()
                return AddrOf(operand, line=t.line)
            if op == '*':
                operand = self.parse_unary()
                return Deref(operand, line=t.line)
            operand = self.parse_unary()
            return UnOp(op, operand, line=t.line)
        return self.parse_postfix()

    def parse_postfix(self) -> Expr:
        expr = self.parse_primary()
        while True:
            t = self.peek()
            # `(` and `[` on a different line than the expression stop parsing —
            # prevents `f\n(x)` being read as `f(x)` across newlines.
            prev_line = self.tokens[self.pos - 1].line
            if t.kind == TK.LPAREN:
                if t.line != prev_line:
                    break
                self.advance()
                args = []
                while not self.check(TK.RPAREN, TK.EOF):
                    args.append(self.parse_expr())
                    if not self.match(TK.COMMA): break
                self.expect(TK.RPAREN)
                expr = Call(expr, args, line=t.line)
            elif t.kind == TK.LBRACKET:
                if t.line != prev_line:
                    break
                self.advance()
                idx = self.parse_expr()
                self.expect(TK.RBRACKET)
                expr = Index(expr, idx, line=t.line)
            elif t.kind == TK.DOT:
                self.advance()
                name = self.expect(TK.IDENT).value
                expr = Field(expr, name, line=t.line)
            elif t.kind == TK.AS:
                self.advance()
                typ = self.parse_type()
                expr = Cast(expr, typ, line=t.line)
            else:
                break
        return expr

    def parse_primary(self) -> Expr:
        t = self.advance()
        if t.kind == TK.INT:   return IntLit(t.value, line=t.line)
        if t.kind == TK.FLOAT: return FloatLit(t.value, line=t.line)
        if t.kind == TK.STR:   return StrLit(t.value, line=t.line)
        if t.kind == TK.BOOL:  return BoolLit(t.value, line=t.line)
        if t.kind == TK.NIL:   return NilLit(line=t.line)

        if t.kind == TK.IDENT:
            # struct literal: Name { field: expr, ... }
            if self.check(TK.LBRACE):
                self.advance()
                fields = []
                while not self.check(TK.RBRACE, TK.EOF):
                    fname = self.expect(TK.IDENT).value
                    self.expect(TK.COLON)
                    fval = self.parse_expr()
                    fields.append((fname, fval))
                    if not self.match(TK.COMMA): break
                self.expect(TK.RBRACE)
                return StructLit(t.value, fields, line=t.line)
            return Ident(t.value, line=t.line)

        if t.kind == TK.LPAREN:
            expr = self.parse_expr()
            self.expect(TK.RPAREN)
            expr.line = t.line
            return expr

        if t.kind == TK.LBRACKET:
            elements = []
            while not self.check(TK.RBRACKET, TK.EOF):
                elements.append(self.parse_expr())
                if not self.match(TK.COMMA): break
            self.expect(TK.RBRACKET)
            return ArrayLit(elements, line=t.line)

        raise ParseError(
            f"{self.filename}:{t.line}:{t.col}: unexpected token {t.kind.name} ({t.value!r})"
        )

    # ---- Statement parsing ----

    def parse_block(self) -> Block:
        t = self.expect(TK.LBRACE)
        stmts = []
        while not self.check(TK.RBRACE, TK.EOF):
            stmts.append(self.parse_stmt())
        self.expect(TK.RBRACE)
        return Block(stmts, line=t.line)

    def parse_stmt(self) -> Stmt:
        t = self.peek()

        if t.kind == TK.LET:
            return self.parse_let()

        if t.kind == TK.RETURN:
            self.advance()
            val = None
            if not self.check(TK.SEMICOLON, TK.RBRACE):
                val = self.parse_expr()
            self.match(TK.SEMICOLON)
            return Return(val, line=t.line)

        if t.kind == TK.IF:
            return self.parse_if()

        if t.kind == TK.WHILE:
            self.advance()
            cond = self.parse_expr()
            body = self.parse_block()
            return While(cond, body, line=t.line)

        if t.kind == TK.FOR:
            self.advance()
            var = self.expect(TK.IDENT).value
            self.expect(TK.IN)
            iter_expr = self.parse_expr()
            body = self.parse_block()
            return For(var, iter_expr, body, line=t.line)

        if t.kind == TK.FREE:
            self.advance()
            expr = self.parse_expr()
            self.match(TK.SEMICOLON)
            return FreeStmt(expr, line=t.line)

        if t.kind == TK.LBRACE:
            return self.parse_block()

        # expression or assignment
        expr = self.parse_expr()
        assign_ops = {TK.ASSIGN:'=', TK.PLUS_EQ:'+=', TK.MINUS_EQ:'-=',
                      TK.STAR_EQ:'*=', TK.SLASH_EQ:'/='}
        if self.peek().kind in assign_ops:
            op = assign_ops[self.advance().kind]
            val = self.parse_expr()
            self.match(TK.SEMICOLON)
            return Assign(expr, op, val, line=t.line)

        self.match(TK.SEMICOLON)
        return ExprStmt(expr, line=t.line)

    def parse_let(self) -> Let:
        t = self.expect(TK.LET)
        mutable = bool(self.match(TK.MUT))
        name = self.expect(TK.IDENT).value
        typ = None
        if self.match(TK.COLON):
            typ = self.parse_type()
        self.expect(TK.ASSIGN)
        value = self.parse_expr()
        self.match(TK.SEMICOLON)
        return Let(name, typ, value, mutable, line=t.line)

    def parse_if(self) -> If:
        t = self.expect(TK.IF)
        cond = self.parse_expr()
        then = self.parse_block()
        els = None
        if self.match(TK.ELSE):
            if self.check(TK.IF):
                els = self.parse_if()
            else:
                els = self.parse_block()
        return If(cond, then, els, line=t.line)

    # ---- Top-level ----

    def parse_module(self) -> Module:
        imports, structs, fns = [], [], []
        while not self.check(TK.EOF):
            t = self.peek()
            if t.kind == TK.IMPORT:
                self.advance()
                path = self.expect(TK.STR).value
                self.match(TK.SEMICOLON)
                imports.append(ImportDecl(path, line=t.line))
            elif t.kind == TK.STRUCT:
                structs.append(self.parse_struct())
            elif t.kind in (TK.FN, TK.EXTERN, TK.INLINE):
                fns.append(self.parse_fn())
            else:
                raise self.error(f"expected top-level declaration, got {t.kind.name}")
        return Module(imports, structs, fns, filename=self.filename)

    def parse_struct(self) -> StructDecl:
        t = self.expect(TK.STRUCT)
        name = self.expect(TK.IDENT).value
        self.expect(TK.LBRACE)
        fields = []
        while not self.check(TK.RBRACE, TK.EOF):
            fname = self.expect(TK.IDENT).value
            self.expect(TK.COLON)
            ftyp = self.parse_type()
            self.match(TK.COMMA)
            fields.append((fname, ftyp))
        self.expect(TK.RBRACE)
        return StructDecl(name, fields, line=t.line)

    def parse_fn(self) -> FnDecl:
        is_extern = bool(self.match(TK.EXTERN))
        is_inline = bool(self.match(TK.INLINE))
        t = self.expect(TK.FN)
        name = self.expect(TK.IDENT).value
        self.expect(TK.LPAREN)
        params = []
        while not self.check(TK.RPAREN, TK.EOF):
            is_mut = bool(self.match(TK.MUT))
            pname = self.expect(TK.IDENT).value
            self.expect(TK.COLON)
            ptyp = self.parse_type()
            params.append(Param(pname, ptyp, is_mut))
            if not self.match(TK.COMMA): break
        self.expect(TK.RPAREN)
        ret = PrimType('void')
        if self.match(TK.ARROW):
            ret = self.parse_type()
        body = None
        if is_extern:
            self.match(TK.SEMICOLON)
        else:
            body = self.parse_block()
        return FnDecl(name, params, ret, body, is_inline, is_extern, line=t.line)


def parse(src: str, filename: str = '<input>') -> Module:
    tokens = tokenize(src, filename)
    return Parser(tokens, filename).parse_module()
