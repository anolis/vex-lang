# Vex Language Reference

Vex is a statically-typed, compiled language that transpiles to C and links with gcc/clang. It is designed for maximum runtime efficiency: no garbage collector, value types by default, explicit heap allocation, and zero runtime overhead.

---

## Quick Start

```
vexc hello.vex -o hello
./hello
```

**Flags:**

| Flag | Meaning |
|---|---|
| `-o <file>` | Output binary name (default: `a.out`) |
| `-S` | Emit C source next to the `.vex` file, don't compile |
| `-O<n>` | Optimization level passed to gcc (`-O0` through `-O3`, default `-O2`) |
| `-v` | Verbose: print the gcc command and confirm output path |

---

## Types

### Primitive types

| Vex type | C type | Width |
|---|---|---|
| `i8` | `int8_t` | 8-bit signed |
| `i16` | `int16_t` | 16-bit signed |
| `i32` | `int32_t` | 32-bit signed |
| `i64` | `int64_t` | 64-bit signed |
| `u8` | `uint8_t` | 8-bit unsigned |
| `u16` | `uint16_t` | 16-bit unsigned |
| `u32` | `uint32_t` | 32-bit unsigned |
| `u64` | `uint64_t` | 64-bit unsigned |
| `f32` | `float` | 32-bit IEEE 754 |
| `f64` | `double` | 64-bit IEEE 754 |
| `bool` | `int` | 0 or 1 |
| `str` | `const char*` | null-terminated string pointer |
| `void` | `void` | no value |

### Pointer types

```
ptr<T>       // immutable pointer to T  →  const T*
ptr<mut T>   // mutable pointer to T    →  T*
```

### Slice types

```
slice<T>     // fat pointer (T*, len) — currently emits T*
```

### Array types

```
[T; N]       // fixed-size array of N elements of type T
```

### Struct types

Defined with `struct`, referenced by name. See [Structs](#structs).

### Function types

```
fn(i32, f64) -> bool    // function taking i32 and f64, returning bool
```

---

## Variables

```
let name: type = expr
let mut name: type = expr
let name = expr             // type inferred from expr
let mut name = expr
```

- `let` bindings are immutable by default.
- `mut` allows the binding to be reassigned.
- The type annotation is optional when it can be inferred.

```vex
let x: i64 = 42
let y = 3.14          // inferred as f64
let mut count = 0     // inferred as i32, reassignable
count = count + 1
```

### Assignment operators

```
x = expr
x += expr
x -= expr
x *= expr
x /= expr
```

---

## Functions

```vex
fn name(param: type, param: type) -> return_type {
    // body
}
```

- Return type defaults to `void` if `->` is omitted.
- Parameters are passed by value.
- `mut` on a parameter allows reassigning it inside the function body.
- Recursive calls are supported; all functions are forward-declared automatically.

```vex
fn add(a: i64, b: i64) -> i64 {
    return a + b
}

fn greet(name: str) {
    print("Hello, %s!\n", name)
}

fn fib(n: i64) -> i64 {
    if n <= 1 { return n }
    return fib(n - 1) + fib(n - 2)
}
```

### Inline functions

```vex
inline fn square(x: f64) -> f64 {
    return x * x
}
```

Emitted as `static inline` in C. Use for hot, small functions where call overhead matters.

### Extern functions

```vex
extern fn memcpy(dst: ptr<mut u8>, src: ptr<u8>, n: u64) -> ptr<mut u8>
```

Declares a C function that Vex can call. No body. The linker resolves it.

---

## Control Flow

### If / else

```vex
if cond {
    // ...
} else if other_cond {
    // ...
} else {
    // ...
}
```

### While loop

```vex
while cond {
    // ...
}
```

### For loop (over array or slice)

```vex
let arr: [i32; 3] = [10, 20, 30]
for val in arr {
    print("%d\n", val)
}
```

The loop variable `val` takes the element type. The iteration count is derived from `sizeof`/element size — works for fixed-size arrays. For slices, pair with an explicit length.

---

## Operators

### Arithmetic

```
+  -  *  /  %
```

### Bitwise

```
&  |  ^  ~  <<  >>
```

### Comparison

```
==  !=  <  >  <=  >=
```

Comparison expressions have type `bool`.

### Logical

```
&&  ||  !
```

Short-circuit evaluation follows C semantics.

### Cast

```vex
let x: i32 = 65535
let y: u8 = x as u8     // truncates to 255
let f: f64 = x as f64
```

`as` casts are zero-cost. They emit a C cast expression.

### Address-of and dereference

```vex
let p: ptr<i32> = &x        // take address
let v: i32 = *p             // dereference
```

### Precedence (high to low)

| Level | Operators |
|---|---|
| 10 | `*`  `/`  `%` |
| 9 | `+`  `-` |
| 8 | `<<`  `>>` |
| 7 | `<`  `>`  `<=`  `>=` |
| 6 | `==`  `!=` |
| 5 | `&` |
| 4 | `^` |
| 3 | `\|` |
| 2 | `&&` |
| 1 | `\|\|` |

Unary `!`, `~`, `-`, `*` (deref), `&` (addr-of) bind tighter than all binary operators.

---

## Structs

```vex
struct Point {
    x: f64,
    y: f64,
}
```

Trailing comma after the last field is optional.

### Struct literals

```vex
let p: Point = Point { x: 1.0, y: 2.0 }
```

Fields can appear in any order in the literal, but all fields must be provided.

### Field access

```vex
let dx: f64 = p.x
```

On a pointer-to-struct, use `(*ptr).field`:

```vex
let q: ptr<mut Point> = alloc<Point>()
(*q).x = 5.0
(*q).y = 10.0
```

### Self-referential structs

Structs may contain pointers to themselves:

```vex
struct Node {
    value: i64,
    next: ptr<mut Node>,
}
```

Vex emits C forward declarations automatically so this compiles cleanly.

---

## Memory Management

Vex has **no garbage collector**. You allocate explicitly and free explicitly.

### alloc

```vex
alloc<T>()       // allocate one T on the heap, returns ptr<mut T>
alloc<T>(count)  // allocate count T values, returns slice<T> (i.e. T*)
```

`alloc` calls `malloc` underneath. It never fails silently — if `malloc` returns NULL and you dereference, that is undefined behavior (same as C). Check the pointer if you need safety.

```vex
let node: ptr<mut Node> = alloc<Node>()
(*node).value = 42
(*node).next = nil
```

### free

```vex
free(ptr)
```

Calls `malloc`'s `free`. The pointer must have come from `alloc`. Freeing twice or freeing a stack pointer is undefined behavior.

```vex
free(node)
```

### Stack vs heap

Local variables are stack-allocated:

```vex
let x: i64 = 10        // on the stack
let p: ptr<mut i64> = alloc<i64>()   // on the heap
(*p) = 10
free(p)
```

Prefer stack allocation whenever the lifetime is bounded by the current function scope.

### nil

`nil` is the null pointer constant. It is compatible with any pointer type:

```vex
let p: ptr<mut Node> = nil
```

Dereferencing `nil` crashes (segfault). Check before use:

```vex
if p != nil {
    print("value = %lld\n", (*p).value)
}
```

---

## Literals

| Kind | Examples |
|---|---|
| Integer | `0`, `42`, `1_000_000`, `-7` |
| Hex | `0xFF`, `0xDEAD_BEEF` |
| Binary | `0b1010_1010` |
| Octal | `0o755` |
| Float | `3.14`, `1.0e-9`, `6.022e23` |
| String | `"hello\nworld"` |
| Bool | `true`, `false` |
| Null | `nil` |
| Array | `[1, 2, 3]` |

Underscores in numeric literals are ignored and exist only for readability.

String escape sequences: `\n` `\t` `\r` `\"` `\\` `\0`.

---

## Built-in Functions

Vex maps the following names directly to C standard library functions:

| Vex name | C name | Notes |
|---|---|---|
| `print(fmt, ...)` | `printf` | format string + variadic args |
| `println(fmt, ...)` | `printf` | alias for `printf` |

Any other C function can be called by declaring it `extern fn`.

**Printing format strings follow C `printf` conventions:**

```vex
print("int: %d\n", 42)
print("long: %lld\n", some_i64)
print("float: %f\n", 3.14)
print("string: %s\n", "hello")
print("hex: 0x%X\n", 255)
```

---

## Imports

```vex
import "mylib.h"
```

Emits `#include "mylib.h"` at the top of the generated C file. Use this to pull in C headers when you need `extern fn` declarations or C type definitions.

---

## Namespacing

All Vex functions are emitted with a `vex_` prefix in C (`fn add` → `int32_t vex_add(...)`). This prevents collisions with C standard library names. The prefix is transparent to Vex code — you always use the bare name.

If your module defines `fn main`, Vex emits a C `main()` that calls `vex_main()`.

---

## Complete Example — Linked List

```vex
struct List {
    value: i64,
    next: ptr<mut List>,
}

fn push(head: ptr<mut List>, val: i64) -> ptr<mut List> {
    let node: ptr<mut List> = alloc<List>()
    (*node).value = val
    (*node).next = head
    return node
}

fn sum(head: ptr<mut List>) -> i64 {
    let mut total: i64 = 0
    let mut cur: ptr<mut List> = head
    while cur != nil {
        total = total + (*cur).value
        cur = (*cur).next
    }
    return total
}

fn free_list(head: ptr<mut List>) {
    let mut cur: ptr<mut List> = head
    while cur != nil {
        let next: ptr<mut List> = (*cur).next
        free(cur)
        cur = next
    }
}

fn main() -> i32 {
    let mut list: ptr<mut List> = nil
    list = push(list, 10)
    list = push(list, 20)
    list = push(list, 30)
    print("sum = %lld\n", sum(list))
    free_list(list)
    return 0
}
```

Compile and run:

```
vexc list.vex -o list
./list
# sum = 60
```

---

## Complete Example — Vec3 Math

```vex
struct Vec3 {
    x: f64,
    y: f64,
    z: f64,
}

fn dot(a: Vec3, b: Vec3) -> f64 {
    return a.x * b.x + a.y * b.y + a.z * b.z
}

fn length_sq(v: Vec3) -> f64 {
    return dot(v, v)
}

fn scale(v: Vec3, s: f64) -> Vec3 {
    return Vec3 { x: v.x * s, y: v.y * s, z: v.z * s }
}

fn main() -> i32 {
    let v: Vec3 = Vec3 { x: 1.0, y: 2.0, z: 3.0 }
    let w: Vec3 = Vec3 { x: 4.0, y: 5.0, z: 6.0 }
    print("dot      = %f\n", dot(v, w))
    print("len_sq   = %f\n", length_sq(v))
    let scaled: Vec3 = scale(v, 2.0)
    print("scaled.x = %f\n", scaled.x)
    return 0
}
```

---

## Tips and Gotchas

**No implicit conversions between integer widths.** Use `as` explicitly:

```vex
let a: i32 = 1000
let b: i64 = a as i64
```

**Call parentheses must be on the same line as the callee.** Vex uses line-aware parsing to avoid ambiguity without semicolons. This is valid:

```vex
let result = some_fn(
    arg1, arg2
)
```

But this silently creates two statements (call without args, then `(arg1, arg2)` would be a syntax error):

```vex
// DON'T:
let result = some_fn
(arg1, arg2)
```

**Struct field assignment requires dereferencing pointers:**

```vex
// ptr<mut Point> p
(*p).x = 1.0     // correct
p.x = 1.0        // wrong — p is a pointer, not a struct
```

**`free` only takes direct pointer expressions.** Don't free a `nil`:

```vex
if p != nil { free(p) }
```
