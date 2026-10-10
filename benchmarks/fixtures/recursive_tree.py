import sys

def tree(depth, value):
    if depth == 0:
        return value % 97
    return tree(depth - 1, (value * 17 + 3) % 1000003) + tree(depth - 1, (value * 29 + 5) % 1000003)

def kernel(n, seed):
    total, x, i = 0, seed, 0
    while i < n:
        x = (x * 48271) % 2147483647
        total = (total + tree(12, x)) % 1000000007
        i += 1
    return total

if __name__ == "__main__":
    print(kernel(int(sys.argv[1]), int(sys.argv[2])))
