# Raw ReadFile input supports console handles, redirected files and byte pipes.
# Console bytes follow its configured input code page; redirection is binary.
runtime_stdin_prepare:
    mov rax, [r15 + 64]
    test rax, rax
    jnz runtime_stdin_prepared
    xor ecx, ecx
    mov edx, STDIN_ALLOCATION
    mov r8d, 0x3000
    mov r9d, 4
    API VirtualAlloc
    test rax, rax
    jz runtime_buffer_allocation_error
    mov [r15 + 64], rax
runtime_stdin_prepared:
    ret
runtime_stdin_refill:
    push rbp
    sub rsp, 32
    mov rbp, rsp
    mov [rbp], rax
    mov ecx, -10
    API GetStdHandle
    mov rcx, rax
    mov rdx, [rbp]
    add rdx, STDIN_DATA
    mov r8d, STDIN_CHUNK
    lea r9, [rbp + 8]
    xor r10d, r10d
    API ReadFile
    test eax, eax
    jz runtime_stdin_read_error
    mov eax, [rbp + 8]
    jmp runtime_stdin_read_done
runtime_stdin_read_error:
    API GetLastError
    cmp eax, 109                 # ERROR_BROKEN_PIPE: writer closed.
    je runtime_stdin_read_eof
    cmp eax, 38                  # ERROR_HANDLE_EOF.
    je runtime_stdin_read_eof
    call runtime_errno
    jmp runtime_stdin_read_done
runtime_stdin_read_eof:
    xor eax, eax
runtime_stdin_read_done:
    add rsp, 32
    pop rbp
    ret
