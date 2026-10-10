# Shared nonmoving conservative heap. Blocks: total size, flags, reserved,
# logical length, then payload. Public handles still point at length (+24).
# 16 MiB live blocks + 8 MiB uint32 ownership map, one entry per 8-byte cell.
# flags 0=free, 1=allocated, 3=marked. No user-visible address conversions.
.equ HEAP_MAPPING_SIZE, BUFFER_ARENA_LIMIT + BUFFER_ARENA_LIMIT / 2
runtime_buffer_new:
    cmp rax, BUFFER_LIMIT
    ja runtime_buffer_size_error
    push rbx
    push rbp
    push rax
    lea rbx, [rax + 39]
    and rbx, -8
    xor ebp, ebp
    call runtime_heap_prepare
runtime_heap_find:
    mov rdi, [r15 + 80]
    test rdi, rdi
    jz runtime_heap_full_scan
    lea rax, [r13 + BUFFER_ARENA_LIMIT]
    cmp rdi, rax
    jae runtime_heap_full_scan
    cmp QWORD PTR [rdi + 8], 0
    jne runtime_heap_full_scan
    cmp [rdi], rbx
    jae runtime_heap_allocate
runtime_heap_full_scan:
    mov rdi, r13
runtime_heap_find_block:
    cmp QWORD PTR [rdi + 8], 0
    jne runtime_heap_next_block
    cmp [rdi], rbx
    jae runtime_heap_allocate
runtime_heap_next_block:
    add rdi, [rdi]
    lea rax, [r13 + BUFFER_ARENA_LIMIT]
    cmp rdi, rax
    jb runtime_heap_find_block
    test ebp, ebp
    jnz runtime_buffer_allocation_error
    mov ebp, 1
    call runtime_collect
    jmp runtime_heap_find
runtime_heap_allocate:
    mov rdx, [rdi]
    sub rdx, rbx
    cmp rdx, 32
    jb runtime_heap_no_split
    lea rcx, [rdi + rbx]
    mov [rcx], rdx
    mov QWORD PTR [rcx + 8], 0
    mov QWORD PTR [rcx + 24], 0
    mov [rdi], rbx
runtime_heap_no_split:
    mov QWORD PTR [rdi + 8], 1
    mov rax, [rsp]
    mov [rdi + 24], rax
    lea rbp, [rdi + 24]
    mov r11, rdi
    mov rax, [rdi]
    add rax, rdi
    mov [r15 + 80], rax
    add r14, [rdi]
    mov rcx, [rdi]
    shr rcx, 3
    sub rcx, 4
    add rdi, 32
    xor eax, eax
    rep stosq                    # Clear payload and padding on every reuse.
    mov rax, r11
    sub rax, r13
    lea rdi, [r13 + BUFFER_ARENA_LIMIT]
    mov rdx, rax
    shr rdx, 1
    add rdi, rdx
    inc eax                       # owner offset + 1; zero means free.
    mov rcx, [r11]
    shr rcx, 3
    rep stosd
    mov rax, rbp
    add rsp, 8
    pop rbp
    pop rbx
    ret
runtime_memory_used:
    mov rax, r14
    ret

# Mark any pointer into an allocated block, including an interior payload ptr.
# RAX candidate; clobber RAX/RCX/RDX, set R8=1 on discovering a new object.
runtime_heap_mark:
    cmp rax, r13
    jb runtime_heap_mark_done
    lea rdx, [r13 + BUFFER_ARENA_LIMIT]
    cmp rax, rdx
    jae runtime_heap_mark_done
    sub rax, r13
    shr rax, 3
    mov eax, DWORD PTR [rdx + rax*4]
    test eax, eax
    jz runtime_heap_mark_done
    dec eax
    add rax, r13
    cmp QWORD PTR [rax + 8], 1
    jne runtime_heap_mark_done
    mov QWORD PTR [rax + 8], 3
    mov r8d, 1
runtime_heap_mark_done:
    ret

runtime_collect:
    test r13, r13
    jz runtime_collect_empty
    push rax
    push rcx
    push rdx
    push rsi
    push rdi
    push r8
    push r9
    push r10
    push r11
    push rbx
    push rbp
    mov rax, [r15 + 88]
    call runtime_heap_mark
    mov rsi, rsp
    mov rdi, r15                  # Process-state block is above active frames.
runtime_heap_roots:
    cmp rsi, rdi
    jae runtime_heap_trace_start
    mov rax, [rsi]
    call runtime_heap_mark
    add rsi, 8
    jmp runtime_heap_roots
runtime_heap_trace_start:
    xor r8d, r8d
    mov rbx, r13
runtime_heap_trace_block:
    cmp QWORD PTR [rbx + 8], 3
    jne runtime_heap_trace_next
    lea rsi, [rbx + 32]
    mov rdi, [rbx + 24]
    add rdi, 7
    and rdi, -8
    add rdi, rsi
runtime_heap_trace_payload:
    cmp rsi, rdi
    jae runtime_heap_trace_next
    mov rax, [rsi]
    call runtime_heap_mark
    add rsi, 8
    jmp runtime_heap_trace_payload
runtime_heap_trace_next:
    add rbx, [rbx]
    lea rax, [r13 + BUFFER_ARENA_LIMIT]
    cmp rbx, rax
    jb runtime_heap_trace_block
    test r8d, r8d
    jnz runtime_heap_trace_start   # Fixed point handles arbitrary cycles.
    mov rbx, r13
runtime_heap_sweep:
    cmp QWORD PTR [rbx + 8], 3
    je runtime_heap_keep
    cmp QWORD PTR [rbx + 8], 1
    jne runtime_heap_sweep_next
    mov QWORD PTR [rbx + 8], 0
    sub r14, [rbx]
    mov rdi, rbx
    sub rdi, r13
    shr rdi, 1
    add rdi, r13
    add rdi, BUFFER_ARENA_LIMIT
    mov rcx, [rbx]
    shr rcx, 3
    xor eax, eax
    rep stosd
    jmp runtime_heap_sweep_next
runtime_heap_keep:
    mov QWORD PTR [rbx + 8], 1
runtime_heap_sweep_next:
    add rbx, [rbx]
    lea rax, [r13 + BUFFER_ARENA_LIMIT]
    cmp rbx, rax
    jb runtime_heap_sweep
    mov rbx, r13
runtime_heap_coalesce:
    lea rax, [r13 + BUFFER_ARENA_LIMIT]
    lea rdx, [rbx]
    add rdx, [rbx]
    cmp rdx, rax
    jae runtime_heap_collection_done
    cmp QWORD PTR [rbx + 8], 0
    jne runtime_heap_coalesce_next
    cmp QWORD PTR [rdx + 8], 0
    jne runtime_heap_coalesce_next
    mov rax, [rdx]
    add [rbx], rax
    jmp runtime_heap_coalesce
runtime_heap_coalesce_next:
    mov rbx, rdx
    jmp runtime_heap_coalesce
runtime_heap_collection_done:
    mov [r15 + 80], r13
    pop rbp
    pop rbx
    pop r11
    pop r10
    pop r9
    pop r8
    pop rdi
    pop rsi
    pop rdx
    pop rcx
    pop rax
runtime_collect_empty:
    xor eax, eax
    ret
