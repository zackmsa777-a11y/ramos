# Copied inside runtime_writer..runtime_writer_end. Opaque handles always
# point into this process-owned monotonic arena. No routine frees/reuses bytes.
# r12=Ramos call depth, r13=arena base (zero before lazy mmap), r14=used bytes.
runtime_buffer_new:
    cmp rax, BUFFER_LIMIT
    ja runtime_buffer_size_error
    # Negative lengths compare above BUFFER_LIMIT as unsigned.
    lea rdx, [rax + 15]
    and rdx, -8
    lea rcx, [r14 + rdx]
    cmp rcx, BUFFER_ARENA_LIMIT
    ja runtime_buffer_allocation_error
    test r13, r13
    jnz runtime_buffer_allocate
    push rax
    push rdx
    mov eax, 9
    xor edi, edi
    mov esi, BUFFER_ARENA_LIMIT
    mov edx, 3                 # PROT_READ | PROT_WRITE, never PROT_EXEC
    mov r10d, 0x22            # MAP_PRIVATE | MAP_ANONYMOUS
    mov r8, -1
    xor r9d, r9d
    syscall
    cmp rax, -4095
    jae runtime_buffer_allocation_error
    mov r13, rax
    pop rdx
    pop rax
runtime_buffer_allocate:
    mov rcx, rax
    lea rax, [r13 + r14]
    add r14, rdx
    mov QWORD PTR [rax], rcx
    # Anonymous mmap is zero-filled; this region has never been handed out.
    ret

runtime_buffer_literal:
    push rsi
    call runtime_buffer_new
    pop rsi
    mov rcx, QWORD PTR [rax]
    lea rdi, [rax + 8]
    rep movsb
    ret
runtime_buffer_len:
    mov rax, QWORD PTR [rax]
    ret
runtime_buffer_get:
    cmp rcx, QWORD PTR [rax]
    jae runtime_buffer_index_error
    movzx eax, BYTE PTR [rax + rcx + 8]
    ret
runtime_buffer_set:
    cmp rcx, QWORD PTR [rax]
    jae runtime_buffer_index_error
    cmp rdx, 255
    ja runtime_buffer_value_error
    mov BYTE PTR [rax + rcx + 8], dl
    xor eax, eax
    ret
runtime_buffer_print:
    mov rdx, QWORD PTR [rax]
    lea rsi, [rax + 8]
    call runtime_writer
    lea rsi, [rip + runtime_buffer_newline]
    mov edx, 1
    jmp runtime_writer
runtime_buffer_newline: .byte 10

runtime_buffer_size_error:
    lea rsi, [rip + runtime_buffer_size_message]
    mov edx, OFFSET FLAT:BUFFER_SIZE_MESSAGE_SIZE
    jmp runtime_buffer_error
runtime_buffer_allocation_error:
    lea rsi, [rip + runtime_buffer_allocation_message]
    mov edx, OFFSET FLAT:BUFFER_ALLOCATION_MESSAGE_SIZE
    jmp runtime_buffer_error
runtime_buffer_index_error:
    lea rsi, [rip + runtime_buffer_index_message]
    mov edx, OFFSET FLAT:BUFFER_INDEX_MESSAGE_SIZE
    jmp runtime_buffer_error
runtime_buffer_value_error:
    lea rsi, [rip + runtime_buffer_value_message]
    mov edx, OFFSET FLAT:BUFFER_VALUE_MESSAGE_SIZE
runtime_buffer_error:
    mov edi, 2
    call runtime_write_fd
    mov edi, 1
    mov eax, 60
    syscall
    ud2
runtime_buffer_size_message:
    .ascii "Ramos runtime error: buffer size must be between 0 and 1048576\n"
.equ BUFFER_SIZE_MESSAGE_SIZE, . - runtime_buffer_size_message
runtime_buffer_allocation_message:
    .ascii "Ramos runtime error: buffer allocation failed or arena limit exceeded\n"
.equ BUFFER_ALLOCATION_MESSAGE_SIZE, . - runtime_buffer_allocation_message
runtime_buffer_index_message:
    .ascii "Ramos runtime error: buffer index out of bounds\n"
.equ BUFFER_INDEX_MESSAGE_SIZE, . - runtime_buffer_index_message
runtime_buffer_value_message:
    .ascii "Ramos runtime error: byte value must be between 0 and 255\n"
.equ BUFFER_VALUE_MESSAGE_SIZE, . - runtime_buffer_value_message
.equ RUNTIME_BUFFER_NEW_FILE, CODE_OFFSET + runtime_buffer_new - runtime_writer
.equ RUNTIME_BUFFER_LITERAL_FILE, CODE_OFFSET + runtime_buffer_literal - runtime_writer
.equ RUNTIME_BUFFER_LEN_FILE, CODE_OFFSET + runtime_buffer_len - runtime_writer
.equ RUNTIME_BUFFER_GET_FILE, CODE_OFFSET + runtime_buffer_get - runtime_writer
.equ RUNTIME_BUFFER_SET_FILE, CODE_OFFSET + runtime_buffer_set - runtime_writer
.equ RUNTIME_BUFFER_PRINT_FILE, CODE_OFFSET + runtime_buffer_print - runtime_writer
