# Shared Linux/Windows decimal and buffered-line semantics. Process state:
# +48 parse status, +56 sticky stdin EOF, +64 lazy stdin scratch mapping.
.equ STDIN_DATA, 64
.equ STDIN_CHUNK, 4096
.equ STDIN_LINE, 8192
.equ STDIN_ALLOCATION, BUFFER_LIMIT + 12288

# RAX signed integer, RSI exclusive end of caller-owned 32-byte scratch.
# Return RSI first digit/sign and RDX length. INT64_MIN uses unsigned magnitude.
runtime_decimal_digits:
    mov r8, rsi
    mov r10, rax
    test rax, rax
    jns runtime_decimal_magnitude
    neg rax
runtime_decimal_magnitude:
    mov r9d, 10
runtime_decimal_digit:
    xor edx, edx
    div r9
    add dl, '0'
    dec rsi
    mov [rsi], dl
    test rax, rax
    jnz runtime_decimal_digit
    test r10, r10
    jns runtime_decimal_done
    dec rsi
    mov BYTE PTR [rsi], '-'
runtime_decimal_done:
    mov rdx, r8
    sub rdx, rsi
    ret
runtime_int_to_text:
    sub rsp, 32
    lea rsi, [rsp + 32]
    call runtime_decimal_digits
    mov rax, rdx
    call runtime_buffer_literal
    add rsp, 32
    ret

# Whole-buffer ASCII [+-]?[0-9]+. Accumulate negatively to represent INT64_MIN.
# Continue validating bytes after overflow: invalid syntax takes precedence.
runtime_text_to_int:
    mov QWORD PTR [r15 + 48], 0
    mov rcx, [rax]
    lea rsi, [rax + 8]
    xor eax, eax
    xor r8d, r8d
    xor r9d, r9d
    xor r11d, r11d
    test rcx, rcx
    jz runtime_parse_invalid
    cmp BYTE PTR [rsi], '-'
    jne runtime_parse_plus
    mov r8d, 1
    inc r9
    jmp runtime_parse_sign_done
runtime_parse_plus:
    cmp BYTE PTR [rsi], '+'
    jne runtime_parse_sign_done
    inc r9
runtime_parse_sign_done:
    cmp r9, rcx
    je runtime_parse_invalid
    mov r10, -922337203685477580
runtime_parse_digit:
    movzx edx, BYTE PTR [rsi + r9]
    sub edx, '0'
    cmp edx, 9
    ja runtime_parse_invalid
    test r11d, r11d
    jnz runtime_parse_next
    cmp rax, r10
    jl runtime_parse_overflow
    jne runtime_parse_accumulate
    cmp edx, 7
    jbe runtime_parse_accumulate
    test r8d, r8d
    jz runtime_parse_overflow
    cmp edx, 8
    ja runtime_parse_overflow
runtime_parse_accumulate:
    imul rax, rax, 10
    sub rax, rdx
    jmp runtime_parse_next
runtime_parse_overflow:
    mov r11d, 1
runtime_parse_next:
    inc r9
    cmp r9, rcx
    jb runtime_parse_digit
    test r11d, r11d
    jnz runtime_parse_range
    test r8d, r8d
    jnz runtime_parse_done
    neg rax
runtime_parse_done:
    ret
runtime_parse_invalid:
    mov QWORD PTR [r15 + 48], -22
    xor eax, eax
    ret
runtime_parse_range:
    mov QWORD PTR [r15 + 48], -34
    xor eax, eax
    ret
runtime_parse_error:
    mov rax, [r15 + 48]
    ret
runtime_stdin_eof:
    mov rax, [r15 + 56]
    ret

# OS helpers allocate bounded RW scratch and refill 4 KiB of raw input bytes.
# Return fresh arena buffers sized to the actual line; scratch is reused.
runtime_read_line:
    push rbp
    push rbx
    sub rsp, 32
    mov rbp, rsp
    xor ebx, ebx
    mov QWORD PTR [rbp + 8], 0
    mov QWORD PTR [r15 + 8], 0
    call runtime_stdin_prepare
    mov [rbp], rax
    cmp QWORD PTR [r15 + 56], 0
    jne runtime_line_finish
runtime_line_more:
    mov rcx, [rbp]
    mov rdx, [rcx]
    cmp rdx, [rcx + 8]
    jb runtime_line_byte
    mov rax, rcx
    call runtime_stdin_refill
    test rax, rax
    js runtime_line_io_error
    jz runtime_line_eof
    mov rcx, [rbp]
    mov QWORD PTR [rcx], 0
    mov [rcx + 8], rax
    xor edx, edx
runtime_line_byte:
    movzx eax, BYTE PTR [rcx + rdx + STDIN_DATA]
    inc QWORD PTR [rcx]
    cmp eax, 10
    je runtime_line_newline
    cmp rbx, BUFFER_LIMIT + 1
    jae runtime_line_drain
    mov [rcx + rbx + STDIN_LINE], al
    inc rbx
    jmp runtime_line_more
runtime_line_drain:
    mov QWORD PTR [rbp + 8], 1
    jmp runtime_line_more
runtime_line_newline:
    test rbx, rbx
    jz runtime_line_finish
    cmp BYTE PTR [rcx + rbx + STDIN_LINE - 1], 13
    jne runtime_line_finish
    dec rbx
    jmp runtime_line_finish
runtime_line_eof:
    mov QWORD PTR [r15 + 56], 1
runtime_line_finish:
    cmp QWORD PTR [rbp + 8], 0
    jne runtime_line_large
    cmp rbx, BUFFER_LIMIT
    ja runtime_line_large
    mov rax, rbx
    mov rsi, [rbp]
    add rsi, STDIN_LINE
    call runtime_buffer_literal
    jmp runtime_line_return
runtime_line_large:
    mov rax, -27
runtime_line_io_error:
    mov [r15 + 8], rax
    xor eax, eax
    call runtime_buffer_new
runtime_line_return:
    add rsp, 32
    pop rbx
    pop rbp
    ret
