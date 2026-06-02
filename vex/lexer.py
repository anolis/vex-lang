"""Vex lexer."""
from __future__ import annotations
from dataclasses import dataclass
from enum import Enum, auto
import re


class TK(Enum):
    # literals
    INT = auto(); FLOAT = auto(); STR = auto(); BOOL = auto(); NIL = auto()
    # identifiers / keywords
    IDENT = auto()
    # keywords
    FN = auto(); LET = auto(); MUT = auto(); IF = auto(); ELSE = auto()
    WHILE = auto(); FOR = auto(); IN = auto(); RETURN = auto()
    BREAK = auto(); CONTINUE = auto()
    STRUCT = auto(); ALLOC = auto(); FREE = auto(); AS = auto()
    IMPORT = auto(); EXTERN = auto(); INLINE = auto()
    # types
    I8=auto(); I16=auto(); I32=auto(); I64=auto()
    U8=auto(); U16=auto(); U32=auto(); U64=auto()
    F32=auto(); F64=auto(); BOOL_T=auto(); STR_T=auto(); VOID=auto()
    PTR=auto(); SLICE=auto()
    # operators
    PLUS=auto(); MINUS=auto(); STAR=auto(); SLASH=auto(); PERCENT=auto()
    AMP=auto(); PIPE=auto(); CARET=auto(); TILDE=auto(); LSHIFT=auto(); RSHIFT=auto()
    EQ=auto(); NEQ=auto(); LT=auto(); GT=auto(); LE=auto(); GE=auto()
    AND=auto(); OR=auto(); NOT=auto()
    ASSIGN=auto(); PLUS_EQ=auto(); MINUS_EQ=auto(); STAR_EQ=auto(); SLASH_EQ=auto()
    ARROW=auto(); FAT_ARROW=auto(); DOT=auto(); DOTDOT=auto(); COLON=auto()
    COMMA=auto(); SEMICOLON=auto(); AT=auto()
    # delimiters
    LPAREN=auto(); RPAREN=auto(); LBRACE=auto(); RBRACE=auto()
    LBRACKET=auto(); RBRACKET=auto()
    # meta
    EOF=auto()


KEYWORDS: dict[str, TK] = {
    'fn': TK.FN, 'let': TK.LET, 'mut': TK.MUT,
    'if': TK.IF, 'else': TK.ELSE, 'while': TK.WHILE,
    'for': TK.FOR, 'in': TK.IN, 'return': TK.RETURN,
    'break': TK.BREAK, 'continue': TK.CONTINUE,
    'struct': TK.STRUCT, 'alloc': TK.ALLOC, 'free': TK.FREE,
    'as': TK.AS, 'import': TK.IMPORT, 'extern': TK.EXTERN,
    'inline': TK.INLINE,
    'true': TK.BOOL, 'false': TK.BOOL, 'nil': TK.NIL,
    'i8': TK.I8, 'i16': TK.I16, 'i32': TK.I32, 'i64': TK.I64,
    'u8': TK.U8, 'u16': TK.U16, 'u32': TK.U32, 'u64': TK.U64,
    'f32': TK.F32, 'f64': TK.F64, 'bool': TK.BOOL_T,
    'str': TK.STR_T, 'void': TK.VOID, 'ptr': TK.PTR, 'slice': TK.SLICE,
}

SYMBOLS: list[tuple[str, TK]] = sorted([
    ('...', TK.DOTDOT), ('=>', TK.FAT_ARROW), ('->', TK.ARROW),
    ('<<', TK.LSHIFT), ('>>', TK.RSHIFT),
    ('==', TK.EQ), ('!=', TK.NEQ), ('<=', TK.LE), ('>=', TK.GE),
    ('&&', TK.AND), ('||', TK.OR),
    ('+=', TK.PLUS_EQ), ('-=', TK.MINUS_EQ), ('*=', TK.STAR_EQ), ('/=', TK.SLASH_EQ),
    ('..', TK.DOTDOT),
    ('+', TK.PLUS), ('-', TK.MINUS), ('*', TK.STAR), ('/', TK.SLASH),
    ('%', TK.PERCENT), ('&', TK.AMP), ('|', TK.PIPE), ('^', TK.CARET),
    ('~', TK.TILDE), ('<', TK.LT), ('>', TK.GT), ('!', TK.NOT),
    ('=', TK.ASSIGN), ('.', TK.DOT), (':', TK.COLON), (',', TK.COMMA),
    (';', TK.SEMICOLON), ('@', TK.AT),
    ('(', TK.LPAREN), (')', TK.RPAREN), ('{', TK.LBRACE), ('}', TK.RBRACE),
    ('[', TK.LBRACKET), (']', TK.RBRACKET),
], key=lambda x: -len(x[0]))


@dataclass
class Token:
    kind: TK
    value: object  # str/int/float/bool/None
    line: int
    col: int

    def __repr__(self):
        return f'Token({self.kind.name}, {self.value!r}, {self.line}:{self.col})'


class LexError(Exception):
    pass


def tokenize(src: str, filename: str = '<input>') -> list[Token]:
    tokens: list[Token] = []
    i = 0
    line = 1
    line_start = 0
    n = len(src)

    while i < n:
        col = i - line_start + 1

        # whitespace
        if src[i] in ' \t\r':
            i += 1; continue
        if src[i] == '\n':
            line += 1; line_start = i + 1; i += 1; continue

        # line comment
        if src[i:i+2] == '//':
            while i < n and src[i] != '\n':
                i += 1
            continue

        # block comment
        if src[i:i+2] == '/*':
            i += 2
            while i < n and src[i:i+2] != '*/':
                if src[i] == '\n':
                    line += 1; line_start = i + 1
                i += 1
            i += 2; continue

        # string literal
        if src[i] == '"':
            i += 1; s = []
            while i < n and src[i] != '"':
                if src[i] == '\\':
                    i += 1
                    esc = {'n':'\n','t':'\t','r':'\r','"':'"','\\':'\\','0':'\0'}.get(src[i], src[i])
                    s.append(esc)
                else:
                    if src[i] == '\n': line += 1; line_start = i + 1
                    s.append(src[i])
                i += 1
            i += 1  # closing "
            tokens.append(Token(TK.STR, ''.join(s), line, col))
            continue

        # number
        if src[i].isdigit() or (src[i] == '0' and i+1 < n and src[i+1] in 'xXbBoO'):
            j = i
            is_float = False
            if src[i:i+2] in ('0x','0X'):
                i += 2
                while i < n and (src[i] in '0123456789abcdefABCDEF_'): i += 1
                tokens.append(Token(TK.INT, int(src[j:i].replace('_',''), 16), line, col))
            elif src[i:i+2] in ('0b','0B'):
                i += 2
                while i < n and src[i] in '01_': i += 1
                tokens.append(Token(TK.INT, int(src[j:i].replace('_',''), 2), line, col))
            elif src[i:i+2] in ('0o','0O'):
                i += 2
                while i < n and src[i] in '01234567_': i += 1
                tokens.append(Token(TK.INT, int(src[j:i].replace('_',''), 8), line, col))
            else:
                while i < n and (src[i].isdigit() or src[i] == '_'): i += 1
                if i < n and src[i] == '.' and (i+1 >= n or src[i+1] != '.'):
                    is_float = True; i += 1
                    while i < n and (src[i].isdigit() or src[i] == '_'): i += 1
                if i < n and src[i] in 'eE':
                    is_float = True; i += 1
                    if i < n and src[i] in '+-': i += 1
                    while i < n and src[i].isdigit(): i += 1
                raw = src[j:i].replace('_','')
                if is_float:
                    tokens.append(Token(TK.FLOAT, float(raw), line, col))
                else:
                    tokens.append(Token(TK.INT, int(raw), line, col))
            continue

        # identifier / keyword
        if src[i].isalpha() or src[i] == '_':
            j = i
            while i < n and (src[i].isalnum() or src[i] == '_'): i += 1
            word = src[j:i]
            if word in KEYWORDS:
                kind = KEYWORDS[word]
                val = True if word == 'true' else (False if word == 'false' else word)
                tokens.append(Token(kind, val, line, col))
            else:
                tokens.append(Token(TK.IDENT, word, line, col))
            continue

        # symbols (longest match first)
        matched = False
        for sym, kind in SYMBOLS:
            if src[i:i+len(sym)] == sym:
                tokens.append(Token(kind, sym, line, col))
                i += len(sym)
                matched = True
                break
        if matched: continue

        raise LexError(f"{filename}:{line}:{col}: unexpected character {src[i]!r}")

    tokens.append(Token(TK.EOF, None, line, i - line_start + 1))
    return tokens
