"""Vex AST node definitions."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional


# ---- Types ----

@dataclass
class TypeNode: pass

@dataclass
class PrimType(TypeNode):
    name: str

@dataclass
class PtrType(TypeNode):
    inner: TypeNode
    mutable: bool = False

@dataclass
class SliceType(TypeNode):
    inner: TypeNode

@dataclass
class ArrayType(TypeNode):
    inner: TypeNode
    size: int

@dataclass
class NamedType(TypeNode):
    name: str

@dataclass
class FnType(TypeNode):
    params: list
    ret: TypeNode


# ---- Expressions ----
# line is always last (with default) to avoid MRO default-arg conflicts.

@dataclass
class IntLit:
    value: int
    line: int = 0

@dataclass
class FloatLit:
    value: float
    line: int = 0

@dataclass
class StrLit:
    value: str
    line: int = 0

@dataclass
class BoolLit:
    value: bool
    line: int = 0

@dataclass
class NilLit:
    line: int = 0

@dataclass
class Ident:
    name: str
    line: int = 0

@dataclass
class BinOp:
    op: str
    left: object
    right: object
    line: int = 0

@dataclass
class UnOp:
    op: str
    operand: object
    line: int = 0

@dataclass
class Call:
    callee: object
    args: list
    line: int = 0

@dataclass
class Index:
    obj: object
    idx: object
    line: int = 0

@dataclass
class Field:
    obj: object
    name: str
    line: int = 0

@dataclass
class Cast:
    expr: object
    typ: TypeNode
    line: int = 0

@dataclass
class Alloc:
    typ: TypeNode
    count: object = None  # None = single value
    line: int = 0

@dataclass
class AddrOf:
    expr: object
    line: int = 0

@dataclass
class Deref:
    expr: object
    line: int = 0

@dataclass
class StructLit:
    name: str
    fields: list  # list of (str, expr)
    line: int = 0

@dataclass
class ArrayLit:
    elements: list
    line: int = 0

Expr = (IntLit | FloatLit | StrLit | BoolLit | NilLit | Ident | BinOp | UnOp |
        Call | Index | Field | Cast | Alloc | AddrOf | Deref | StructLit | ArrayLit)


# ---- Statements ----

@dataclass
class Block:
    stmts: list
    line: int = 0

@dataclass
class Let:
    name: str
    typ: object   # TypeNode | None
    value: object
    mutable: bool = False
    line: int = 0

@dataclass
class Assign:
    target: object
    op: str
    value: object
    line: int = 0

@dataclass
class Return:
    value: object  # Expr | None
    line: int = 0

@dataclass
class If:
    cond: object
    then: Block
    els: object    # Block | If | None
    line: int = 0

@dataclass
class While:
    cond: object
    body: Block
    line: int = 0

@dataclass
class For:
    var: str
    iter: object
    body: Block
    line: int = 0

@dataclass
class FreeStmt:
    expr: object
    line: int = 0

@dataclass
class Break:
    line: int = 0

@dataclass
class Continue:
    line: int = 0

@dataclass
class ExprStmt:
    expr: object
    line: int = 0


# ---- Top-level declarations ----

@dataclass
class Param:
    name: str
    typ: TypeNode
    mutable: bool = False

@dataclass
class FnDecl:
    name: str
    params: list   # list[Param]
    ret: TypeNode
    body: object   # Block | None
    inline: bool = False
    extern: bool = False
    line: int = 0

@dataclass
class StructDecl:
    name: str
    fields: list   # list[(str, TypeNode)]
    line: int = 0

@dataclass
class ImportDecl:
    path: str
    line: int = 0

@dataclass
class Module:
    imports: list
    structs: list
    fns: list
    filename: str = '<input>'
