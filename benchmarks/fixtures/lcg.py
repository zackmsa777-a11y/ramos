import sys

def kernel(n, seed):
    x = seed
    i = 0
    while i < n:
        x = (x * 1664525 + 1013904223) % 2147483647
        i += 1
    return x

if __name__ == "__main__":
    print(kernel(int(sys.argv[1]), int(sys.argv[2])))
