#![allow(dead_code)]
fn buffer(n: i64) -> Vec<u8> {
    assert!((0..=1048576).contains(&n)); vec![0; n as usize]
}
fn get(b: &[u8], i: i64) -> i64 { b[usize::try_from(i).unwrap()] as i64 }
fn set(b: &mut [u8], i: i64, v: i64) {
    b[usize::try_from(i).unwrap()] = u8::try_from(v).unwrap();
}
fn kernel(n: i64, seed: i64) -> i64 {
    let mut text = buffer(16384); let mut i = 0;
    while i < 16384 { set(&mut text, i, (i * 37 + seed) % 95 + 32); i += 1; }
    let mut total = 0; let mut repeat = 0;
    while repeat < n {
        set(&mut text, repeat % 16384, (repeat + seed) % 95 + 32);
        let mut count = 0; i = 0;
        while i < 16384 {
            let c = get(&text, i);
            if c >= 48 && c <= 57 { count += 1; }
            if c >= 65 && c <= 90 { count += 2; }
            if c == 32 { count += 3; }
            i += 1;
        }
        total = (total + count) % 1000000007; repeat += 1;
    }
    total
}
fn main() {
    let a: Vec<String> = std::env::args().collect();
    let n: i64 = a[1].parse().unwrap();
    let seed: i64 = a[2].parse().unwrap();
    println!("{}", kernel(n, seed));
}
