#!/usr/bin/env python3
"""Benchmark Flux vs JSON vs msgpack."""
import sys, os, time, json
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from flux.flux import encode, decode, Schema

try:
    import msgpack
    HAS_MSGPACK = True
except ImportError:
    HAS_MSGPACK = False

ITERS = 100_000

DATA = {
    "user_id": 123456789,
    "name": "Alice",
    "score": 9999.5,
    "active": True,
    "tags": ["fast", "efficient", "binary"],
    "metadata": {"level": 42, "region": "us-east"},
}

DATA_LIST = [
    {"id": i, "value": i * 3.14, "label": f"item_{i}", "ok": i % 2 == 0}
    for i in range(100)
]


def bench(name, enc_fn, dec_fn, data, iters=ITERS):
    # warmup
    for _ in range(100):
        enc_fn(data)
    blob = enc_fn(data)
    for _ in range(100):
        dec_fn(blob)

    t0 = time.perf_counter()
    for _ in range(iters):
        enc_fn(data)
    enc_time = time.perf_counter() - t0

    t0 = time.perf_counter()
    for _ in range(iters):
        dec_fn(blob)
    dec_time = time.perf_counter() - t0

    size = len(blob)
    print(f"{name:20s}  size={size:5d}B  enc={enc_time*1e6/iters:6.2f}µs  dec={dec_time*1e6/iters:6.2f}µs")
    return blob


print(f"\n=== Single object ({ITERS:,} iterations) ===")
bench("JSON",  lambda d: json.dumps(d).encode(), lambda b: json.loads(b), DATA)
bench("Flux",  encode, decode, DATA)
if HAS_MSGPACK:
    bench("msgpack", msgpack.packb, msgpack.unpackb, DATA)

print(f"\n=== 100-item list ({ITERS:,} iterations) ===")
bench("JSON",  lambda d: json.dumps(d).encode(), lambda b: json.loads(b), DATA_LIST)
bench("Flux",  encode, decode, DATA_LIST)
if HAS_MSGPACK:
    bench("msgpack", msgpack.packb, msgpack.unpackb, DATA_LIST)

# Schema mode
USER_SCHEMA = Schema(["user_id", "name", "score", "active"])
schema_data = {"user_id": 123456789, "name": "Alice", "score": 9999.5, "active": True}
schema_blob = USER_SCHEMA.encode(schema_data)

print(f"\n=== Schema-aware record ({ITERS:,} iterations) ===")
print(f"  Flux (schema) size = {len(schema_blob)}B  (vs JSON={len(json.dumps(schema_data).encode())}B)")

t0 = time.perf_counter()
for _ in range(ITERS):
    USER_SCHEMA.encode(schema_data)
enc_time = time.perf_counter() - t0

t0 = time.perf_counter()
for _ in range(ITERS):
    Schema.decode(schema_blob)
dec_time = time.perf_counter() - t0

print(f"{'Flux (schema)':20s}  size={len(schema_blob):5d}B  enc={enc_time*1e6/ITERS:6.2f}µs  dec={dec_time*1e6/ITERS:6.2f}µs")

if not HAS_MSGPACK:
    print("\n(install msgpack for comparison: pip install msgpack)")
