/*
 * C-level Flux encode/decode benchmark.
 * Encodes a record {user_id:123456789, score:9999.5, active:true, name:"Alice"}
 * 10 million times and decodes it back.
 */
#include <stdio.h>
#include <stdint.h>
#include <string.h>
#include <time.h>
#include "../flux/flux.h"

#define ITERS 10000000

static double now_sec(void) {
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return ts.tv_sec + ts.tv_nsec * 1e-9;
}

int main(void) {
    uint8_t buf[256];
    size_t pos, encoded_len = 0;
    double t0, t1;

    /* --- ENCODE bench --- */
    t0 = now_sec();
    for (int i = 0; i < ITERS; i++) {
        pos = 0;
        flux_encode_map_header(buf, sizeof(buf), &pos, 4);
        flux_encode_str(buf, sizeof(buf), &pos, "user_id", 7);
        flux_encode_int64(buf, sizeof(buf), &pos, 123456789LL);
        flux_encode_str(buf, sizeof(buf), &pos, "score", 5);
        flux_encode_double(buf, sizeof(buf), &pos, 9999.5);
        flux_encode_str(buf, sizeof(buf), &pos, "active", 6);
        flux_encode_bool(buf, sizeof(buf), &pos, 1);
        flux_encode_str(buf, sizeof(buf), &pos, "name", 4);
        flux_encode_str(buf, sizeof(buf), &pos, "Alice", 5);
    }
    t1 = now_sec();
    encoded_len = pos;

    printf("Flux C encode: %zu bytes  %.2f ns/iter  (%.2f M/s)\n",
           encoded_len,
           (t1 - t0) * 1e9 / ITERS,
           ITERS / (t1 - t0) / 1e6);

    /* --- DECODE bench --- */
    FluxValue val;
    t0 = now_sec();
    for (int i = 0; i < ITERS; i++) {
        size_t rpos = 0;
        flux_decode(buf, encoded_len, &rpos, &val);  /* MAP header */
        size_t count = val.v.count;
        for (size_t j = 0; j < count; j++) {
            flux_decode(buf, encoded_len, &rpos, &val); /* key */
            flux_decode(buf, encoded_len, &rpos, &val); /* value */
        }
    }
    t1 = now_sec();

    printf("Flux C decode:             %.2f ns/iter  (%.2f M/s)\n",
           (t1 - t0) * 1e9 / ITERS,
           ITERS / (t1 - t0) / 1e6);

    /* --- Schema-mode bench (just values, no keys) --- */
    t0 = now_sec();
    for (int i = 0; i < ITERS; i++) {
        pos = 0;
        buf[pos++] = FLUX_TAG_SCHEMA;
        /* schema_id = 0 as single byte varint */
        buf[pos++] = 0x00;
        flux_encode_int64(buf, sizeof(buf), &pos, 123456789LL);
        flux_encode_double(buf, sizeof(buf), &pos, 9999.5);
        flux_encode_bool(buf, sizeof(buf), &pos, 1);
        flux_encode_str(buf, sizeof(buf), &pos, "Alice", 5);
    }
    t1 = now_sec();
    size_t schema_len = pos;

    printf("Flux C schema encode: %zu bytes  %.2f ns/iter  (%.2f M/s)\n",
           schema_len,
           (t1 - t0) * 1e9 / ITERS,
           ITERS / (t1 - t0) / 1e6);

    t0 = now_sec();
    for (int i = 0; i < ITERS; i++) {
        size_t rpos = 2; /* skip tag + schema_id */
        flux_decode(buf, schema_len, &rpos, &val); /* user_id */
        flux_decode(buf, schema_len, &rpos, &val); /* score */
        flux_decode(buf, schema_len, &rpos, &val); /* active */
        flux_decode(buf, schema_len, &rpos, &val); /* name */
    }
    t1 = now_sec();

    printf("Flux C schema decode:         %.2f ns/iter  (%.2f M/s)\n",
           (t1 - t0) * 1e9 / ITERS,
           ITERS / (t1 - t0) / 1e6);

    return 0;
}
