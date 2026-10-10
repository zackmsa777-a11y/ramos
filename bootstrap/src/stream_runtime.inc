# Shared checked stream registry. 64 slots of 64 bytes: native handle, public
# generation ID, mode (0 read/1 exclusive create/2 append), two identity words,
# sticky EOF. Registry is a GC root at process +104; ID counter at +120.
runtime_stream_table:
    mov rax, [r15 + 104]
    test rax, rax
    jnz runtime_stream_table_ready
    mov eax, 4096
    call runtime_buffer_new
    mov [r15 + 104], rax
runtime_stream_table_ready:
    ret
runtime_stream_lookup:
    test rax, rax
    jle runtime_stream_bad
    mov rcx, [r15 + 104]
    test rcx, rcx
    jz runtime_stream_bad
    add rcx, 8
    lea rdx, [rcx + 4096]
runtime_stream_lookup_more:
    cmp [rcx + 8], rax
    je runtime_stream_found
    add rcx, 64
    cmp rcx, rdx
    jb runtime_stream_lookup_more
runtime_stream_bad:
    mov rax, -9
    ret
runtime_stream_found:
    mov rax, rcx
    ret
# identity in RAX/RDX; return 1 if any active input has this identity.
runtime_stream_alias:
    mov rcx, [r15 + 104]
    test rcx, rcx
    jz runtime_stream_no_alias
    add rcx, 8
    lea r8, [rcx + 4096]
runtime_stream_alias_more:
    cmp QWORD PTR [rcx + 8], 0
    je runtime_stream_alias_next
    cmp QWORD PTR [rcx + 16], 0
    jne runtime_stream_alias_next
    cmp [rcx + 24], rax
    jne runtime_stream_alias_next
    cmp [rcx + 32], rdx
    je runtime_stream_yes_alias
runtime_stream_alias_next:
    add rcx, 64
    cmp rcx, r8
    jb runtime_stream_alias_more
runtime_stream_no_alias:
    xor eax, eax
    ret
runtime_stream_yes_alias:
    mov eax, 1
    ret
runtime_file_open:
    push rbp
    push rbx
    sub rsp, 208
    mov rbp, rsp
    mov [rbp], rax
    mov [rbp + 8], rcx
    mov QWORD PTR [rbp + 24], -1
    cmp rcx, 2
    ja runtime_stream_open_invalid
    call runtime_stream_table
    lea rbx, [rax + 8]
    lea rdx, [rbx + 4096]
runtime_stream_open_slot:
    cmp QWORD PTR [rbx + 8], 0
    je runtime_stream_open_available
    add rbx, 64
    cmp rbx, rdx
    jb runtime_stream_open_slot
    mov rax, -24
    jmp runtime_stream_open_return
runtime_stream_open_available:
    mov [rbp + 16], rbx
    mov rax, [r15 + 120]
    inc rax
    test rax, rax
    jle runtime_stream_open_exhausted
    mov [rbp + 40], rax
    mov rax, [rbp]
    call runtime_path
    test rax, rax
    js runtime_stream_open_return
    call runtime_os_stream_open
    test rax, rax
    js runtime_stream_open_cleanup
    cmp QWORD PTR [rbp + 8], 0
    je runtime_stream_open_register
    mov rax, [rbp + 176]
    mov rdx, [rbp + 184]
    call runtime_guard_alias
    test rax, rax
    jnz runtime_stream_open_alias
    cmp QWORD PTR [r15 + 32], 0
    je runtime_stream_check_active
    mov rax, [rbp + 176]
    cmp [r15 + 16], rax
    jne runtime_stream_check_active
    mov rax, [rbp + 184]
    cmp [r15 + 24], rax
    je runtime_stream_open_alias
runtime_stream_check_active:
    mov rax, [rbp + 176]
    mov rdx, [rbp + 184]
    call runtime_stream_alias
    test rax, rax
    jnz runtime_stream_open_alias
runtime_stream_open_register:
    mov rbx, [rbp + 16]
    mov rax, [rbp + 24]
    mov [rbx], rax
    mov rax, [rbp + 40]
    mov [rbx + 8], rax
    mov [r15 + 120], rax
    mov rcx, [rbp + 8]
    mov [rbx + 16], rcx
    mov rdx, [rbp + 176]
    mov [rbx + 24], rdx
    mov rdx, [rbp + 184]
    mov [rbx + 32], rdx
    mov QWORD PTR [rbx + 40], 0
    test rcx, rcx
    jnz runtime_stream_open_success
    mov rdx, [rbx + 24]
    mov [r15 + 16], rdx
    mov rdx, [rbx + 32]
    mov [r15 + 24], rdx
    mov QWORD PTR [r15 + 32], 1
runtime_stream_open_success:
    mov QWORD PTR [r15 + 8], 0
    jmp runtime_stream_open_done
runtime_stream_open_alias:
    mov rax, -22
    jmp runtime_stream_open_cleanup
runtime_stream_open_invalid:
    mov rax, -22
    jmp runtime_stream_open_return
runtime_stream_open_exhausted:
    mov rax, -75
    jmp runtime_stream_open_return
runtime_stream_open_cleanup:
    mov [rbp + 32], rax
    mov rdi, [rbp + 24]
    cmp rdi, -1
    je runtime_stream_open_status
    call runtime_os_stream_close
runtime_stream_open_status:
    mov rax, [rbp + 32]
runtime_stream_open_return:
    mov [r15 + 8], rax
runtime_stream_open_done:
    add rsp, 208
    pop rbx
    pop rbp
    ret
runtime_file_read:
    push rbp
    push rbx
    sub rsp, 24
    mov rbp, rsp
    mov [rbp], rcx
    call runtime_stream_lookup
    test rax, rax
    js runtime_stream_read_error
    mov rbx, rax
    cmp QWORD PTR [rbx + 16], 0
    jne runtime_stream_read_bad
    mov rax, [rbp]
    cmp rax, BUFFER_LIMIT
    ja runtime_stream_read_invalid
    call runtime_buffer_new
    mov [rbp + 8], rax
    mov rdx, [rbp]
    test rdx, rdx
    jz runtime_stream_read_success
    lea rsi, [rax + 8]
    mov rdi, [rbx]
    call runtime_os_stream_read
    test rax, rax
    js runtime_stream_read_error
    test rax, rax
    jnz runtime_stream_read_count
    mov QWORD PTR [rbx + 40], 1
runtime_stream_read_count:
    mov rcx, [rbp + 8]
    mov [rcx], rax
runtime_stream_read_success:
    mov QWORD PTR [r15 + 8], 0
    mov rax, [rbp + 8]
    jmp runtime_stream_read_done
runtime_stream_read_bad:
    mov rax, -9
    jmp runtime_stream_read_error
runtime_stream_read_invalid:
    mov rax, -22
runtime_stream_read_error:
    mov [r15 + 8], rax
    xor eax, eax
    call runtime_buffer_new
runtime_stream_read_done:
    add rsp, 24
    pop rbx
    pop rbp
    ret
runtime_file_write:
    push rbp
    push rbx
    push rcx
    call runtime_stream_lookup
    test rax, rax
    js runtime_stream_write_done
    cmp QWORD PTR [rax + 16], 0
    je runtime_stream_write_bad
    mov rdi, [rax]
    mov rsi, [rsp]
    mov rdx, [rsi]
    add rsi, 8
    call runtime_os_stream_write
    jmp runtime_stream_write_done
runtime_stream_write_bad:
    mov rax, -9
runtime_stream_write_done:
    mov [r15 + 8], rax
    add rsp, 8
    pop rbx
    pop rbp
    ret
runtime_file_eof:
    call runtime_stream_lookup
    test rax, rax
    js runtime_stream_eof_bad
    cmp QWORD PTR [rax + 16], 0
    jne runtime_stream_eof_invalid
    mov rax, [rax + 40]
    mov QWORD PTR [r15 + 8], 0
    ret
runtime_stream_eof_invalid:
    mov rax, -9
runtime_stream_eof_bad:
    mov [r15 + 8], rax
    xor eax, eax
    ret
runtime_file_close:
    call runtime_stream_lookup
    test rax, rax
    js runtime_stream_close_done
    mov rdi, [rax]
    mov QWORD PTR [rax + 8], 0
    call runtime_os_stream_close
runtime_stream_close_done:
    mov [r15 + 8], rax
    ret
runtime_stdout:
    mov rdx, [rax]
    lea rsi, [rax + 8]
    call runtime_stdout_write
    mov [r15 + 8], rax
    ret
runtime_file_seek:
    push rbx
    push rcx
    call runtime_stream_lookup
    test rax, rax
    js runtime_stream_seek_done
    mov rbx, rax
    cmp QWORD PTR [rbx + 16], 0
    jne runtime_stream_seek_bad
    mov rax, [rsp]
    test rax, rax
    js runtime_stream_seek_invalid
    mov rdi, [rbx]
    call runtime_os_stream_seek
    test rax, rax
    js runtime_stream_seek_done
    mov QWORD PTR [rbx + 40], 0
    mov QWORD PTR [r15 + 8], 0
    jmp runtime_stream_seek_return
runtime_stream_seek_bad:
    mov rax, -9
    jmp runtime_stream_seek_done
runtime_stream_seek_invalid:
    mov rax, -22
runtime_stream_seek_done:
    mov [r15 + 8], rax
runtime_stream_seek_return:
    add rsp, 8
    pop rbx
    ret
