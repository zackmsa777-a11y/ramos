import sys

def kernel(n, seed):
    b = bytearray(4096)
    i = 0
    while i < 4096:
        b[i] = (i * 17 + seed) % 256
        i += 1
    h, i = seed, 0
    while i < n:
        h = (h * 33 + b[i % 4096]) % 1000000007
        i += 1
    return h

if __name__ == "__main__":
    print(kernel(int(sys.argv[1]), int(sys.argv[2])))
