# Getting Started

This guide walks you from installation to a working program in about five minutes.

---

## Requirements

- Python 3.10 or later (the compiler is written in Python)
- gcc (any recent version — used to compile generated C)

---

## Installation

No package manager needed. Clone or copy the repo, then make the compiler executable:

```bash
chmod +x vexc
```

Optionally symlink it onto your PATH:

```bash
ln -s "$(pwd)/vexc" ~/.local/bin/vexc
```

---

## Hello, World

Create `hello.vex`:

```vex
fn main() -> i32 {
    print("Hello, World!\n")
    return 0
}
```

Compile and run:

```bash
./vexc hello.vex -o hello
./hello
```

Output:

```
Hello, World!
```

---

## Your First Real Program — Fibonacci

Create `fib.vex`:

```vex
fn fib(n: i64) -> i64 {
    if n <= 1 { return n }
    return fib(n - 1) + fib(n - 2)
}

fn main() -> i32 {
    let result: i64 = fib(40)
    print("fib(40) = %lld\n", result)
    return 0
}
```

```bash
./vexc fib.vex -O3 -o fib
./fib
# fib(40) = 102334155
```

With `-O3` this runs in about 0.14 seconds. The equivalent Python program takes ~10 seconds.

---

## Inspecting Generated C

Use `-S` to emit the C source instead of compiling:

```bash
./vexc fib.vex -S
cat fib.c
```

This is useful for debugging, understanding what Vex emits, or tweaking the output manually.

---

## Using Structs

```vex
struct Point {
    x: f64,
    y: f64,
}

fn dist_sq(a: Point, b: Point) -> f64 {
    let dx: f64 = a.x - b.x
    let dy: f64 = a.y - b.y
    return dx * dx + dy * dy
}

fn main() -> i32 {
    let a: Point = Point { x: 0.0, y: 0.0 }
    let b: Point = Point { x: 3.0, y: 4.0 }
    print("dist_sq = %f\n", dist_sq(a, b))
    return 0
}
```

```
dist_sq = 25.000000
```

---

## Heap Allocation

```vex
struct Node {
    value: i64,
    next: ptr<mut Node>,
}

fn main() -> i32 {
    let a: ptr<mut Node> = alloc<Node>()
    let b: ptr<mut Node> = alloc<Node>()

    (*a).value = 1
    (*a).next  = b
    (*b).value = 2
    (*b).next  = nil

    print("%lld -> %lld\n", (*a).value, (*(*a).next).value)

    free(b)
    free(a)
    return 0
}
```

```
1 -> 2
```

`alloc<T>()` allocates one `T` on the heap. `free(p)` releases it. There is no garbage collector — you own the memory.

---

## Calling C from Vex

Declare the C function with `extern fn`, then call it like any other function:

```vex
extern fn sqrt(x: f64) -> f64
extern fn abs(x: i32) -> i32

fn main() -> i32 {
    let r: f64 = sqrt(2.0)
    print("sqrt(2) = %f\n", r)
    return 0
}
```

The `extern fn` declaration tells Vex the signature; the linker resolves the symbol. Standard C library functions (`sqrt`, `memcpy`, `strlen`, etc.) are always available since Vex links with `-lm` and includes `<stdlib.h>`, `<string.h>`, `<stdio.h>` by default.

---

## Using Flux for Serialization

Flux is the companion binary format. Use it from Python:

```python
from flux.flux import encode, decode

record = {
    "user_id": 99,
    "name": "Alice",
    "score": 9999.5,
    "active": True,
}

blob = encode(record)        # bytes — smaller than JSON
back = decode(blob)          # identical dict
assert back == record
```

Or use schema mode when all records have the same shape:

```python
from flux.flux import Schema

USER = Schema(["user_id", "name", "score", "active"])

blob = USER.encode({"user_id": 99, "name": "Alice", "score": 9999.5, "active": True})
# blob is ~20 bytes — no field names stored on the wire

back = Schema.decode(blob)
```

For the C API, see `docs/flux.md`.

---

## Project Layout

```
vexc               — compiler CLI (Python script)
vex/
  lexer.py         — tokenizer
  ast.py           — AST nodes
  parser.py        — parser (Pratt expressions + statements)
  typeck.py        — type checker
  codegen.py       — C code generator
flux/
  flux.py          — Python encoder/decoder
  flux.h           — C header
  flux.c           — C implementation
examples/
  hello.vex
  fib.vex
  structs.vex
  alloc.vex
bench/
  bench_flux.py    — Python Flux vs JSON benchmark
  bench_flux.c     — C Flux benchmark (10M iterations)
docs/
  getting-started.md  ← you are here
  vex.md              — full language reference
  flux.md             — full Flux format reference
```

---

## Next Steps

- Read `docs/vex.md` for the full language reference — all types, operators, and gotchas.
- Read `docs/flux.md` for the Flux wire format and C API.
- Look at `examples/` for complete working programs.
- Run `bench/bench_flux.py` and `bench/bench_flux.c` to see Flux performance on your machine.
