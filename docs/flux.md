# Flux Format Reference

Flux is a binary serialization format designed for maximum encode/decode throughput and minimum wire size. It is a drop-in replacement for JSON in contexts where human readability is not required.

---

## Why Flux

| Concern | JSON | Flux |
|---|---|---|
| Encoding | Text (UTF-8) | Binary |
| Integer `123456789` | 9 bytes | 5 bytes (tag + u32) |
| Float `9999.5` | 6 bytes | 5 bytes (tag + f32) |
| String `"Alice"` | 7 bytes | 7 bytes (tag + varint-len + bytes) |
| Bool `true` | 4 bytes | 1 byte |
| `null` | 4 bytes | 1 byte |
| Field names | Stored in full every time | Optional (schema mode: zero bytes) |
| Parse step | Requires text → number conversion | memcpy directly into typed fields |
| C decode speed | N/A | ~100M records/sec (schema mode) |

---

## Wire Format

Every value starts with a 1-byte **type tag**, followed by optional payload.

### Type tags

| Tag | Hex | Payload |
|---|---|---|
| `NULL` | `0x00` | none |
| `FALSE` | `0x01` | none |
| `TRUE` | `0x02` | none |
| `INT8` | `0x03` | 1 byte, signed |
| `INT16` | `0x04` | 2 bytes LE, signed |
| `INT32` | `0x05` | 4 bytes LE, signed |
| `INT64` | `0x06` | 8 bytes LE, signed |
| `UINT8` | `0x07` | 1 byte, unsigned |
| `UINT16` | `0x08` | 2 bytes LE, unsigned |
| `UINT32` | `0x09` | 4 bytes LE, unsigned |
| `UINT64` | `0x0A` | 8 bytes LE, unsigned |
| `FLOAT32` | `0x0B` | 4 bytes LE, IEEE 754 |
| `FLOAT64` | `0x0C` | 8 bytes LE, IEEE 754 |
| `BYTES` | `0x0D` | varint(len) + raw bytes |
| `STR` | `0x0E` | varint(len) + UTF-8 bytes |
| `LIST` | `0x0F` | varint(count) + *count* values |
| `MAP` | `0x10` | varint(count) + *count* (key, value) pairs |
| `SCHEMA` | `0x11` | varint(schema_id) + values in field order |

### Varint encoding

Integers used for lengths and counts use **unsigned LEB128** (same as WebAssembly, protobuf):

- Values 0–127 encode in 1 byte.
- Values 128–16383 encode in 2 bytes.
- Each byte contributes 7 bits; the high bit signals "more bytes follow."

```
0x00        → 0
0x01        → 1
0x7F        → 127
0x80 0x01   → 128
0xFF 0x7F   → 16383
```

### Integer auto-sizing

When encoding an integer, Flux picks the smallest type that fits the value:

- `0–255` → `UINT8` (2 bytes total)
- `-128–-1` → `INT8` (2 bytes total)
- `256–65535` → `UINT16` (3 bytes total)
- etc.

This is automatic on encode; on decode any integer tag is accepted.

### Float auto-sizing

If a `float64` value can be represented exactly as `float32`, it is stored as `FLOAT32` (5 bytes instead of 9). On decode, `FLOAT32` is widened to `float64` transparently.

---

## Python API

```python
from flux.flux import encode, decode, Schema
```

### encode / decode

```python
import flux.flux as flux

data = {
    "user_id": 123456789,
    "name": "Alice",
    "score": 9999.5,
    "active": True,
    "tags": ["fast", "binary"],
    "meta": {"level": 42},
}

blob = flux.encode(data)   # → bytes
back = flux.decode(blob)   # → dict identical to data
```

Any Python value composed of `None`, `bool`, `int`, `float`, `bytes`, `str`, `list`, `tuple`, and `dict` is encodable. Keys must be strings or ints.

### Schema mode

When all records share the same structure, use a `Schema` to strip field names from the wire entirely.

```python
from flux.flux import Schema

# Define once, globally. Field order is fixed.
USER = Schema(["user_id", "name", "score", "active"])

record = {"user_id": 1, "name": "Bob", "score": 99.0, "active": True}

blob = USER.encode(record)      # 20 bytes instead of ~70
back = Schema.decode(blob)      # → {"user_id": 1, "name": "Bob", ...}
```

The schema is registered globally by ID at construction time. Both encoder and decoder must share the same `Schema` objects (same order, same IDs). In a client/server system, schemas are agreed on at startup or versioned in a handshake.

---

## C API

Include `flux/flux.h` and compile `flux/flux.c` alongside your program.

```c
#include "flux/flux.h"
```

### Encoding

All encode functions write into a caller-supplied buffer and advance `*pos`. They return `FLUX_OK` (0) or an error code if the buffer is too small.

```c
uint8_t buf[512];
size_t pos = 0;

// Write a map with 3 fields
flux_encode_map_header(buf, sizeof(buf), &pos, 3);

flux_encode_str(buf, sizeof(buf), &pos, "id", 2);
flux_encode_int64(buf, sizeof(buf), &pos, 42LL);

flux_encode_str(buf, sizeof(buf), &pos, "name", 4);
flux_encode_str(buf, sizeof(buf), &pos, "Alice", 5);

flux_encode_str(buf, sizeof(buf), &pos, "score", 5);
flux_encode_double(buf, sizeof(buf), &pos, 9999.5);

// buf[0..pos] is the encoded message
```

#### Encode functions

```c
int flux_encode_null   (uint8_t *buf, size_t cap, size_t *pos);
int flux_encode_bool   (uint8_t *buf, size_t cap, size_t *pos, int v);
int flux_encode_int64  (uint8_t *buf, size_t cap, size_t *pos, int64_t v);
int flux_encode_double (uint8_t *buf, size_t cap, size_t *pos, double v);
int flux_encode_bytes  (uint8_t *buf, size_t cap, size_t *pos,
                        const uint8_t *data, size_t len);
int flux_encode_str    (uint8_t *buf, size_t cap, size_t *pos,
                        const char *s, size_t len);
int flux_encode_list_header(uint8_t *buf, size_t cap, size_t *pos, size_t count);
int flux_encode_map_header (uint8_t *buf, size_t cap, size_t *pos, size_t count);
```

`flux_encode_int64` picks the smallest integer tag automatically. `flux_encode_double` uses `FLOAT32` when lossless.

### Decoding

```c
FluxValue val;
size_t pos = 0;

flux_decode(buf, len, &pos, &val);

if (val.tag == FLUX_TAG_MAP) {
    size_t count = val.v.count;
    for (size_t i = 0; i < count; i++) {
        FluxValue key, value;
        flux_decode(buf, len, &pos, &key);    // key (usually STR)
        flux_decode(buf, len, &pos, &value);  // value
        // key.v.str.ptr / key.v.str.len
        // value.tag, value.v.i64, value.v.f64, etc.
    }
}
```

#### FluxValue

```c
typedef struct {
    uint8_t tag;
    union {
        int64_t  i64;    // INT8/16/32/64
        uint64_t u64;    // UINT8/16/32/64, FALSE/TRUE
        double   f64;    // FLOAT32/64
        struct {
            const char *ptr;  // points into original buffer (zero-copy)
            size_t      len;
        } str;            // STR or BYTES
        size_t count;     // LIST or MAP — number of elements/pairs
    } v;
} FluxValue;
```

String and bytes values point **directly into the source buffer** — no allocation, no copy. The pointer is valid as long as the source buffer is alive.

#### Error codes

```c
FLUX_OK            // 0 — success
FLUX_ERR_OVERFLOW  // 1 — buffer too small to encode
FLUX_ERR_TRUNCATED // 2 — buffer ended mid-value
FLUX_ERR_BADTAG    // 3 — unknown type tag
```

---

## Schema Mode Wire Layout

```
SCHEMA_TAG (0x11)
varint(schema_id)
value_0
value_1
...
value_N
```

No keys. No field count. Just the tag, the schema ID (usually 1 byte for IDs < 128), and the values in the order the schema defines them. A 4-field record with small integers and a short string can fit in 15–25 bytes.

---

## Size Comparison

Encoding `{"user_id": 123456789, "name": "Alice", "score": 9999.5, "active": true}`:

| Format | Bytes |
|---|---|
| JSON | 72 |
| Flux (self-describing) | 50 |
| Flux (schema) | 20 |

---

## Performance (C, 10 million iterations, -O3)

| Operation | Throughput | Latency |
|---|---|---|
| Self-describing encode | 37.7 M/s | 26.5 ns |
| Self-describing decode | 47.8 M/s | 20.9 ns |
| Schema encode | 97.1 M/s | 10.3 ns |
| Schema decode | 106.7 M/s | 9.4 ns |

---

## Comparison with Similar Formats

| | JSON | MessagePack | Protobuf | Flux |
|---|---|---|---|---|
| Self-describing | Yes | Yes | No | Yes |
| Schema mode | No | No | Yes | Yes |
| Binary | No | Yes | Yes | Yes |
| Zero-copy decode | No | No | No | Yes (C API) |
| Integer auto-sizing | No | Yes | Varint only | Yes |
| Float auto-sizing | No | No | No | Yes |
| Endianness | N/A | Big | N/A | Little |
| Implementation | Everywhere | Many | Google | This repo |

---

## Gotchas

**Schema IDs are process-global.** `Schema` objects are numbered sequentially from 0 in the order they are constructed. If the sender and receiver construct schemas in different orders, schema IDs will mismatch and decoding will read wrong fields. Establish a canonical schema initialization order and stick to it.

**String pointers in C are non-owning.** `val.v.str.ptr` points into your input buffer. If you free or reuse the buffer, the pointer dangles. Copy the string if you need it to outlive the buffer.

**Flux does not include a message length prefix.** When streaming multiple messages over a socket or file, prefix each message with its byte length (e.g. a 4-byte or varint length) so the reader knows where one message ends and the next begins.
