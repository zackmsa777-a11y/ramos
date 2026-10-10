# Native, position-independent OS boundary. r15 points to process state:
# initial argv stack, last errno, last read device/inode, identity-valid flag.
runtime_arg_count:
    mov rax, [r15]
    mov rax, [rax]
    ret
runtime_arg:
    mov rcx, [r15]
    cmp rax, [rcx]
    jae runtime_buffer_index_error
    mov rsi, [rcx + rax*8 + 8]
    xor eax, eax
runtime_arg_length:
    cmp BYTE PTR [rsi + rax], 0
    je runtime_buffer_literal
    inc rax
    cmp rax, BUFFER_LIMIT
    ja runtime_buffer_size_error
    jmp runtime_arg_length
runtime_io_error:
    mov rax, [r15 + 8]
    ret
runtime_stderr:
    mov rdx, [rax]
    lea rsi, [rax + 8]
    mov edi, 2
    call runtime_write_fd
    xor eax, eax
    ret
runtime_process_exit:
    cmp rax, 255
    ja runtime_buffer_value_error
    mov rdi, rax
    mov eax, 60
    syscall
    ud2
# Path bytes -> allocated NUL-terminated path, or -EINVAL/-ENAMETOOLONG.
runtime_path:
    mov rcx, [rax]
    cmp rcx, 4096
    jae runtime_path_long
    test rcx, rcx
    jz runtime_path_invalid
    lea rsi, [rax + 8]
    xor edx, edx
runtime_path_scan:
    cmp BYTE PTR [rsi + rdx], 0
    je runtime_path_invalid
    inc rdx
    cmp rdx, rcx
    jb runtime_path_scan
    push rsi
    lea rax, [rcx + 1]
    call runtime_buffer_new
    pop rsi
    lea rdi, [rax + 8]
    mov rcx, [rax]
    dec rcx
    rep movsb
    add rax, 8
    ret
runtime_path_long:
    mov rax, -36
    ret
runtime_path_invalid:
    mov rax, -22
    ret
runtime_read_file:
    push rbp
    push rbx
    sub rsp, 176
    mov rbp, rsp
    mov QWORD PTR [r15 + 8], 0
    mov QWORD PTR [rbp + 144], -1
    call runtime_path
    test rax, rax
    js runtime_read_error
    mov rsi, rax
    mov eax, 257
    mov rdi, -100
    mov edx, 0x80800
    xor r10d, r10d
    syscall
    test rax, rax
    js runtime_read_error
    mov [rbp + 144], rax
    mov rdi, rax
    mov rsi, rbp
    mov eax, 5
    syscall
    test rax, rax
    js runtime_read_error
    mov eax, [rbp + 24]
    and eax, 0xf000
    cmp eax, 0x8000
    jne runtime_read_invalid
    mov rax, [rbp + 48]
    cmp rax, BUFFER_LIMIT
    ja runtime_read_large
    call runtime_buffer_new
    mov [rbp + 152], rax
    xor ebx, ebx
runtime_read_more:
    mov rax, [rbp + 152]
    mov rdx, [rax]
    sub rdx, rbx
    jz runtime_read_probe
    lea rsi, [rax + rbx + 8]
    mov rdi, [rbp + 144]
    xor eax, eax
    syscall
    cmp rax, -4
    je runtime_read_more
    test rax, rax
    js runtime_read_error
    jz runtime_read_done
    add rbx, rax
    jmp runtime_read_more
runtime_read_probe:
    mov rdi, [rbp + 144]
    lea rsi, [rbp + 168]
    mov edx, 1
    xor eax, eax
    syscall
    cmp rax, -4
    je runtime_read_probe
    test rax, rax
    js runtime_read_error
    jnz runtime_read_large
runtime_read_done:
    mov rdi, [rbp + 144]
    mov QWORD PTR [rbp + 144], -1
    mov eax, 3
    syscall
    test rax, rax
    js runtime_read_error
    mov rax, [rbp]
    mov [r15 + 16], rax
    mov rax, [rbp + 8]
    mov [r15 + 24], rax
    mov QWORD PTR [r15 + 32], 1
    mov rax, [rbp + 152]
    mov [rax], rbx
    jmp runtime_read_return
runtime_read_large:
    mov rax, -27
    jmp runtime_read_error
runtime_read_invalid:
    mov rax, -22
runtime_read_error:
    mov [r15 + 8], rax
    mov rdi, [rbp + 144]
    test rdi, rdi
    js runtime_read_empty
    mov eax, 3
    syscall
runtime_read_empty:
    xor eax, eax
    call runtime_buffer_new
runtime_read_return:
    add rsp, 176
    pop rbx
    pop rbp
    ret
# fd=rdi, data=rsi, count=rdx; return 0 or negative errno, handling EINTR.
runtime_io_write_all:
    test rdx, rdx
    jz runtime_io_write_ok
runtime_io_write_more:
    mov eax, 1
    syscall
    cmp rax, -4
    je runtime_io_write_more
    test rax, rax
    js runtime_io_write_return
    jz runtime_io_write_zero
    add rsi, rax
    sub rdx, rax
    jnz runtime_io_write_more
runtime_io_write_ok:
    xor eax, eax
runtime_io_write_return:
    ret
runtime_io_write_zero:
    mov rax, -5
    ret
# Verify destination relative to the anchored directory; preserve last-read file.
runtime_check_destination:
    mov eax, 262
    mov rdi, [rbp + 24]
    mov rsi, [rbp + 48]
    lea rdx, [rbp + 128]
    xor r10d, r10d
    syscall
    cmp rax, -2
    je runtime_destination_ok
    test rax, rax
    js runtime_destination_return
    mov rax, [rbp + 128]
    mov rdx, [rbp + 136]
    call runtime_guard_alias
    test rax, rax
    jnz runtime_destination_alias
    cmp QWORD PTR [r15 + 32], 0
    je runtime_destination_exists
    mov rax, [r15 + 16]
    cmp rax, [rbp + 128]
    jne runtime_destination_exists
    mov rax, [r15 + 24]
    cmp rax, [rbp + 136]
    je runtime_destination_alias
runtime_destination_exists:
    test QWORD PTR [rbp + 16], 2
    jz runtime_destination_conflict
runtime_destination_ok:
    xor eax, eax
runtime_destination_return:
    ret
runtime_destination_alias:
    mov rax, -22
    ret
runtime_destination_conflict:
    mov rax, -17
    ret
# write_file(path, contents, flags): atomic same-directory publication.
# flags bit 0 executable, bit 1 replace; other bits rejected.
runtime_write_file:
    push rbp
    push rbx
    sub rsp, 4416
    mov rbp, rsp
    mov [rbp + 8], rcx
    mov [rbp + 16], rdx
    mov QWORD PTR [rbp + 24], -1
    mov QWORD PTR [rbp + 32], -1
    mov QWORD PTR [rbp + 40], 0
    mov QWORD PTR [r15 + 8], 0
    cmp rdx, 3
    ja runtime_write_invalid
    call runtime_path
    test rax, rax
    js runtime_write_error
    mov [rbp], rax
    xor ecx, ecx
    xor edx, edx
runtime_destination_scan:
    cmp BYTE PTR [rax + rcx], 0
    je runtime_destination_split
    cmp BYTE PTR [rax + rcx], '/'
    jne runtime_destination_scan_next
    lea rdx, [rcx + 1]
runtime_destination_scan_next:
    inc rcx
    jmp runtime_destination_scan
runtime_destination_split:
    cmp rcx, rdx
    je runtime_write_invalid
    lea rsi, [rax + rdx]
    mov [rbp + 48], rsi
    lea rdi, [rbp + 272]
    test rdx, rdx
    jz runtime_destination_current
    mov rsi, rax
    mov rcx, rdx
    rep movsb
    mov BYTE PTR [rdi], 0
    jmp runtime_destination_open
runtime_destination_current:
    mov WORD PTR [rdi], 0x002e
runtime_destination_open:
    mov eax, 257
    mov rdi, -100
    lea rsi, [rbp + 272]
    mov edx, 0x290000
    xor r10d, r10d
    syscall
    test rax, rax
    js runtime_write_error
    mov [rbp + 24], rax
    call runtime_check_destination
    test rax, rax
    js runtime_write_error
    xor ebx, ebx
runtime_temporary_retry:
    inc ebx
    cmp ebx, 16
    ja runtime_write_conflict
    mov eax, 318
    lea rdi, [rbp + 4384]
    mov esi, 8
    xor edx, edx
    syscall
    cmp rax, -4
    je runtime_temporary_retry
    cmp rax, 8
    jne runtime_write_random_error
    lea rdi, [rbp + 64]
    lea rsi, [rip + runtime_temporary_prefix]
    mov ecx, 11
    rep movsb
    mov rax, [rbp + 4384]
    mov ecx, 16
runtime_temporary_hex:
    mov edx, eax
    and edx, 15
    add edx, 97
    mov [rdi], dl
    inc rdi
    shr rax, 4
    loop runtime_temporary_hex
    mov BYTE PTR [rdi], 0
    # Never choose the requested basename as our temporary name.
    mov rsi, [rbp + 48]
    lea rdi, [rbp + 64]
    xor ecx, ecx
runtime_temporary_compare:
    mov al, [rsi + rcx]
    cmp al, [rdi + rcx]
    jne runtime_temporary_open
    test al, al
    jz runtime_temporary_retry
    inc rcx
    jmp runtime_temporary_compare
runtime_temporary_open:
    mov eax, 257
    mov rdi, [rbp + 24]
    lea rsi, [rbp + 64]
    mov edx, 0xa00c1
    mov r10d, 0x180
    syscall
    cmp rax, -17
    je runtime_temporary_retry
    test rax, rax
    js runtime_write_error
    mov [rbp + 32], rax
    mov QWORD PTR [rbp + 40], 1
    mov rdi, rax
    mov rax, [rbp + 8]
    mov rdx, [rax]
    lea rsi, [rax + 8]
    call runtime_io_write_all
    test rax, rax
    js runtime_write_error
    mov eax, 91
    mov rdi, [rbp + 32]
    mov esi, 0x1a4
    test QWORD PTR [rbp + 16], 1
    jz runtime_temporary_chmod
    mov esi, 0x1ed
runtime_temporary_chmod:
    syscall
    test rax, rax
    js runtime_write_error
    mov rdi, [rbp + 32]
    mov QWORD PTR [rbp + 32], -1
    mov eax, 3
    syscall
    test rax, rax
    js runtime_write_error
    call runtime_check_destination
    test rax, rax
    js runtime_write_error
    mov eax, 316
    mov rdi, [rbp + 24]
    lea rsi, [rbp + 64]
    mov rdx, rdi
    mov r10, [rbp + 48]
    mov r8d, 1
    test QWORD PTR [rbp + 16], 2
    jz runtime_temporary_rename
    xor r8d, r8d
runtime_temporary_rename:
    syscall
    test rax, rax
    js runtime_write_error
    mov QWORD PTR [rbp + 40], 0
    xor eax, eax
    jmp runtime_write_error
runtime_write_invalid:
    mov rax, -22
    jmp runtime_write_error
runtime_write_conflict:
    mov rax, -17
    jmp runtime_write_error
runtime_write_random_error:
    test rax, rax
    js runtime_write_error
    mov rax, -5
runtime_write_error:
    mov [rbp + 56], rax
    mov [r15 + 8], rax
    mov rdi, [rbp + 32]
    test rdi, rdi
    js runtime_write_unlink
    mov eax, 3
    syscall
runtime_write_unlink:
    cmp QWORD PTR [rbp + 40], 0
    je runtime_write_close_directory
    mov eax, 263
    mov rdi, [rbp + 24]
    lea rsi, [rbp + 64]
    xor edx, edx
    syscall
runtime_write_close_directory:
    mov rdi, [rbp + 24]
    test rdi, rdi
    js runtime_write_return
    mov eax, 3
    syscall
runtime_write_return:
    mov rax, [rbp + 56]
    add rsp, 4416
    pop rbx
    pop rbp
    ret
runtime_temporary_prefix: .ascii ".ramos-tmp-"
.equ RUNTIME_ARG_COUNT_FILE, CODE_OFFSET + runtime_arg_count - runtime_writer
.equ RUNTIME_ARG_FILE, CODE_OFFSET + runtime_arg - runtime_writer
.equ RUNTIME_READ_FILE_FILE, CODE_OFFSET + runtime_read_file - runtime_writer
.equ RUNTIME_WRITE_FILE_FILE, CODE_OFFSET + runtime_write_file - runtime_writer
.equ RUNTIME_IO_ERROR_FILE, CODE_OFFSET + runtime_io_error - runtime_writer
.equ RUNTIME_STDERR_FILE, CODE_OFFSET + runtime_stderr - runtime_writer
.equ RUNTIME_EXIT_FILE, CODE_OFFSET + runtime_process_exit - runtime_writer

runtime_platform:
    xor eax, eax
    ret
.equ RUNTIME_PLATFORM_FILE, CODE_OFFSET + runtime_platform - runtime_writer

.equ RUNTIME_PROTECT_FILE, CODE_OFFSET + runtime_protect_input - runtime_writer
