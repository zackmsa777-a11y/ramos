#![allow(dead_code)]
fn buffer(n: i64) -> Vec<u8> {
    assert!((0..=1048576).contains(&n)); vec![0; n as usize]
}
fn get(b: &[u8], i: i64) -> i64 { b[usize::try_from(i).unwrap()] as i64 }
fn set(b: &mut [u8], i: i64, v: i64) {
    b[usize::try_from(i).unwrap()] = u8::try_from(v).unwrap();
}
fn tree(depth: i64, value: i64) -> i64 {
    if depth == 0 { return value % 97; }
    tree(depth - 1, (value * 17 + 3) % 1000003) + tree(depth - 1, (value * 29 + 5) % 1000003)
}
fn kernel(n: i64, seed: i64) -> i64 {
    let mut total = 0; let mut x = seed; let mut i = 0;
    while i < n {
        x = (x * 48271) % 2147483647;
        total = (total + tree(12, x)) % 1000000007;
        i += 1;
    }
    total
}

fn main() {
    let a: Vec<String> = std::env::args().collect();
    let n: i64 = a[1].parse().unwrap();
    let seed: i64 = a[2].parse().unwrap();
    println!("{}", kernel(n, seed));
}
