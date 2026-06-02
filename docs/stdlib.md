# Vex Standard Library

The Vex standard library is a collection of `.vex` modules in the `std/` directory. Each module wraps a set of C standard library functions and adds thin Vex-native helpers on top. All modules are imported with a relative path:

```
import "../std/mem.vex"
import "../std/io.vex"
```

Modules that depend on other stdlib modules import them internally — you do not need to import transitive dependencies yourself.

---

## Table of Contents

- [mem](#mem) — raw memory and heap allocation
- [str](#str) — null-terminated string operations
- [io](#io) — file I/O (stdio)
- [fs](#fs) — filesystem operations
- [math](#math) — floating-point and integer math
- [hash](#hash) — open-addressing hash map
- [flux](#flux) — Flux binary format encoder/decoder
- [net](#net) — TCP/IP socket primitives

---

## mem

**File:** `std/mem.vex`

Raw memory manipulation and heap allocation. These map 1-to-1 onto the C standard library functions of the same name.

> `free` is a built-in Vex keyword, not an extern fn. Use the `free` statement directly.

### Functions

#### Allocation

```
fn malloc(size: u64) -> ptr<mut u8>
```
Allocate `size` bytes on the heap. Returns nil on failure. Prefer `alloc<T>()` for typed allocations.

```
fn calloc(count: u64, size: u64) -> ptr<mut u8>
```
Allocate and zero-initialize `count * size` bytes.

```
fn realloc(p: ptr<mut u8>, size: u64) -> ptr<mut u8>
```
Resize a heap allocation. The old pointer is invalid after this call.

#### Copying and Moving

```
fn memcpy(dst: ptr<mut u8>, src: ptr<u8>, n: u64) -> ptr<mut u8>
```
Copy `n` bytes from `src` to `dst`. Regions must not overlap.

```
fn memmove(dst: ptr<mut u8>, src: ptr<u8>, n: u64) -> ptr<mut u8>
```
Copy `n` bytes, handling overlapping regions correctly.

```
fn mem_copy(dst: ptr<mut u8>, src: ptr<u8>, n: u64)
```
Wrapper around `memcpy` with no return value.

#### Initialization

```
fn memset(dst: ptr<mut u8>, c: i32, n: u64) -> ptr<mut u8>
```
Fill `n` bytes starting at `dst` with the byte value `c`.

```
fn mem_zero(dst: ptr<mut u8>, n: u64)
```
Zero-fill `n` bytes. Equivalent to `memset(dst, 0, n)`.

#### Comparison

```
fn memcmp(a: ptr<u8>, b: ptr<u8>, n: u64) -> i32
```
Compare `n` bytes. Returns 0 if equal, <0 if `a` < `b`, >0 if `a` > `b`.

```
fn mem_eq(a: ptr<u8>, b: ptr<u8>, n: u64) -> bool
```
Return `true` if the first `n` bytes of `a` and `b` are identical.

### Common Patterns

```
// Zero-initialize a struct via its pointer
let s: ptr<mut MyStruct> = alloc<MyStruct>()
mem_zero(s as ptr<mut u8>, 32)   // must know size manually

// Copy bytes between buffers
let dst: ptr<mut u8> = malloc(len)
mem_copy(dst, src, len)

// Read a struct from a byte buffer (e.g. a file record)
let hdr: ptr<mut RecHdr> = alloc<RecHdr>()
memcpy(hdr as ptr<mut u8>, buf + offset, rechdr_size())
```

---

## str

**File:** `std/str.vex`

Operations on null-terminated C strings (`str` type). The `str` type in Vex is a `const char*` — an immutable pointer to a null-terminated sequence of bytes.

### Functions

#### Measurement

```
fn strlen(s: str) -> u64
fn str_len(s: str) -> u64
```
Return the length of `s` in bytes, not including the null terminator. `str_len` is an alias.

#### Comparison

```
fn strcmp(a: str, b: str) -> i32
```
Lexicographic comparison. Returns 0 if equal, <0 if `a` < `b`, >0 if `a` > `b`.

```
fn strncmp(a: str, b: str, n: u64) -> i32
```
Compare at most `n` bytes.

```
fn str_eq(a: str, b: str) -> bool
```
Return `true` if `a` and `b` are equal. Prefer this over `strcmp` when you just need equality.

```
fn str_starts_with(s: str, prefix: str) -> bool
```
Return `true` if `s` begins with `prefix`.

#### Searching

```
fn strchr(s: str, c: i32) -> ptr<mut u8>
```
Find first occurrence of byte `c` in `s`. Returns nil if not found.

```
fn strstr(haystack: str, needle: str) -> ptr<mut u8>
```
Find first occurrence of substring `needle` in `haystack`. Returns nil if not found.

#### Copying

```
fn strcpy(dst: ptr<mut u8>, src: str) -> ptr<mut u8>
fn strncpy(dst: ptr<mut u8>, src: str, n: u64) -> ptr<mut u8>
fn strcat(dst: ptr<mut u8>, src: str) -> ptr<mut u8>
```
Standard C string copy and concatenation. `dst` must be pre-allocated with enough space.

#### Parsing

```
fn atoi(s: str) -> i32
fn atol(s: str) -> i64
fn strtol(s: str, end: ptr<mut u8>, base: i32) -> i64
fn strtod(s: str, end: ptr<mut u8>) -> f64
```
Parse numeric values from strings. `strtol` and `strtod` set `end` to the first unparsed character; pass `nil` to ignore it.

### Common Patterns

```
// Equality check
if str_eq(cmd, "quit") { return 0 }

// Prefix routing
if str_starts_with(line, "GET ") { ... }

// Parse an integer from user input
let n: i64 = atol(argv[1])

// Build a string into a stack buffer (snprintf is in std/io.vex)
let buf: ptr<mut u8> = malloc(64)
snprintf(buf, 64, "user:%d", uid)
```

---

## io

**File:** `std/io.vex`

File I/O based on C stdio. `FILE*` is represented as `ptr<mut u8>` — an opaque handle that must never be dereferenced.

**Seek whence constants:**

| Constant | Value | Meaning |
|---|---|---|
| `SEEK_SET` | 0 | Absolute position |
| `SEEK_CUR` | 1 | Relative to current position |
| `SEEK_END` | 2 | Relative to end of file |

### Opening and Closing

```
fn fopen(path: str, mode: str) -> ptr<mut u8>
```
Open a file. Common modes: `"r"`, `"w"`, `"a"`, `"rb"`, `"wb"`, `"ab"`. Returns nil on failure.

```
fn fclose(fp: ptr<mut u8>) -> i32
```
Close a file handle. Always call this when done.

```
fn fflush(fp: ptr<mut u8>) -> i32
fn feof(fp: ptr<mut u8>) -> i32
fn ferror(fp: ptr<mut u8>) -> i32
fn clearerr(fp: ptr<mut u8>)
fn rewind(fp: ptr<mut u8>)
```
Standard stdio state management.

### Reading and Writing

```
fn fread(buf: ptr<mut u8>, size: u64, count: u64, fp: ptr<mut u8>) -> u64
```
Read `count` items of `size` bytes each. Returns number of items actually read.

```
fn fwrite(buf: ptr<u8>, size: u64, count: u64, fp: ptr<mut u8>) -> u64
```
Write `count` items of `size` bytes each. Returns number of items written.

```
fn fgetc(fp: ptr<mut u8>) -> i32
fn fputc(c: i32, fp: ptr<mut u8>) -> i32
fn fputs(s: str, fp: ptr<mut u8>) -> i32
```
Single-character and string output.

```
fn fprintf(fp: ptr<mut u8>, fmt: str) -> i32
fn snprintf(buf: ptr<mut u8>, size: u64, fmt: str) -> i32
```
Formatted output to a file or buffer. Both are variadic — pass additional arguments after `fmt`.

### Seeking

```
fn fseek(fp: ptr<mut u8>, offset: i64, whence: i32) -> i32
fn ftell(fp: ptr<mut u8>) -> i64
```
Seek and report position within a file.

### Filesystem

```
fn remove(path: str) -> i32
fn rename(old: str, new: str) -> i32
```
Delete or rename files. Returns 0 on success.

### Convenience Wrappers

```
fn io_read_all(path: str, out_len: ptr<mut u64>) -> ptr<mut u8>
```
Read an entire file into a heap-allocated buffer. Sets `*out_len` to the byte count. The buffer is null-terminated but may contain embedded nulls. **Caller must `free` the result.**

```
fn io_write_all(path: str, buf: ptr<u8>, len: u64) -> i32
```
Atomically write (overwrite) a file with `len` bytes from `buf`. Returns 0 on success, -1 on failure.

```
fn io_append(path: str, buf: ptr<u8>, len: u64) -> i32
```
Append `len` bytes from `buf` to `path`. Creates the file if it does not exist.

```
fn io_file_size(path: str) -> i64
```
Return the size of a file in bytes, or -1 if the file cannot be opened.

### Common Patterns

```
// Read a whole file
let mut sz: u64 = 0
let data: ptr<mut u8> = io_read_all("config.bin", &sz)
if data == nil { println("open failed"); return 1 }
// ... use data ...
free(data)

// Write bytes to a file
io_write_all("out.bin", buf, len)

// Append a log line
let line: ptr<mut u8> = malloc(64)
snprintf(line, 64, "[%d] event\n", code)
io_append("events.log", line as ptr<u8>, strlen(line as str))
free(line)

// Formatted output to stderr (stderr = fd 2, not accessible as ptr<mut u8> directly)
fprintf(fopen("/dev/stderr", "w"), "error: %s\n", msg)
```

---

## fs

**File:** `std/fs.vex`

Filesystem operations beyond file I/O — directory creation, existence checks, and path manipulation.

### Functions

```
fn fs_mkdir(path: str) -> i32
```
Create a directory with permissions `0755`. Returns 0 on success, -1 on failure (e.g., already exists).

```
fn fs_exists(path: str) -> bool
```
Return `true` if `path` exists (file or directory).

```
fn fs_unlink(path: str) -> i32
```
Delete a file. Returns 0 on success.

```
fn fs_rmdir(path: str) -> i32
```
Delete an empty directory. Returns 0 on success.

```
fn fs_chdir(path: str) -> i32
```
Change the current working directory. Returns 0 on success.

### Low-Level Externs

```
fn mkdir(path: str, mode: u32) -> i32
fn rmdir(path: str) -> i32
fn unlink(path: str) -> i32
fn access(path: str, mode: i32) -> i32   // mode 0 = F_OK (existence only)
fn getcwd(buf: ptr<mut u8>, size: u64) -> ptr<mut u8>
fn chdir(path: str) -> i32
fn realpath(path: str, resolved: ptr<mut u8>) -> ptr<mut u8>
```

### Common Patterns

```
// Create a data directory if it doesn't exist
if !fs_exists("/var/myapp/data") {
    fs_mkdir("/var/myapp/data")
}

// Get the absolute path of a relative path
let resolved: ptr<mut u8> = malloc(4096)
realpath("../../config", resolved)
print("config at: %s\n", resolved as str)
free(resolved)

// Delete a temp file on exit
fs_unlink("/tmp/work.bin")
```

---

## math

**File:** `std/math.vex`

Floating-point math (wraps `libm`) and integer helpers. When using `math.vex`, pass `-lm` to gcc — `vexc` does this automatically.

### Floating-Point Functions

```
fn sqrt(x: f64) -> f64
fn sqrtf(x: f32) -> f32
```
Square root.

```
fn pow(base: f64, exp: f64) -> f64
```
`base` raised to the power `exp`.

```
fn fabs(x: f64) -> f64
fn fabsf(x: f32) -> f32
```
Absolute value.

```
fn floor(x: f64) -> f64
fn ceil(x: f64) -> f64
fn round(x: f64) -> f64
```
Rounding toward −∞, +∞, and nearest integer.

```
fn log(x: f64) -> f64
fn log2(x: f64) -> f64
fn log10(x: f64) -> f64
fn exp(x: f64) -> f64
```
Natural log, log base 2, log base 10, and e^x.

```
fn sin(x: f64) -> f64
fn cos(x: f64) -> f64
fn tan(x: f64) -> f64
fn atan2(y: f64, x: f64) -> f64
```
Trigonometry. Arguments in radians.

```
fn fmin(a: f64, b: f64) -> f64
fn fmax(a: f64, b: f64) -> f64
```
Floating-point min/max (NaN-safe per C spec).

### Integer Helpers

```
fn min_i64(a: i64, b: i64) -> i64
fn max_i64(a: i64, b: i64) -> i64
```
Return the smaller or larger of two signed 64-bit integers.

```
fn clamp_i64(v: i64, lo: i64, hi: i64) -> i64
```
Clamp `v` to the range `[lo, hi]`.

```
fn abs_i64(x: i64) -> i64
```
Absolute value of a signed 64-bit integer.

### Common Patterns

```
// Euclidean distance
let dx: f64 = x2 - x1
let dy: f64 = y2 - y1
let dist: f64 = sqrt(dx*dx + dy*dy)

// Integer clamp for array index
let idx: i64 = clamp_i64(user_input, 0, len as i64 - 1)

// Degrees to radians
let rad: f64 = deg * 3.14159265358979 / 180.0
let s: f64 = sin(rad)
```

---

## hash

**File:** `std/hash.vex`  
**Imports:** `str.vex`, `mem.vex`

An open-addressing hash map with string keys and `u64` values. Values can store integers, byte offsets, or pointers cast to `u64`.

**HT_MISSING** sentinel: `0xFFFFFFFFFFFFFFFF` — returned by `ht_get` when a key is not present.

### Data Structures

```
struct HSlot {
    key:  ptr<mut u8>,
    val:  u64,
    hash: u64,
}

struct HTable {
    slots: ptr<mut u8>,
    cap:   u64,
    len:   u64,
}
```

`HTable.len` is the number of occupied slots. `HTable.cap` is the total slot capacity — choose a power of two larger than your expected key count.

### Functions

```
fn ht_new(cap: u64) -> ptr<mut HTable>
```
Allocate a new hash table with `cap` slots. All slots start empty. **Choose `cap` larger than the maximum number of keys** — load factor affects performance, and there is no automatic rehashing.

```
fn ht_set(ht: ptr<mut HTable>, key: str, val: u64)
```
Insert or update `key` → `val`. The key is heap-copied; the caller's string need not outlive this call.

```
fn ht_get(ht: ptr<mut HTable>, key: str) -> u64
```
Look up `key`. Returns the stored value, or `HT_MISSING` (`0xFFFFFFFFFFFFFFFF`) if not found.

```
fn ht_has(ht: ptr<mut HTable>, key: str) -> bool
```
Return `true` if `key` is in the table. Equivalent to `ht_get(ht, key) != 0xffffffffffffffff`.

```
fn ht_del(ht: ptr<mut HTable>, key: str)
```
Remove `key` from the table. Frees the heap-copied key string. No-op if key not present.

```
fn ht_free(ht: ptr<mut HTable>)
```
Free all slot key strings, the slot array, and the `HTable` itself.

### Common Patterns

```
// Basic usage
let ht: ptr<mut HTable> = ht_new(1024)
ht_set(ht, "name", name_ptr as u64)
ht_set(ht, "score", 9999)

let score: u64 = ht_get(ht, "score")
if score == 0xffffffffffffffff {
    println("key not found")
}

if ht_has(ht, "name") {
    ht_del(ht, "name")
}

ht_free(ht)

// Storing pointers as u64
let node: ptr<mut Node> = alloc<Node>()
ht_set(ht, "root", node as u64)
let root: ptr<mut Node> = ht_get(ht, "root") as ptr<mut Node>
```

> **Note:** `ht_del` marks the slot as empty by setting `key = nil`. This means linear-probe chains can be broken by a deletion. For best results, avoid heavy delete workloads on nearly-full tables.

---

## flux

**File:** `std/flux.vex`  
**Imports:** `mem.vex`, `str.vex`

Encoder and decoder for the **Flux binary format** — a compact, self-describing binary serialization format. Values are type-tagged at the byte level with automatic integer width selection (i8 through u64 as needed). Encoding is allocation-free; the caller supplies a fixed buffer.

### Type Tags

| Tag function | Value | Meaning |
|---|---|---|
| `flux_tag_null()` | 0 | null |
| `flux_tag_false()` | 1 | boolean false |
| `flux_tag_true()` | 2 | boolean true |
| `flux_tag_i8()` | 3 | signed 8-bit |
| `flux_tag_i16()` | 4 | signed 16-bit |
| `flux_tag_i32()` | 5 | signed 32-bit |
| `flux_tag_i64()` | 6 | signed 64-bit |
| `flux_tag_u8()` | 7 | unsigned 8-bit |
| `flux_tag_u16()` | 8 | unsigned 16-bit |
| `flux_tag_u32()` | 9 | unsigned 32-bit |
| `flux_tag_u64()` | 10 | unsigned 64-bit |
| `flux_tag_f32()` | 11 | 32-bit float |
| `flux_tag_f64()` | 12 | 64-bit float |
| `flux_tag_bytes()` | 13 | raw bytes (varint length prefix) |
| `flux_tag_str()` | 14 | UTF-8 string (varint length prefix) |
| `flux_tag_list()` | 15 | list header (varint element count) |
| `flux_tag_map()` | 16 | map header (varint pair count) |
| `flux_tag_schema()` | 17 | schema-mode header (varint schema ID) |

### Error Codes

| Function | Value | Meaning |
|---|---|---|
| `flux_ok()` | 0 | success |
| `flux_overflow()` | 1 | buffer too small |
| `flux_trunc()` | 2 | input truncated |
| `flux_badtag()` | 3 | unknown tag byte |

### FluxVal — Decoded Value

```
struct FluxVal {
    tag:     u8,
    ival:    i64,    // integer value (signed); also set for unsigned integers
    uval:    u64,    // integer value (unsigned); also set for signed integers
    fval:    f64,    // float value
    str_ptr: ptr<u8>,  // pointer into source buffer (not heap-allocated)
    str_len: u64,
    count:   u64,    // element count for list/map/schema
}
```

Both `ival` and `uval` are always set for integer types so you can read whichever interpretation you need without checking the tag.

`str_ptr` points into the source buffer — it is **not** null-terminated. Copy it before the buffer is freed.

### Encoders

All encoders take `(buf, cap, pos)` where `pos` is a `ptr<mut u64>` cursor advanced in place.

```
fn flux_enc_null(buf: ptr<mut u8>, cap: u64, pos: ptr<mut u64>) -> i32
fn flux_enc_bool(buf: ptr<mut u8>, cap: u64, pos: ptr<mut u64>, v: bool) -> i32
fn flux_enc_i64(buf: ptr<mut u8>, cap: u64, pos: ptr<mut u64>, v: i64) -> i32
fn flux_enc_f64(buf: ptr<mut u8>, cap: u64, pos: ptr<mut u64>, v: f64) -> i32
fn flux_enc_bytes(buf: ptr<mut u8>, cap: u64, pos: ptr<mut u64>, data: ptr<u8>, len: u64) -> i32
fn flux_enc_str(buf: ptr<mut u8>, cap: u64, pos: ptr<mut u64>, s: str) -> i32
fn flux_enc_list_hdr(buf: ptr<mut u8>, cap: u64, pos: ptr<mut u64>, count: u64) -> i32
fn flux_enc_map_hdr(buf: ptr<mut u8>, cap: u64, pos: ptr<mut u64>, count: u64) -> i32
fn flux_enc_schema_hdr(buf: ptr<mut u8>, cap: u64, pos: ptr<mut u64>, schema_id: u64) -> i32
```

`flux_enc_i64` automatically selects the smallest encoding that fits the value (u8 through i64). A value of 0 encodes as 2 bytes; a value of 1000 encodes as 3 bytes.

`flux_enc_list_hdr` and `flux_enc_map_hdr` write the container header only. The caller writes the elements immediately after.

### Decoder

```
fn flux_dec(buf: ptr<u8>, len: u64, pos: ptr<mut u64>, out: ptr<mut FluxVal>) -> i32
```
Decode one value from `buf` starting at `*pos`. Advances `*pos` past the consumed bytes. Writes result into `*out`. Call repeatedly to decode a sequence.

### Varint Primitives

The varint encoding is unsigned LEB128 — each byte contributes 7 bits; the high bit signals continuation.

```
fn flux_write_varint(buf: ptr<mut u8>, cap: u64, pos: ptr<mut u64>, n: u64) -> i32
fn flux_read_varint(buf: ptr<u8>, len: u64, pos: ptr<mut u64>, out: ptr<mut u64>) -> i32
```

### Common Patterns

```
// Encode a small map {name: "Alice", score: 42}
let buf: ptr<mut u8> = malloc(256)
let mut pos: u64 = 0
flux_enc_map_hdr(buf, 256, &pos, 2)
flux_enc_str(buf, 256, &pos, "name")
flux_enc_str(buf, 256, &pos, "Alice")
flux_enc_str(buf, 256, &pos, "score")
flux_enc_i64(buf, 256, &pos, 42)
// pos now holds the encoded byte count

// Decode a single value
let fv: ptr<mut FluxVal> = alloc<FluxVal>()
mem_zero(fv as ptr<mut u8>, 56)
let mut rpos: u64 = 0
flux_dec(buf, pos, &rpos, fv)
if (*fv).tag == flux_tag_str() {
    // (*fv).str_ptr points into buf; str_len is the byte count
}
free(fv)
free(buf)
```

---

## net

**File:** `std/net.vex`  
**Imports:** `mem.vex`, `str.vex`

TCP/IP socket primitives for IPv4 on Linux and macOS. This module exposes the raw socket API plus two convenience wrappers for listen/accept and send.

### Data Structures

```
struct SockAddrIn {
    sin_family: u16,   // AF_INET = 2
    sin_port:   u16,   // big-endian; set with htons()
    sin_addr:   u32,   // IPv4 address; 0 = INADDR_ANY
    sin_zero:   u64,   // padding — keep zeroed
}
```

This struct is 16 bytes with no padding and matches `struct sockaddr_in` on Linux and macOS.

### Low-Level Externs

```
fn socket(domain: i32, type_: i32, proto: i32) -> i32
fn bind(sockfd: i32, addr: ptr<u8>, addrlen: u32) -> i32
fn listen(sockfd: i32, backlog: i32) -> i32
fn accept(sockfd: i32, addr: ptr<mut u8>, addrlen: ptr<mut u32>) -> i32
fn connect(sockfd: i32, addr: ptr<u8>, addrlen: u32) -> i32
fn close(fd: i32) -> i32
fn shutdown(sockfd: i32, how: i32) -> i32
fn send(sockfd: i32, buf: ptr<u8>, len: u64, flags: i32) -> i64
fn recv(sockfd: i32, buf: ptr<mut u8>, len: u64, flags: i32) -> i64
fn setsockopt(sockfd: i32, level: i32, optname: i32, optval: ptr<u8>, optlen: u32) -> i32
fn htons(n: u16) -> u16
fn htonl(n: u32) -> u32
fn ntohs(n: u16) -> u16
fn ntohl(n: u32) -> u32
fn fdopen(fd: i32, mode: str) -> ptr<mut u8>
fn fgets(buf: ptr<mut u8>, size: i32, fp: ptr<mut u8>) -> ptr<mut u8>
```

### Convenience Wrappers

```
fn net_tcp_listen(port: u16) -> i32
```
Create a TCP socket, bind it to all interfaces on `port`, and set it listening with backlog 128. Sets `SO_REUSEADDR` so the port is immediately reusable after restart. Returns a server file descriptor ≥ 0 on success, or -1 on failure.

```
fn net_tcp_accept(server_fd: i32) -> i32
```
Accept one incoming connection from a listening socket. Blocks until a client connects. Returns a client file descriptor ≥ 0 on success, or -1 on failure.

```
fn net_send_str(fd: i32, s: str) -> i64
```
Send a null-terminated string. Returns bytes sent, or -1 on error.

```
fn net_send_bytes(fd: i32, buf: ptr<u8>, len: u64) -> i64
```
Send `len` bytes from `buf`. Returns bytes sent, or -1 on error.

### Common Patterns

```
// Minimal TCP echo server
let sfd: i32 = net_tcp_listen(7771)
if sfd < 0 { println("listen failed"); return 1 }

while true {
    let cfd: i32 = net_tcp_accept(sfd)
    let buf: ptr<mut u8> = malloc(4096)
    let n: i64 = recv(cfd, buf, 4096, 0)
    if n > 0 {
        send(cfd, buf as ptr<u8>, n as u64, 0)
    }
    free(buf)
    close(cfd)
}

// Connect as a client
let fd: i32 = socket(2, 1, 0)
let addr: ptr<mut SockAddrIn> = alloc<SockAddrIn>()
mem_zero(addr as ptr<mut u8>, 16)
(*addr).sin_family = 2
(*addr).sin_port   = htons(7771)
(*addr).sin_addr   = 0x0100007f   // 127.0.0.1 in network byte order
connect(fd, addr as ptr<u8>, 16)
net_send_str(fd, "hello\n")
free(addr)
close(fd)

// Line-by-line reading with fdopen + fgets (from std/io.vex)
let fp: ptr<mut u8> = fdopen(cfd, "r")
let line: ptr<mut u8> = malloc(256)
while fgets(line, 256, fp) != nil {
    // process line
}
free(line)
fclose(fp)
```

> **Note:** `net.vex` does not include `unistd.h` directly — `close`, `send`, and `recv` are declared as externs. The generated C is compiled with gcc which finds these in the default headers. No extra linker flags are required.
