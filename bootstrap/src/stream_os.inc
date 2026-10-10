# rbp shared open frame: native fstat scratch +48..191, identities +176/+184.
runtime_os_stream_open:
    mov rsi, rax
    mov eax, 257
    mov rdi, -100
    mov edx, 0x80800                    # read-only, nonblocking, close-on-exec
    cmp QWORD PTR [rbp + 8], 0
    je runtime_os_stream_flags_ready
    mov edx, 0x808c1                    # exclusive create, write-only
    cmp QWORD PTR [rbp + 8], 1
    je runtime_os_stream_flags_ready
    mov edx, 0x80c41                    # append, create, write-only
runtime_os_stream_flags_ready:
    mov r10d, 0x1a4                     # 0644 subject to umask
    syscall
    test rax, rax
    js runtime_os_stream_open_done
    mov [rbp + 24], rax
    mov rdi, rax
    lea rsi, [rbp + 48]
    mov eax, 5
    syscall
    test rax, rax
    js runtime_os_stream_open_done
    mov eax, [rbp + 72]
    and eax, 0xf000
    cmp eax, 0x8000
    jne runtime_os_stream_invalid
    mov rax, [rbp + 48]
    mov [rbp + 176], rax
    mov rax, [rbp + 56]
    mov [rbp + 184], rax
    xor eax, eax
runtime_os_stream_open_done:
    ret
runtime_os_stream_invalid:
    mov rax, -22
    ret
runtime_os_stream_read:
    xor eax, eax
    syscall
    cmp rax, -4
    je runtime_os_stream_read
    ret
runtime_os_stream_write:
    jmp runtime_io_write_all
runtime_stdout_write:
    mov edi, 1
    jmp runtime_io_write_all
runtime_os_stream_close:
    mov eax, 3
    syscall
    ret
runtime_os_stream_seek:
    mov rsi, rax
    xor edx, edx
    mov eax, 8
    syscall
    ret
