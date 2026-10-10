# Linux stdin uses blocking read(0), retrying EINTR. Never close inherited stdin.
runtime_stdin_prepare:
    mov rax, [r15 + 64]
    test rax, rax
    jnz runtime_stdin_prepared
    mov eax, 9
    xor edi, edi
    mov esi, STDIN_ALLOCATION
    mov edx, 3
    mov r10d, 0x22
    mov r8, -1
    xor r9d, r9d
    syscall
    cmp rax, -4095
    jae runtime_buffer_allocation_error
    mov [r15 + 64], rax
runtime_stdin_prepared:
    ret
runtime_stdin_refill:
    lea rsi, [rax + STDIN_DATA]
    xor edi, edi
    mov edx, STDIN_CHUNK
runtime_stdin_read_again:
    xor eax, eax
    syscall
    cmp rax, -4
    je runtime_stdin_read_again
    ret
.equ RUNTIME_READ_LINE_FILE, CODE_OFFSET + runtime_read_line - runtime_writer
.equ RUNTIME_STDIN_EOF_FILE, CODE_OFFSET + runtime_stdin_eof - runtime_writer
.equ RUNTIME_INT_TO_TEXT_FILE, CODE_OFFSET + runtime_int_to_text - runtime_writer
.equ RUNTIME_TEXT_TO_INT_FILE, CODE_OFFSET + runtime_text_to_int - runtime_writer
.equ RUNTIME_PARSE_ERROR_FILE, CODE_OFFSET + runtime_parse_error - runtime_writer
