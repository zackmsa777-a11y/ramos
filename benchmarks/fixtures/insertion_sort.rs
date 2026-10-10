#![allow(dead_code)]
fn buffer(n: i64) -> Vec<u8> {
    assert!((0..=1048576).contains(&n)); vec![0; n as usize]
}
fn get(b: &[u8], i: i64) -> i64 { b[usize::try_from(i).unwrap()] as i64 }
fn set(b: &mut [u8], i: i64, v: i64) {
    b[usize::try_from(i).unwrap()] = u8::try_from(v).unwrap();
}
fn kernel(n: i64, seed: i64) -> i64 {
    let mut b = buffer(128); let mut total = 0; let mut repeat = 0;
    while repeat < n {
        let mut i = 0;
        while i < 128 { set(&mut b, i, (i * 73 + seed + repeat) % 256); i += 1; }
        i = 1;
        while i < 128 {
            let v = get(&b, i); let mut j = i;
            while j > 0 {
                let prev = get(&b, j - 1);
                if prev <= v { break; } set(&mut b, j, prev); j -= 1;
            }
            set(&mut b, j, v); i += 1;
        }
        i = 0;
        while i < 128 { total = (total + get(&b, i) * (i + 1)) % 1000000007; i += 1; }
        repeat += 1;
    }
    total
}
fn main() {
    let a: Vec<String> = std::env::args().collect();
    let n: i64 = a[1].parse().unwrap();
    let seed: i64 = a[2].parse().unwrap();
    println!("{}", kernel(n, seed));
}
