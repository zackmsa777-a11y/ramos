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
    Buf a = buffer(256), b = buffer(256), out = buffer(256); int64_t i = 0;
    while (i < 256) {
        set(a, i, add(mul(i, 17), seed) % 256); set(b, i, add(mul(i, 29), seed) % 256); i = add(i, 1);
    }
    int64_t total = 0, repeat = 0;
    while (repeat < n) {
        set(a, repeat % 256, add(repeat, seed) % 256);
        int64_t row = 0;
        while (row < 16) {
            int64_t col = 0;
            while (col < 16) {
                int64_t sum = 0, k = 0;
                while (k < 16) {
                    sum = add(sum, mul(get(a, add(mul(row, 16), k)), get(b, add(mul(k, 16), col)))); k = add(k, 1);
                }
                set(out, add(mul(row, 16), col), sum % 256); col = add(col, 1);
            }
            row = add(row, 1);
        }
        i = 0;
        while (i < 256) { total = add(total, mul(get(out, i), add(i, 1))) % 1000000007; i = add(i, 1); }
        repeat = add(repeat, 1);
    }
    free(a.data); free(b.data); free(out.data); return total;
}
int main(int argc, char **argv) {
    if (argc != 3) return 2;
    printf("%" PRId64 "\n", kernel(strtoll(argv[1], NULL, 10), strtoll(argv[2], NULL, 10)));
    return 0;
}
