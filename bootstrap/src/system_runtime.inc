# 64 directory slots (64 bytes), plus Windows lazy API pointers. GC root +136.
# slot: native handle, generation ID, chunk, cursor, count, kind, EOF, pending.
runtime_system_table:
    mov rax, [r15 + 136]
    test rax, rax
    jnz runtime_system_table_ready
    mov eax, 4224
    call runtime_buffer_new
    mov [r15 + 136], rax
runtime_system_table_ready:
    ret
runtime_directory_lookup:
    test rax, rax
    jle runtime_directory_bad
    mov rcx, [r15 + 136]
    test rcx, rcx
    jz runtime_directory_bad
    add rcx, 8
    lea rdx, [rcx + 4096]
runtime_directory_lookup_more:
    cmp [rcx + 8], rax
    je runtime_directory_found
    add rcx, 64
    cmp rcx, rdx
    jb runtime_directory_lookup_more
runtime_directory_bad:
    mov rax, -9
    ret
runtime_directory_found:
    mov rax, rcx
    ret
runtime_dir_open:
    push rbp
    push rbx
    sub rsp, 32
    mov rbp, rsp
    mov [rbp], rax
    call runtime_system_table
    lea rbx, [rax + 8]
    lea rdx, [rbx + 4096]
runtime_directory_slot:
    cmp QWORD PTR [rbx + 8], 0
    je runtime_directory_available
    add rbx, 64
    cmp rbx, rdx
    jb runtime_directory_slot
    mov rax, -24
    jmp runtime_directory_open_done
runtime_directory_available:
    mov rax, [r15 + 120]
    inc rax
    js runtime_directory_generation_exhausted
    mov [rbp + 8], rax
    mov rax, [rbp]
    call runtime_path
    test rax, rax
    js runtime_directory_open_done
    mov [rbp + 16], rax
    mov eax, 8192
    call runtime_buffer_new
    mov [rbx + 16], rax
    mov QWORD PTR [rbx + 24], 0
    mov QWORD PTR [rbx + 32], 0
    mov QWORD PTR [rbx + 40], 0
    mov QWORD PTR [rbx + 48], 0
    mov QWORD PTR [rbx + 56], 0
    mov rax, [rbp + 16]
    call runtime_os_dir_open
    test rax, rax
    js runtime_directory_open_failed
    mov [rbx], rax
    mov rax, [rbp + 8]
    mov [rbx + 8], rax
    mov [r15 + 120], rax
    jmp runtime_directory_open_done
runtime_directory_generation_exhausted:
    mov rax, -75
    jmp runtime_directory_open_done
runtime_directory_open_failed:
    mov QWORD PTR [rbx + 16], 0
runtime_directory_open_done:
    mov [r15 + 8], rax
    test rax, rax
    js runtime_directory_open_return
    mov QWORD PTR [r15 + 8], 0
runtime_directory_open_return:
    add rsp, 32
    pop rbx
    pop rbp
    ret
runtime_dir_next:
    push rbx
    call runtime_directory_lookup
    test rax, rax
    js runtime_directory_next_error
    mov rbx, rax
    mov QWORD PTR [rbx + 40], 0
    call runtime_os_dir_next
    test rax, rax
    js runtime_directory_next_os_error
    mov QWORD PTR [r15 + 8], 0
    pop rbx
    ret
runtime_directory_next_os_error:
    mov QWORD PTR [rbx + 40], 0
runtime_directory_next_error:
    mov [r15 + 8], rax
    xor eax, eax
    call runtime_buffer_new
    pop rbx
    ret
runtime_dir_kind:
    call runtime_directory_lookup
    test rax, rax
    js runtime_directory_kind_error
    mov rax, [rax + 40]
    mov QWORD PTR [r15 + 8], 0
    ret
runtime_directory_kind_error:
    mov [r15 + 8], rax
    xor eax, eax
    ret
runtime_dir_close:
    push rbx
    call runtime_directory_lookup
    test rax, rax
    js runtime_directory_close_done
    mov rbx, rax
    mov QWORD PTR [rbx + 8], 0
    call runtime_os_dir_close
    mov QWORD PTR [rbx + 16], 0
runtime_directory_close_done:
    mov [r15 + 8], rax
    pop rbx
    ret
