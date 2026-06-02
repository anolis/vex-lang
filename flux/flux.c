/*
 * Flux: C implementation of the binary serialization format.
 * Zero-allocation decode via cursor into caller-owned buffer.
 */
#include "flux.h"
#include <string.h>
#include <math.h>

/* ---- varint ---- */

static int flux_write_varint(uint8_t *buf, size_t cap, size_t *pos, uint64_t n) {
    do {
        if (*pos >= cap) return FLUX_ERR_OVERFLOW;
        uint8_t b = n & 0x7F;
        n >>= 7;
        buf[(*pos)++] = n ? (b | 0x80) : b;
    } while (n);
    return FLUX_OK;
}

static int flux_read_varint(const uint8_t *buf, size_t len, size_t *pos, uint64_t *out) {
    uint64_t result = 0;
    int shift = 0;
    while (*pos < len) {
        uint8_t b = buf[(*pos)++];
        result |= (uint64_t)(b & 0x7F) << shift;
        if (!(b & 0x80)) { *out = result; return FLUX_OK; }
        shift += 7;
        if (shift >= 64) return FLUX_ERR_OVERFLOW;
    }
    return FLUX_ERR_TRUNCATED;
}

/* ---- encode ---- */

int flux_encode_null(uint8_t *buf, size_t cap, size_t *pos) {
    if (*pos >= cap) return FLUX_ERR_OVERFLOW;
    buf[(*pos)++] = FLUX_TAG_NULL;
    return FLUX_OK;
}

int flux_encode_bool(uint8_t *buf, size_t cap, size_t *pos, int v) {
    if (*pos >= cap) return FLUX_ERR_OVERFLOW;
    buf[(*pos)++] = v ? FLUX_TAG_TRUE : FLUX_TAG_FALSE;
    return FLUX_OK;
}

int flux_encode_int64(uint8_t *buf, size_t cap, size_t *pos, int64_t v) {
    if (*pos + 9 > cap) return FLUX_ERR_OVERFLOW;
    if (v >= 0 && v <= 255) {
        buf[(*pos)++] = FLUX_TAG_UINT8;
        buf[(*pos)++] = (uint8_t)v;
    } else if (v >= -128 && v < 0) {
        buf[(*pos)++] = FLUX_TAG_INT8;
        buf[(*pos)++] = (uint8_t)(int8_t)v;
    } else if (v >= 0 && v <= 65535) {
        buf[(*pos)++] = FLUX_TAG_UINT16;
        uint16_t u = (uint16_t)v;
        memcpy(buf + *pos, &u, 2); *pos += 2;
    } else if (v >= -32768 && v < 0) {
        buf[(*pos)++] = FLUX_TAG_INT16;
        int16_t u = (int16_t)v;
        memcpy(buf + *pos, &u, 2); *pos += 2;
    } else if (v >= 0 && v <= (int64_t)0xFFFFFFFF) {
        buf[(*pos)++] = FLUX_TAG_UINT32;
        uint32_t u = (uint32_t)v;
        memcpy(buf + *pos, &u, 4); *pos += 4;
    } else if (v >= -2147483648LL && v < 0) {
        buf[(*pos)++] = FLUX_TAG_INT32;
        int32_t u = (int32_t)v;
        memcpy(buf + *pos, &u, 4); *pos += 4;
    } else {
        buf[(*pos)++] = FLUX_TAG_INT64;
        memcpy(buf + *pos, &v, 8); *pos += 8;
    }
    return FLUX_OK;
}

int flux_encode_double(uint8_t *buf, size_t cap, size_t *pos, double v) {
    if (*pos + 9 > cap) return FLUX_ERR_OVERFLOW;
    float f = (float)v;
    if ((double)f == v) {
        buf[(*pos)++] = FLUX_TAG_F32;
        memcpy(buf + *pos, &f, 4); *pos += 4;
    } else {
        buf[(*pos)++] = FLUX_TAG_F64;
        memcpy(buf + *pos, &v, 8); *pos += 8;
    }
    return FLUX_OK;
}

int flux_encode_bytes(uint8_t *buf, size_t cap, size_t *pos,
                      const uint8_t *data, size_t len) {
    if (*pos >= cap) return FLUX_ERR_OVERFLOW;
    buf[(*pos)++] = FLUX_TAG_BYTES;
    int r = flux_write_varint(buf, cap, pos, (uint64_t)len);
    if (r) return r;
    if (*pos + len > cap) return FLUX_ERR_OVERFLOW;
    memcpy(buf + *pos, data, len);
    *pos += len;
    return FLUX_OK;
}

int flux_encode_str(uint8_t *buf, size_t cap, size_t *pos,
                    const char *s, size_t len) {
    if (*pos >= cap) return FLUX_ERR_OVERFLOW;
    buf[(*pos)++] = FLUX_TAG_STR;
    int r = flux_write_varint(buf, cap, pos, (uint64_t)len);
    if (r) return r;
    if (*pos + len > cap) return FLUX_ERR_OVERFLOW;
    memcpy(buf + *pos, s, len);
    *pos += len;
    return FLUX_OK;
}

int flux_encode_list_header(uint8_t *buf, size_t cap, size_t *pos, size_t count) {
    if (*pos >= cap) return FLUX_ERR_OVERFLOW;
    buf[(*pos)++] = FLUX_TAG_LIST;
    return flux_write_varint(buf, cap, pos, (uint64_t)count);
}

int flux_encode_map_header(uint8_t *buf, size_t cap, size_t *pos, size_t count) {
    if (*pos >= cap) return FLUX_ERR_OVERFLOW;
    buf[(*pos)++] = FLUX_TAG_MAP;
    return flux_write_varint(buf, cap, pos, (uint64_t)count);
}

/* ---- decode ---- */

int flux_decode(const uint8_t *buf, size_t len, size_t *pos, FluxValue *out) {
    if (*pos >= len) return FLUX_ERR_TRUNCATED;
    uint8_t tag = buf[(*pos)++];
    out->tag = tag;

    switch (tag) {
        case FLUX_TAG_NULL:  return FLUX_OK;
        case FLUX_TAG_FALSE: out->v.u64 = 0; return FLUX_OK;
        case FLUX_TAG_TRUE:  out->v.u64 = 1; return FLUX_OK;

        case FLUX_TAG_INT8:
            if (*pos + 1 > len) return FLUX_ERR_TRUNCATED;
            out->v.i64 = (int8_t)buf[(*pos)++];
            return FLUX_OK;
        case FLUX_TAG_INT16:
            if (*pos + 2 > len) return FLUX_ERR_TRUNCATED;
            { int16_t x; memcpy(&x, buf+*pos, 2); out->v.i64 = x; *pos += 2; }
            return FLUX_OK;
        case FLUX_TAG_INT32:
            if (*pos + 4 > len) return FLUX_ERR_TRUNCATED;
            { int32_t x; memcpy(&x, buf+*pos, 4); out->v.i64 = x; *pos += 4; }
            return FLUX_OK;
        case FLUX_TAG_INT64:
            if (*pos + 8 > len) return FLUX_ERR_TRUNCATED;
            memcpy(&out->v.i64, buf+*pos, 8); *pos += 8;
            return FLUX_OK;

        case FLUX_TAG_UINT8:
            if (*pos + 1 > len) return FLUX_ERR_TRUNCATED;
            out->v.u64 = buf[(*pos)++];
            return FLUX_OK;
        case FLUX_TAG_UINT16:
            if (*pos + 2 > len) return FLUX_ERR_TRUNCATED;
            { uint16_t x; memcpy(&x, buf+*pos, 2); out->v.u64 = x; *pos += 2; }
            return FLUX_OK;
        case FLUX_TAG_UINT32:
            if (*pos + 4 > len) return FLUX_ERR_TRUNCATED;
            { uint32_t x; memcpy(&x, buf+*pos, 4); out->v.u64 = x; *pos += 4; }
            return FLUX_OK;
        case FLUX_TAG_UINT64:
            if (*pos + 8 > len) return FLUX_ERR_TRUNCATED;
            memcpy(&out->v.u64, buf+*pos, 8); *pos += 8;
            return FLUX_OK;

        case FLUX_TAG_F32:
            if (*pos + 4 > len) return FLUX_ERR_TRUNCATED;
            { float x; memcpy(&x, buf+*pos, 4); out->v.f64 = x; *pos += 4; }
            return FLUX_OK;
        case FLUX_TAG_F64:
            if (*pos + 8 > len) return FLUX_ERR_TRUNCATED;
            memcpy(&out->v.f64, buf+*pos, 8); *pos += 8;
            return FLUX_OK;

        case FLUX_TAG_BYTES:
        case FLUX_TAG_STR: {
            uint64_t slen;
            int r = flux_read_varint(buf, len, pos, &slen);
            if (r) return r;
            if (*pos + slen > len) return FLUX_ERR_TRUNCATED;
            out->v.str.ptr = (const char *)(buf + *pos);
            out->v.str.len = (size_t)slen;
            *pos += slen;
            return FLUX_OK;
        }

        case FLUX_TAG_LIST:
        case FLUX_TAG_MAP: {
            uint64_t count;
            int r = flux_read_varint(buf, len, pos, &count);
            if (r) return r;
            out->v.count = (size_t)count;
            return FLUX_OK;
        }

        default:
            return FLUX_ERR_BADTAG;
    }
}
