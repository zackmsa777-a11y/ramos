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

# Create a fresh private directory, compile output already supplied in memory.
# A single synchronous operation owns publication, waiting and cleanup.
runtime_run_file:
    push rbp
    push rbx
    sub rsp, 64
    mov rbp, rsp
    mov [rbp], rax
    mov [rbp + 8], rcx
    mov QWORD PTR [rbp + 24], 0
    mov QWORD PTR [rbp + 40], 0
    call runtime_run_directory
    test rax, rax
    js runtime_run_file_error
    mov [rbp + 16], rax
    mov rbx, [rax]
    lea rax, [rbx + 8]
    call runtime_buffer_new
    mov [rbp + 24], rax
    lea rdi, [rax + 8]
    mov rsi, [rbp + 16]
    add rsi, 8
    mov rcx, rbx
    rep movsb
    mov rax, 0x6578652e7070612f   # /app.exe
    mov [rdi], rax
    mov rax, [rbp + 24]
    mov rcx, [rbp]
    mov edx, 1
    call runtime_write_file
    test rax, rax
    js runtime_run_file_save_error
    mov rax, [rbp + 24]
    mov rcx, [rbp + 8]
    call runtime_process_run
    mov [rbp + 32], rax
    mov rax, [r15 + 8]
    mov [rbp + 40], rax
    jmp runtime_run_file_cleanup
runtime_run_file_save_error:
    mov [rbp + 40], rax
runtime_run_file_cleanup:
    mov rax, [rbp + 24]
    call runtime_os_run_unlink
    cmp rax, -2
    je runtime_run_file_remove_dir
    test rax, rax
    jns runtime_run_file_remove_dir
    cmp QWORD PTR [rbp + 40], 0
    jne runtime_run_file_remove_dir
    mov [rbp + 40], rax
runtime_run_file_remove_dir:
    mov rax, [rbp + 16]
    call runtime_os_run_rmdir
    test rax, rax
    jns runtime_run_file_status
    cmp QWORD PTR [rbp + 40], 0
    jne runtime_run_file_status
    mov [rbp + 40], rax
runtime_run_file_status:
    mov rax, [rbp + 40]
    test rax, rax
    js runtime_run_file_error
    mov QWORD PTR [r15 + 8], 0
    mov rax, [rbp + 32]
    jmp runtime_run_file_return
runtime_run_file_error:
    mov [r15 + 8], rax
runtime_run_file_return:
    add rsp, 64
    pop rbx
    pop rbp
    ret
runtime_run_directory:
    push rbp
    push rbx
    sub rsp, 40
    mov rbp, rsp
    call runtime_os_run_base
    test rax, rax
    js runtime_run_directory_return
    mov [rbp], rax
    mov rdx, [rax]
    cmp rdx, 4060
    ja runtime_run_directory_long
    lea rax, [rdx + 27]
    call runtime_buffer_new
    mov [rbp + 8], rax
    lea rdi, [rax + 8]
    mov rsi, [rbp]
    mov rcx, [rsi]
    add rsi, 8
    rep movsb
    lea rsi, [rip + runtime_run_prefix]
    mov ecx, 11
    rep movsb
    mov [rbp + 16], rdi
    xor ebx, ebx
runtime_run_directory_retry:
    inc ebx
    cmp ebx, 16
    ja runtime_run_directory_conflict
    call runtime_os_run_random
    cmp QWORD PTR [r15 + 8], 0
    jne runtime_run_directory_random_error
    add rax, rbx
    mov rdi, [rbp + 16]
    mov ecx, 16
runtime_run_directory_hex:
    mov edx, eax
    and edx, 15
    add edx, 'a'
    mov [rdi], dl
    inc rdi
    shr rax, 4
    loop runtime_run_directory_hex
    mov rax, [rbp + 8]
    call runtime_os_run_mkdir
    cmp rax, -17
    je runtime_run_directory_retry
    test rax, rax
    js runtime_run_directory_return
    mov rax, [rbp + 8]
    jmp runtime_run_directory_return
runtime_run_directory_random_error:
    mov rax, [r15 + 8]
    jmp runtime_run_directory_return
runtime_run_directory_conflict:
    mov rax, -17
    jmp runtime_run_directory_return
runtime_run_directory_long:
    mov rax, -36
runtime_run_directory_return:
    add rsp, 40
    pop rbx
    pop rbp
    ret
runtime_run_prefix: .ascii "/ramos-run-"
.ifdef CODE_OFFSET
.equ RUNTIME_STDOUT_FILE, CODE_OFFSET + runtime_stdout - runtime_writer
.equ RUNTIME_RUN_FILE_FILE, CODE_OFFSET + runtime_run_file - runtime_writer
.endif
