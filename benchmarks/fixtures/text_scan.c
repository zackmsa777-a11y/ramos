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
    Buf text = buffer(16384); int64_t i = 0;
    while (i < 16384) { set(text, i, add(add(mul(i, 37), seed) % 95, 32)); i = add(i, 1); }
    int64_t total = 0, repeat = 0;
    while (repeat < n) {
        set(text, repeat % 16384, add(add(repeat, seed) % 95, 32));
        int64_t count = 0; i = 0;
        while (i < 16384) {
            int64_t c = get(text, i);
            if (c >= 48 && c <= 57) count = add(count, 1);
            if (c >= 65 && c <= 90) count = add(count, 2);
            if (c == 32) count = add(count, 3);
            i = add(i, 1);
        }
        total = add(total, count) % 1000000007; repeat = add(repeat, 1);
    }
    free(text.data); return total;
}
int main(int argc, char **argv) {
    if (argc != 3) return 2;
    printf("%" PRId64 "\n", kernel(strtoll(argv[1], NULL, 10), strtoll(argv[2], NULL, 10)));
    return 0;
}
