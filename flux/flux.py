"""
Flux: hyper-efficient binary serialization format.

Type tags (1 byte):
  0x00  NULL
  0x01  FALSE
  0x02  TRUE
  0x03  INT8    + 1 byte
  0x04  INT16   + 2 bytes LE
  0x05  INT32   + 4 bytes LE
  0x06  INT64   + 8 bytes LE
  0x07  UINT8   + 1 byte
  0x08  UINT16  + 2 bytes LE
  0x09  UINT32  + 4 bytes LE
  0x0A  UINT64  + 8 bytes LE
  0x0B  FLOAT32 + 4 bytes LE (IEEE 754)
  0x0C  FLOAT64 + 8 bytes LE (IEEE 754)
  0x0D  BYTES   + varint(len) + raw bytes
  0x0E  STR     + varint(len) + UTF-8 bytes
  0x0F  LIST    + varint(count) + items
  0x10  MAP     + varint(count) + (key, value) pairs
  0x11  SCHEMA  + schema_id(varint) + items (compact schema-aware record)

Varint: unsigned LEB128.
"""

import struct
from typing import Any

TAG_NULL    = 0x00
TAG_FALSE   = 0x01
TAG_TRUE    = 0x02
TAG_INT8    = 0x03
TAG_INT16   = 0x04
TAG_INT32   = 0x05
TAG_INT64   = 0x06
TAG_UINT8   = 0x07
TAG_UINT16  = 0x08
TAG_UINT32  = 0x09
TAG_UINT64  = 0x0A
TAG_F32     = 0x0B
TAG_F64     = 0x0C
TAG_BYTES   = 0x0D
TAG_STR     = 0x0E
TAG_LIST    = 0x0F
TAG_MAP     = 0x10
TAG_SCHEMA  = 0x11


def _encode_varint(n: int) -> bytes:
    out = []
    while True:
        b = n & 0x7F
        n >>= 7
        if n:
            out.append(b | 0x80)
        else:
            out.append(b)
            break
    return bytes(out)


def _decode_varint(buf: memoryview, pos: int) -> tuple[int, int]:
    result = 0
    shift = 0
    while True:
        b = buf[pos]
        pos += 1
        result |= (b & 0x7F) << shift
        if not (b & 0x80):
            return result, pos
        shift += 7


def encode(value: Any) -> bytes:
    out = bytearray()
    _enc(value, out)
    return bytes(out)


def _enc(value: Any, out: bytearray) -> None:
    if value is None:
        out.append(TAG_NULL)
    elif value is False:
        out.append(TAG_FALSE)
    elif value is True:
        out.append(TAG_TRUE)
    elif isinstance(value, int):
        _enc_int(value, out)
    elif isinstance(value, float):
        # prefer float32 if lossless
        f32 = struct.pack('<f', value)
        if struct.unpack('<f', f32)[0] == value:
            out.append(TAG_F32)
            out += f32
        else:
            out.append(TAG_F64)
            out += struct.pack('<d', value)
    elif isinstance(value, (bytes, bytearray)):
        out.append(TAG_BYTES)
        out += _encode_varint(len(value))
        out += value
    elif isinstance(value, str):
        b = value.encode('utf-8')
        out.append(TAG_STR)
        out += _encode_varint(len(b))
        out += b
    elif isinstance(value, (list, tuple)):
        out.append(TAG_LIST)
        out += _encode_varint(len(value))
        for item in value:
            _enc(item, out)
    elif isinstance(value, dict):
        out.append(TAG_MAP)
        out += _encode_varint(len(value))
        for k, v in value.items():
            _enc(k, out)
            _enc(v, out)
    else:
        raise TypeError(f"Flux: cannot encode {type(value)}")


def _enc_int(n: int, out: bytearray) -> None:
    if 0 <= n <= 255:
        out.append(TAG_UINT8); out.append(n)
    elif -128 <= n < 0:
        out.append(TAG_INT8); out += struct.pack('<b', n)
    elif 0 <= n <= 65535:
        out.append(TAG_UINT16); out += struct.pack('<H', n)
    elif -32768 <= n < 0:
        out.append(TAG_INT16); out += struct.pack('<h', n)
    elif 0 <= n <= 0xFFFFFFFF:
        out.append(TAG_UINT32); out += struct.pack('<I', n)
    elif -2147483648 <= n < 0:
        out.append(TAG_INT32); out += struct.pack('<i', n)
    elif 0 <= n <= 0xFFFFFFFFFFFFFFFF:
        out.append(TAG_UINT64); out += struct.pack('<Q', n)
    else:
        out.append(TAG_INT64); out += struct.pack('<q', n)


def decode(data: bytes | bytearray) -> Any:
    mv = memoryview(bytes(data))
    value, pos = _dec(mv, 0)
    return value


def _dec(buf: memoryview, pos: int) -> tuple[Any, int]:
    tag = buf[pos]; pos += 1
    if tag == TAG_NULL:    return None, pos
    if tag == TAG_FALSE:   return False, pos
    if tag == TAG_TRUE:    return True, pos
    if tag == TAG_INT8:    return struct.unpack_from('<b', buf, pos)[0], pos+1
    if tag == TAG_INT16:   return struct.unpack_from('<h', buf, pos)[0], pos+2
    if tag == TAG_INT32:   return struct.unpack_from('<i', buf, pos)[0], pos+4
    if tag == TAG_INT64:   return struct.unpack_from('<q', buf, pos)[0], pos+8
    if tag == TAG_UINT8:   return buf[pos], pos+1
    if tag == TAG_UINT16:  return struct.unpack_from('<H', buf, pos)[0], pos+2
    if tag == TAG_UINT32:  return struct.unpack_from('<I', buf, pos)[0], pos+4
    if tag == TAG_UINT64:  return struct.unpack_from('<Q', buf, pos)[0], pos+8
    if tag == TAG_F32:     return struct.unpack_from('<f', buf, pos)[0], pos+4
    if tag == TAG_F64:     return struct.unpack_from('<d', buf, pos)[0], pos+8
    if tag == TAG_BYTES:
        n, pos = _decode_varint(buf, pos)
        return bytes(buf[pos:pos+n]), pos+n
    if tag == TAG_STR:
        n, pos = _decode_varint(buf, pos)
        return bytes(buf[pos:pos+n]).decode('utf-8'), pos+n
    if tag == TAG_LIST:
        count, pos = _decode_varint(buf, pos)
        items = []
        for _ in range(count):
            v, pos = _dec(buf, pos)
            items.append(v)
        return items, pos
    if tag == TAG_MAP:
        count, pos = _decode_varint(buf, pos)
        d = {}
        for _ in range(count):
            k, pos = _dec(buf, pos)
            v, pos = _dec(buf, pos)
            d[k] = v
        return d, pos
    raise ValueError(f"Flux: unknown tag 0x{tag:02X} at pos {pos-1}")


# ---------- Schema-aware mode ----------
# Schema: ordered list of field names. On encode, only values are written in order.
# Wire: TAG_SCHEMA + varint(schema_id) + values in order (no tags for primitive-typed schemas).

class Schema:
    _registry: dict[int, 'Schema'] = {}
    _next_id = 0

    def __init__(self, fields: list[str]):
        self.fields = fields
        self.id = Schema._next_id
        Schema._next_id += 1
        Schema._registry[self.id] = self

    def encode(self, record: dict) -> bytes:
        out = bytearray()
        out.append(TAG_SCHEMA)
        out += _encode_varint(self.id)
        for f in self.fields:
            _enc(record[f], out)
        return bytes(out)

    @staticmethod
    def decode(data: bytes | bytearray) -> dict:
        buf = memoryview(bytes(data))
        assert buf[0] == TAG_SCHEMA
        schema_id, pos = _decode_varint(buf, 1)
        schema = Schema._registry[schema_id]
        result = {}
        for f in schema.fields:
            v, pos = _dec(buf, pos)
            result[f] = v
        return result
