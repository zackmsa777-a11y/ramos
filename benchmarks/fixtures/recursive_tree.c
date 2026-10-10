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
static int64_t tree(int64_t depth, int64_t value) {
    if (depth == 0) return value % 97;
    return add(tree(sub(depth, 1), add(mul(value, 17), 3) % 1000003), tree(sub(depth, 1), add(mul(value, 29), 5) % 1000003));
}
static int64_t kernel(int64_t n, int64_t seed) {
    int64_t total = 0, x = seed, i = 0;
    while (i < n) {
        x = mul(x, 48271) % 2147483647;
        total = add(total, tree(12, x)) % 1000000007;
        i = add(i, 1);
    }
    return total;
}

int main(int argc, char **argv) {
    if (argc != 3) return 2;
    printf("%" PRId64 "\n", kernel(strtoll(argv[1], NULL, 10), strtoll(argv[2], NULL, 10)));
    return 0;
}
