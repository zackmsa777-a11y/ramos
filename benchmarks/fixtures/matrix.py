import sys

def kernel(n, seed):
    a, b, out = bytearray(256), bytearray(256), bytearray(256)
    i = 0
    while i < 256:
        a[i] = (i * 17 + seed) % 256
        b[i] = (i * 29 + seed) % 256
        i += 1
    total, repeat = 0, 0
    while repeat < n:
        a[repeat % 256] = (repeat + seed) % 256
        row = 0
        while row < 16:
            col = 0
            while col < 16:
                value, k = 0, 0
                while k < 16:
                    value += a[row * 16 + k] * b[k * 16 + col]
                    k += 1
                out[row * 16 + col] = value % 256
                col += 1
            row += 1
        i = 0
        while i < 256:
            total = (total + out[i] * (i + 1)) % 1000000007
            i += 1
        repeat += 1
    return total

if __name__ == "__main__":
    print(kernel(int(sys.argv[1]), int(sys.argv[2])))
