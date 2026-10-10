#![allow(dead_code)]
fn buffer(n: i64) -> Vec<u8> {
    assert!((0..=1048576).contains(&n)); vec![0; n as usize]
}
fn get(b: &[u8], i: i64) -> i64 { b[usize::try_from(i).unwrap()] as i64 }
fn set(b: &mut [u8], i: i64, v: i64) {
    b[usize::try_from(i).unwrap()] = u8::try_from(v).unwrap();
}
fn kernel(n: i64, seed: i64) -> i64 {
    let mut x = seed; let mut i = 0;
    while i < n { x = (x * 1664525 + 1013904223) % 2147483647; i += 1; }
    x
}
fn main() {
    let a: Vec<String> = std::env::args().collect();
    let n: i64 = a[1].parse().unwrap();
    let seed: i64 = a[2].parse().unwrap();
    println!("{}", kernel(n, seed));
}
