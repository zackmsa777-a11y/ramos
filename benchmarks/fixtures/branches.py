import sys

def kernel(n, seed):
    x, total, i = seed, 0, 0
    while i < n:
        x = (x * 48271) % 2147483647
        if x % 2 == 0:
            total = (total + x % 97) % 1000000007
        else:
            total = (total + x % 31) % 1000000007
        if x % 7 == 0:
            total = (total + 11) % 1000000007
        i += 1
    return total

if __name__ == "__main__":
    print(kernel(int(sys.argv[1]), int(sys.argv[2])))
