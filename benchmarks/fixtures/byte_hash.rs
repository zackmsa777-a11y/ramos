#![allow(dead_code)]
fn buffer(n: i64) -> Vec<u8> {
    assert!((0..=1048576).contains(&n)); vec![0; n as usize]
}
fn get(b: &[u8], i: i64) -> i64 { b[usize::try_from(i).unwrap()] as i64 }
fn set(b: &mut [u8], i: i64, v: i64) {
    b[usize::try_from(i).unwrap()] = u8::try_from(v).unwrap();
}
fn kernel(n: i64, seed: i64) -> i64 {
    let mut b = buffer(4096); let mut i = 0;
    while i < 4096 { set(&mut b, i, (i * 17 + seed) % 256); i += 1; }
    let mut h = seed; i = 0;
    while i < n { h = (h * 33 + get(&b, i % 4096)) % 1000000007; i += 1; }
    h
}
fn main() {
    let a: Vec<String> = std::env::args().collect();
    let n: i64 = a[1].parse().unwrap();
    let seed: i64 = a[2].parse().unwrap();
    println!("{}", kernel(n, seed));
}
