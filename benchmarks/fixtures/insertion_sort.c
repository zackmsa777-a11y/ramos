#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <inttypes.h>
static int64_t add(int64_t a, int64_t b) {
    int64_t r; if (__builtin_add_overflow(a, b, &r)) abort(); return r;
}
static int64_t sub(int64_t a, int64_t b) {
    int64_t r; if (__builtin_sub_overflow(a, b, &r)) abort(); return r;
}
static int64_t mul(int64_t a, int64_t b) {
    int64_t r; if (__builtin_mul_overflow(a, b, &r)) abort(); return r;
}
typedef struct { uint8_t *data; int64_t len; } Buf;
static Buf buffer(int64_t n) {
    if (n < 0 || n > 1048576) abort();
    Buf b = {calloc((size_t)n, 1), n}; if (!b.data && n) abort(); return b;
}
static int64_t get(Buf b, int64_t i) {
    if (i < 0 || i >= b.len) abort(); return b.data[i];
}
static void set(Buf b, int64_t i, int64_t v) {
    if (i < 0 || i >= b.len || v < 0 || v > 255) abort(); b.data[i] = (uint8_t)v;
}
static int64_t kernel(int64_t n, int64_t seed) {
    Buf b = buffer(128); int64_t total = 0, repeat = 0;
    while (repeat < n) {
        int64_t i = 0;
        while (i < 128) { set(b, i, add(add(mul(i, 73), seed), repeat) % 256); i = add(i, 1); }
        i = 1;
        while (i < 128) {
            int64_t v = get(b, i), j = i;
            while (j > 0) {
                int64_t prev = get(b, sub(j, 1));
                if (prev <= v) break; set(b, j, prev); j = sub(j, 1);
            }
            set(b, j, v); i = add(i, 1);
        }
        i = 0;
        while (i < 128) { total = add(total, mul(get(b, i), add(i, 1))) % 1000000007; i = add(i, 1); }
        repeat = add(repeat, 1);
    }
    free(b.data); return total;
}
int main(int argc, char **argv) {
    if (argc != 3) return 2;
    printf("%" PRId64 "\n", kernel(strtoll(argv[1], NULL, 10), strtoll(argv[2], NULL, 10)));
    return 0;
}
