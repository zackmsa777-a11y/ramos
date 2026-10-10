import sys

def kernel(n, seed):
    b = bytearray(128)
    total, repeat = 0, 0
    while repeat < n:
        i = 0
        while i < 128:
            b[i] = (i * 73 + seed + repeat) % 256
            i += 1
        i = 1
        while i < 128:
            v, j = b[i], i
            while j > 0:
                prev = b[j - 1]
                if prev <= v:
                    break
                b[j] = prev
                j -= 1
            b[j] = v
            i += 1
        i = 0
        while i < 128:
            total = (total + b[i] * (i + 1)) % 1000000007
            i += 1
        repeat += 1
    return total

if __name__ == "__main__":
    print(kernel(int(sys.argv[1]), int(sys.argv[2])))
