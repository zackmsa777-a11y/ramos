import sys

def kernel(n, seed):
    text = bytearray(16384)
    i = 0
    while i < 16384:
        text[i] = (i * 37 + seed) % 95 + 32
        i += 1
    total, repeat = 0, 0
    while repeat < n:
        text[repeat % 16384] = (repeat + seed) % 95 + 32
        count, i = 0, 0
        while i < 16384:
            c = text[i]
            if 48 <= c <= 57:
                count += 1
            if 65 <= c <= 90:
                count += 2
            if c == 32:
                count += 3
            i += 1
        total = (total + count) % 1000000007
        repeat += 1
    return total

if __name__ == "__main__":
    print(kernel(int(sys.argv[1]), int(sys.argv[2])))
