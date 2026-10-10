#![allow(dead_code)]
fn buffer(n: i64) -> Vec<u8> {
    assert!((0..=1048576).contains(&n)); vec![0; n as usize]
}
fn get(b: &[u8], i: i64) -> i64 { b[usize::try_from(i).unwrap()] as i64 }
fn set(b: &mut [u8], i: i64, v: i64) {
    b[usize::try_from(i).unwrap()] = u8::try_from(v).unwrap();
}
fn kernel(n: i64, seed: i64) -> i64 {
    let mut a = buffer(256); let mut b = buffer(256); let mut out = buffer(256); let mut i = 0;
    while i < 256 {
        set(&mut a, i, (i * 17 + seed) % 256); set(&mut b, i, (i * 29 + seed) % 256); i += 1;
    }
    let mut total = 0; let mut repeat = 0;
    while repeat < n {
        set(&mut a, repeat % 256, (repeat + seed) % 256);
        let mut row = 0;
        while row < 16 {
            let mut col = 0;
            while col < 16 {
                let mut sum = 0; let mut k = 0;
                while k < 16 {
                    sum += get(&a, row * 16 + k) * get(&b, k * 16 + col); k += 1;
                }
                set(&mut out, row * 16 + col, sum % 256); col += 1;
            }
            row += 1;
        }
        i = 0;
        while i < 256 { total = (total + get(&out, i) * (i + 1)) % 1000000007; i += 1; }
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
