import sys

def gcd(x, y):
    while y != 0:
        t = x % y
        x = y
        y = t
    return x

def kernel(n, seed):
    x, total, i = seed, 0, 0
    while i < n:
        x = (x * 48271) % 2147483647
        total = (total + gcd(x + 1, (i + seed) % 100000 + 1)) % 1000000007
        i += 1
    return total

if __name__ == "__main__":
    print(kernel(int(sys.argv[1]), int(sys.argv[2])))
