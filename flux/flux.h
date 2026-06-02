#pragma once
#include <stdint.h>
#include <stddef.h>

/* Type tags */
#define FLUX_TAG_NULL   0x00
#define FLUX_TAG_FALSE  0x01
#define FLUX_TAG_TRUE   0x02
#define FLUX_TAG_INT8   0x03
#define FLUX_TAG_INT16  0x04
#define FLUX_TAG_INT32  0x05
#define FLUX_TAG_INT64  0x06
#define FLUX_TAG_UINT8  0x07
#define FLUX_TAG_UINT16 0x08
#define FLUX_TAG_UINT32 0x09
#define FLUX_TAG_UINT64 0x0A
#define FLUX_TAG_F32    0x0B
#define FLUX_TAG_F64    0x0C
#define FLUX_TAG_BYTES  0x0D
#define FLUX_TAG_STR    0x0E
#define FLUX_TAG_LIST   0x0F
#define FLUX_TAG_MAP    0x10
#define FLUX_TAG_SCHEMA 0x11

/* Error codes */
#define FLUX_OK           0
#define FLUX_ERR_OVERFLOW  1
#define FLUX_ERR_TRUNCATED 2
#define FLUX_ERR_BADTAG    3

typedef struct {
    uint8_t tag;
    union {
        int64_t  i64;
        uint64_t u64;
        double   f64;
        struct { const char *ptr; size_t len; } str;
        size_t   count;  /* for LIST/MAP: number of elements/pairs */
    } v;
} FluxValue;

/* Encode helpers — write into caller-supplied buffer, advance *pos */
int flux_encode_null(uint8_t *buf, size_t cap, size_t *pos);
int flux_encode_bool(uint8_t *buf, size_t cap, size_t *pos, int v);
int flux_encode_int64(uint8_t *buf, size_t cap, size_t *pos, int64_t v);
int flux_encode_double(uint8_t *buf, size_t cap, size_t *pos, double v);
int flux_encode_bytes(uint8_t *buf, size_t cap, size_t *pos, const uint8_t *data, size_t len);
int flux_encode_str(uint8_t *buf, size_t cap, size_t *pos, const char *s, size_t len);
int flux_encode_list_header(uint8_t *buf, size_t cap, size_t *pos, size_t count);
int flux_encode_map_header(uint8_t *buf, size_t cap, size_t *pos, size_t count);

/* Decode — fills FluxValue, advances *pos. For LIST/MAP, count is in v.count;
   caller must decode each element/pair with further calls. */
int flux_decode(const uint8_t *buf, size_t len, size_t *pos, FluxValue *out);
