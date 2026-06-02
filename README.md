# Vex + Flux

**Vex** is a statically-typed compiled language. **Flux** is a binary serialization format. Both are designed for maximum efficiency — no garbage collector, no text parsing, no runtime overhead.

```vex
fn fib(n: i64) -> i64 {
    if n <= 1 { return n }
    return fib(n - 1) + fib(n - 2)
}

fn main() -> i32 {
    print("fib(40) = %lld\n", fib(40))
    return 0
}
```

```
vexc fib.vex -O3 -o fib && ./fib
fib(40) = 102334155          # runs in 0.14s  (Python takes 10s)
```

---

## Performance

### Vex vs Python — fib(40)

| | Time |
|---|---|
| Vex (`-O3`) | 0.14s |
| Python | 10.06s |
| Speedup | **71×** |

### Flux vs JSON — serialization

| Format | Size | Encode | Decode |
|---|---|---|---|
| JSON (Python) | 161B | 2.3 µs | 2.1 µs |
| Flux C (self-describing) | 50B | 26 ns | 21 ns |
| Flux C (schema mode) | **20B** | **10 ns** | **9 ns** |

Schema mode strips field names from the wire entirely. At 100M+ records/sec it is suitable for high-frequency logging, IPC, and network protocols.

---

## Vex Language

### Requirements

- Python 3.10+ (the compiler)
- gcc (to compile generated C)

### Install

```bash
git clone https://github.com/anolis/vex-lang
cd vex-lang
chmod +x vexc
# optionally: ln -s $(pwd)/vexc ~/.local/bin/vexc
```

### Compile

```bash
vexc hello.vex -o hello          # compile to binary
vexc hello.vex -O3 -o hello      # max optimization
vexc hello.vex -S                # emit C source only (hello.c)
vexc hello.vex -v                # verbose: show gcc command
```

### Types

| Vex | C | Width |
|---|---|---|
| `i8` `i16` `i32` `i64` | `int8_t` … `int64_t` | signed integers |
| `u8` `u16` `u32` `u64` | `uint8_t` … `uint64_t` | unsigned integers |
| `f32` `f64` | `float` `double` | IEEE 754 |
| `bool` | `int` | 0 or 1 |
| `str` | `const char*` | null-terminated |
| `ptr<T>` / `ptr<mut T>` | `const T*` / `T*` | pointers |
| `[T; N]` | `T[N]` | fixed arrays |
| `void` | `void` | no value |

### Variables

```vex
let x: i64 = 42          // immutable
let mut count = 0         // mutable, type inferred as i32
count += 1
```

### Functions

```vex
fn add(a: i64, b: i64) -> i64 {
    return a + b
}

inline fn square(x: f64) -> f64 { return x * x }   // static inline in C

extern fn sqrt(x: f64) -> f64                       // declare a C function
```

### Control flow

```vex
if x > 0 {
    print("positive\n")
} else if x < 0 {
    print("negative\n")
} else {
    print("zero\n")
}

while n > 0 { n -= 1 }

for val in arr { print("%d\n", val) }
```

### Structs

```vex
struct Vec3 {
    x: f64,
    y: f64,
    z: f64,
}

fn dot(a: Vec3, b: Vec3) -> f64 {
    return a.x * b.x + a.y * b.y + a.z * b.z
}

fn main() -> i32 {
    let v: Vec3 = Vec3 { x: 1.0, y: 2.0, z: 3.0 }
    let w: Vec3 = Vec3 { x: 4.0, y: 5.0, z: 6.0 }
    print("dot = %f\n", dot(v, w))
    return 0
}
```

### Memory

No garbage collector. Allocate explicitly, free explicitly.

```vex
struct Node {
    value: i64,
    next: ptr<mut Node>,    // self-referential — works out of the box
}

fn main() -> i32 {
    let a: ptr<mut Node> = alloc<Node>()   // malloc(sizeof(Node))
    (*a).value = 42
    (*a).next = nil

    print("value = %lld\n", (*a).value)
    free(a)
    return 0
}
```

`alloc<T>()` — one value. `alloc<T>(n)` — n values (slice). `free(p)` — release. `nil` — null pointer.

### Calling C

```vex
extern fn strlen(s: str) -> u64
extern fn memcpy(dst: ptr<mut u8>, src: ptr<u8>, n: u64) -> ptr<mut u8>

fn main() -> i32 {
    print("length = %llu\n", strlen("hello"))
    return 0
}
```

Standard headers (`stdio.h`, `stdlib.h`, `string.h`) are always included. Link any C library by passing flags through gcc after `-S`.

---

## Flux Format

### Python

```python
from flux.flux import encode, decode, Schema

# Self-describing (no schema needed)
blob = encode({"user_id": 1, "name": "Alice", "score": 99.5, "active": True})
data = decode(blob)

# Schema mode — field names not stored on the wire
USER = Schema(["user_id", "name", "score", "active"])
blob = USER.encode({"user_id": 1, "name": "Alice", "score": 99.5, "active": True})
data = Schema.decode(blob)   # → 20 bytes vs 72 bytes as JSON
```

### C

```c
#include "flux/flux.h"

uint8_t buf[256];
size_t pos = 0;

// Encode
flux_encode_map_header(buf, sizeof(buf), &pos, 2);
flux_encode_str(buf, sizeof(buf), &pos, "id", 2);
flux_encode_int64(buf, sizeof(buf), &pos, 42);
flux_encode_str(buf, sizeof(buf), &pos, "ok", 2);
flux_encode_bool(buf, sizeof(buf), &pos, 1);

// Decode
FluxValue val;
size_t rpos = 0;
flux_decode(buf, pos, &rpos, &val);          // MAP, val.v.count = 2
for (size_t i = 0; i < val.v.count; i++) {
    FluxValue key, value;
    flux_decode(buf, pos, &rpos, &key);      // key: val.v.str.ptr / .len
    flux_decode(buf, pos, &rpos, &value);    // value: val.v.i64, .f64, etc.
}
```

Build: `gcc -O3 myprogram.c flux/flux.c -lm`

String values point directly into the source buffer — zero copy, zero allocation.

---

## Benchmarks

```bash
# Flux Python vs JSON
python3 bench/bench_flux.py

# Flux C (10 million iterations)
gcc -O3 -o bench_flux bench/bench_flux.c flux/flux.c -lm && ./bench_flux

# Vex vs Python — fib(40)
vexc examples/fib.vex -O3 -o fib && time ./fib
time python3 -c "
def fib(n): return n if n<=1 else fib(n-1)+fib(n-2)
print(fib(40))
"
```

---

## How the Compiler Works

```
.vex source
    │
    ▼
lexer.py       tokenize — produces a flat list of typed tokens
    │
    ▼
parser.py      Pratt expression parser + recursive-descent statements → AST
    │
    ▼
typeck.py      scope analysis, type inference, compatibility checking
    │
    ▼
codegen.py     AST → C source string
    │
    ▼
gcc -O3        C → native binary
```

All Vex functions are emitted with a `vex_` prefix in C to avoid collisions with the standard library.

---

## Project Layout

```
vexc               compiler CLI
vex/
  lexer.py         tokenizer
  ast.py           AST node types
  parser.py        parser
  typeck.py        type checker
  codegen.py       C code generator
flux/
  flux.py          Python encoder/decoder
  flux.h           C header
  flux.c           C implementation
examples/
  hello.vex        Hello World
  fib.vex          recursive fibonacci (benchmark)
  structs.vex      Vec3 math
  alloc.vex        heap allocation and linked structs
bench/
  bench_flux.py    Python: Flux vs JSON
  bench_flux.c     C: 10M iteration throughput test
docs/
  getting-started.md
  vex.md           full language reference
  flux.md          full format reference
```

---

## Documentation

- [Getting Started](docs/getting-started.md) — install, first programs, step-by-step
- [Vex Language Reference](docs/vex.md) — all types, operators, memory, gotchas
- [Flux Format Reference](docs/flux.md) — wire format, C API, schema mode, performance
