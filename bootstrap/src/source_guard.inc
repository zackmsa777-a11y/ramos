# Compiler source identities survive subsequent reads and heap collections.
# Private intrinsic returns 0, or -22 (no input) / -27 (64 identities full).
runtime_protect_input:
    cmp QWORD PTR [r15 + 32], 0
    je runtime_protect_no_input
    cmp QWORD PTR [r15 + 88], 0
    jne runtime_protect_ready
    mov eax, 1024
    call runtime_buffer_new
    mov [r15 + 88], rax
runtime_protect_ready:
    mov rax, [r15 + 16]
    mov rdx, [r15 + 24]
    call runtime_guard_alias
    test rax, rax
    jnz runtime_protect_ok
    mov rcx, [r15 + 96]
    cmp rcx, 64
    jae runtime_protect_full
    mov r8, [r15 + 88]
    shl rcx, 4
    mov rax, [r15 + 16]
    mov [r8 + rcx + 8], rax
    mov rax, [r15 + 24]
    mov [r8 + rcx + 16], rax
    inc QWORD PTR [r15 + 96]
runtime_protect_ok:
    xor eax, eax
    ret
runtime_protect_no_input:
    mov rax, -22
    ret
runtime_protect_full:
    mov rax, -27
    ret
# RAX/RDX destination identity; returns 1 if explicitly protected, else 0.
runtime_guard_alias:
    mov r8, [r15 + 88]
    test r8, r8
    jz runtime_guard_not_found
    mov r9, [r15 + 96]
    add r8, 8
runtime_guard_next:
    test r9, r9
    jz runtime_guard_not_found
    cmp rax, [r8]
    jne runtime_guard_advance
    cmp rdx, [r8 + 8]
    jne runtime_guard_advance
    mov eax, 1
    ret
runtime_guard_advance:
    add r8, 16
    dec r9
    jmp runtime_guard_next
runtime_guard_not_found:
    xor eax, eax
    ret
