# Finite binary64 values travel as eight-byte payloads in the Ramos stack ABI.
# SSE2 rounding is initialized to nearest/even with gradual underflow at entry.
runtime_float_error:
    lea rsi, [rip + runtime_float_message]
    mov edx, runtime_float_message_end - runtime_float_message
    jmp runtime_value_error
runtime_float_check:
    mov rcx, rax
    shr rcx, 52
    and ecx, 2047
    cmp ecx, 2047
    je runtime_float_error
    ret
runtime_float_from_int:
    cvtsi2sd xmm0, rax
    movq rax, xmm0
    ret
runtime_float_to_int:
    call runtime_float_check
    movq xmm0, rax
    mov rcx, 0x43e0000000000000  # +2^63 (excluded)
    movq xmm1, rcx
    ucomisd xmm0, xmm1
    jae runtime_float_error
    mov rcx, 0xc3e0000000000000  # -2^63 (included)
    movq xmm1, rcx
    ucomisd xmm0, xmm1
    jb runtime_float_error
    cvttsd2si rax, xmm0
    ret
runtime_float_sqrt:
    call runtime_float_check
    movq xmm0, rax
    xorpd xmm1, xmm1
    ucomisd xmm0, xmm1
    jb runtime_float_error
    sqrtsd xmm0, xmm0
    movq rax, xmm0
    jmp runtime_float_check
runtime_float_print:
    mov ecx, 6
    call runtime_float_to_text
    jmp runtime_buffer_print

# Exact fixed decimal rounding: m*2^e * 10^places = m*5^places*2^(e+places).
# Base-1e9 limbs avoid floating decimal arithmetic and double-rounding.
runtime_float_to_text:
    cmp rcx, 18
    ja runtime_float_error
    push rbp
    push rbx
    sub rsp, 1088
    mov rbp, rsp
    mov [rbp + 8], rcx
    mov rdx, rax
    shr rdx, 63
    mov [rbp], rdx
    call runtime_float_check
    mov r8, rax
    shr r8, 52
    and r8d, 2047
    mov r9, 0x000fffffffffffff
    and rax, r9
    mov rdx, -1074
    test r8, r8
    jz runtime_float_format_exponent
    bts rax, 52
    lea rdx, [r8 - 1075]
runtime_float_format_exponent:
    add rdx, [rbp + 8]
    mov [rbp + 16], rdx
    push rax
    lea rdi, [rbp + 64]
    xor eax, eax
    mov ecx, 40
    rep stosq
    pop rax
    xor r9d, r9d
    mov r10d, 1000000000
runtime_float_format_initial:
    xor edx, edx
    div r10
    mov [rbp + r9*8 + 64], rdx
    inc r9
    test rax, rax
    jnz runtime_float_format_initial
    mov [rbp + 24], r9
    mov ebx, [rbp + 8]
    mov r8d, 5
runtime_float_format_fives:
    test ebx, ebx
    jz runtime_float_format_binary
    call runtime_float_format_multiply
    dec ebx
    jmp runtime_float_format_fives
runtime_float_format_binary:
    mov rbx, [rbp + 16]
    test rbx, rbx
    js runtime_float_format_fraction
    mov r8d, 2
runtime_float_format_twos:
    test ebx, ebx
    jz runtime_float_format_digits
    call runtime_float_format_multiply
    dec ebx
    jmp runtime_float_format_twos
runtime_float_format_fraction:
    neg ebx
    mov QWORD PTR [rbp + 32], 0
    mov QWORD PTR [rbp + 40], 0
runtime_float_format_halves:
    mov rax, [rbp + 32]
    or [rbp + 40], rax
    mov r9, [rbp + 24]
    xor r11d, r11d
runtime_float_format_half_limb:
    dec r9
    mov rax, r11
    imul rax, rax, 1000000000
    add rax, [rbp + r9*8 + 64]
    mov r11, rax
    and r11d, 1
    shr rax, 1
    mov [rbp + r9*8 + 64], rax
    test r9, r9
    jnz runtime_float_format_half_limb
    mov [rbp + 32], r11
    mov r9, [rbp + 24]
runtime_float_format_trim:
    cmp r9, 1
    jbe runtime_float_format_trim_done
    cmp QWORD PTR [rbp + r9*8 + 56], 0
    jne runtime_float_format_trim_done
    dec r9
    jmp runtime_float_format_trim
runtime_float_format_trim_done:
    mov [rbp + 24], r9
    dec ebx
    jnz runtime_float_format_halves
    cmp QWORD PTR [rbp + 32], 0
    je runtime_float_format_digits
    cmp QWORD PTR [rbp + 40], 0
    jne runtime_float_format_round
    test QWORD PTR [rbp + 64], 1
    jz runtime_float_format_digits
runtime_float_format_round:
    xor r9d, r9d
runtime_float_format_round_limb:
    inc QWORD PTR [rbp + r9*8 + 64]
    cmp QWORD PTR [rbp + r9*8 + 64], 1000000000
    jb runtime_float_format_round_done
    mov QWORD PTR [rbp + r9*8 + 64], 0
    inc r9
    jmp runtime_float_format_round_limb
runtime_float_format_round_done:
    inc r9
    cmp r9, [rbp + 24]
    jbe runtime_float_format_digits
    mov [rbp + 24], r9
runtime_float_format_digits:
    mov r9, [rbp + 24]
    imul r9, r9, 9
    lea rdi, [rbp + r9 + 383]
    xor r8d, r8d
    mov r10d, 10
runtime_float_format_digit_limb:
    mov rax, [rbp + r8*8 + 64]
    mov ecx, 9
runtime_float_format_digit:
    xor edx, edx
    div r10
    add dl, '0'
    mov [rdi], dl
    dec rdi
    dec ecx
    jnz runtime_float_format_digit
    inc r8
    cmp r8, [rbp + 24]
    jb runtime_float_format_digit_limb
    lea rsi, [rbp + 384]
runtime_float_format_leading:
    cmp r9, 1
    jbe runtime_float_format_output
    cmp BYTE PTR [rsi], '0'
    jne runtime_float_format_output
    inc rsi
    dec r9
    jmp runtime_float_format_leading
runtime_float_format_output:
    lea rdi, [rbp + 736]
    cmp QWORD PTR [rbp], 0
    je runtime_float_format_sign_done
    mov BYTE PTR [rdi], '-'
    inc rdi
runtime_float_format_sign_done:
    mov rcx, r9
    sub rcx, [rbp + 8]
    jle runtime_float_format_small
    sub r9, rcx
    rep movsb
    cmp QWORD PTR [rbp + 8], 0
    je runtime_float_format_tail
    mov BYTE PTR [rdi], '.'
    inc rdi
    jmp runtime_float_format_tail
runtime_float_format_small:
    mov BYTE PTR [rdi], '0'
    inc rdi
    mov BYTE PTR [rdi], '.'
    inc rdi
    neg rcx
    mov al, '0'
    rep stosb
runtime_float_format_tail:
    mov rcx, r9
    rep movsb
    lea rsi, [rbp + 736]
    mov rax, rdi
    sub rax, rsi
    call runtime_buffer_literal
    add rsp, 1088
    pop rbx
    pop rbp
    ret
# Private helper, RBP is the formatting frame and R8 the factor (2 or 5).
runtime_float_format_multiply:
    xor ecx, ecx
    xor r11d, r11d
runtime_float_format_mul_limb:
    mov rax, [rbp + rcx*8 + 64]
    imul rax, r8
    add rax, r11
    xor edx, edx
    div r10
    mov [rbp + rcx*8 + 64], rdx
    mov r11, rax
    inc rcx
    cmp rcx, [rbp + 24]
    jb runtime_float_format_mul_limb
    test r11, r11
    jz runtime_float_format_mul_done
    mov [rbp + rcx*8 + 64], r11
    inc QWORD PTR [rbp + 24]
runtime_float_format_mul_done:
    ret
runtime_float_message: .ascii "Ramos runtime error: non-finite float result or invalid float operation\n"
runtime_float_message_end:
