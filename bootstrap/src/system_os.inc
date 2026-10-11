runtime_cwd:
    push rbp
    mov rbp, rsp
    mov eax, 4096
    call runtime_buffer_new
    push rax
    lea rdi, [rax + 8]
    mov esi, 4096
    mov eax, 79
    syscall
    test rax, rax
    js runtime_cwd_error
    dec rax
    mov rdx, [rsp]
    mov [rdx], rax
    mov rax, rdx
    mov QWORD PTR [r15 + 8], 0
    jmp runtime_cwd_return
runtime_cwd_error:
    mov [r15 + 8], rax
    xor eax, eax
    call runtime_buffer_new
runtime_cwd_return:
    mov rsp, rbp
    pop rbp
    ret
# Environment is the process's inherited envp, after argv and its NULL.
runtime_env_get:
    mov rcx, [rax]
    test rcx, rcx
    jz runtime_env_invalid
    cmp rcx, 32767
    ja runtime_env_invalid
    xor edx, edx
runtime_env_validate:
    mov r8b, [rax + rdx + 8]
    test r8b, r8b
    jz runtime_env_invalid
    cmp r8b, '='
    je runtime_env_invalid
    inc rdx
    cmp rdx, rcx
    jb runtime_env_validate
    mov rdx, [r15]
    mov r8, [rdx]
    lea rdx, [rdx + r8*8 + 16]
runtime_env_search:
    mov rsi, [rdx]
    test rsi, rsi
    jz runtime_env_missing
    xor r8d, r8d
runtime_env_compare:
    mov r9b, [rsi + r8]
    cmp r9b, [rax + r8 + 8]
    jne runtime_env_next
    inc r8
    cmp r8, rcx
    jb runtime_env_compare
    cmp BYTE PTR [rsi + r8], '='
    je runtime_env_found
runtime_env_next:
    add rdx, 8
    jmp runtime_env_search
runtime_env_found:
    lea rsi, [rsi + rcx + 1]
    xor eax, eax
runtime_env_length:
    cmp BYTE PTR [rsi + rax], 0
    je runtime_env_copy
    inc rax
    cmp rax, 32767
    jbe runtime_env_length
    mov rax, -27
    jmp runtime_env_error
runtime_env_copy:
    mov QWORD PTR [r15 + 8], 0
    jmp runtime_buffer_literal
runtime_env_missing:
    mov rax, -2
    jmp runtime_env_error
runtime_env_invalid:
    mov rax, -22
runtime_env_error:
    mov [r15 + 8], rax
    xor eax, eax
    jmp runtime_buffer_new
runtime_os_dir_open:
    mov rsi, rax
    mov rdi, -100
    mov edx, 0x90000             # O_DIRECTORY | O_CLOEXEC
    xor r10d, r10d
    mov eax, 257
    syscall
    ret
runtime_os_dir_next:
    push rbp
    sub rsp, 160
    mov rbp, rsp
runtime_directory_more:
    cmp QWORD PTR [rbx + 48], 0
    jne runtime_directory_empty
    mov rax, [rbx + 24]
    cmp rax, [rbx + 32]
    jb runtime_directory_entry
    mov rsi, [rbx + 16]
    add rsi, 8
    mov rdi, [rbx]
    mov edx, 8192
    mov eax, 217
    syscall
    cmp rax, -4
    je runtime_directory_more
    test rax, rax
    js runtime_directory_os_return
    jz runtime_directory_end
    mov [rbx + 32], rax
    mov QWORD PTR [rbx + 24], 0
    xor eax, eax
runtime_directory_entry:
    mov rdx, [rbx + 16]
    lea rdx, [rdx + rax + 8]
    movzx ecx, WORD PTR [rdx + 16]
    cmp ecx, 20
    jb runtime_directory_corrupt
    add rax, rcx
    cmp rax, [rbx + 32]
    ja runtime_directory_corrupt
    mov [rbx + 24], rax
    lea rsi, [rdx + 19]
    sub ecx, 19
    xor eax, eax
runtime_directory_name_length:
    cmp rax, rcx
    jae runtime_directory_corrupt
    cmp BYTE PTR [rsi + rax], 0
    je runtime_directory_name_ready
    inc rax
    jmp runtime_directory_name_length
runtime_directory_name_ready:
    test rax, rax
    jz runtime_directory_corrupt
    cmp BYTE PTR [rsi], '.'
    jne runtime_directory_classify
    cmp rax, 1
    je runtime_directory_more
    cmp rax, 2
    jne runtime_directory_classify
    cmp BYTE PTR [rsi + 1], '.'
    je runtime_directory_more
runtime_directory_classify:
    mov [rbp + 144], rax
    mov [rbp + 152], rsi
    movzx eax, BYTE PTR [rdx + 18]
    test eax, eax
    jnz runtime_directory_type
    mov rdi, [rbx]
    mov rdx, rbp
    mov r10d, 256                # AT_SYMLINK_NOFOLLOW for DT_UNKNOWN
    mov eax, 262
    syscall
    test rax, rax
    js runtime_directory_os_return
    mov eax, [rbp + 24]
    shr eax, 12
runtime_directory_type:
    mov ecx, 4
    cmp eax, 8
    jne runtime_directory_not_file
    mov ecx, 1
runtime_directory_not_file:
    cmp eax, 4
    jne runtime_directory_not_dir
    mov ecx, 2
runtime_directory_not_dir:
    cmp eax, 10
    jne runtime_directory_type_ready
    mov ecx, 3
runtime_directory_type_ready:
    mov [rbx + 40], rcx
    mov rax, [rbp + 144]
    mov rsi, [rbp + 152]
    call runtime_buffer_literal
    jmp runtime_directory_os_return
runtime_directory_corrupt:
    mov rax, -5
    jmp runtime_directory_os_return
runtime_directory_end:
    mov QWORD PTR [rbx + 48], 1
runtime_directory_empty:
    xor eax, eax
    call runtime_buffer_new
runtime_directory_os_return:
    add rsp, 160
    pop rbp
    ret
runtime_os_dir_close:
    mov rdi, [rbx]
    mov eax, 3
    syscall
    ret
# NUL-terminated argument packet (excluding argv[0]), maximum 256 arguments.
# fork + CLOEXEC error pipe reports exec errors separately from child status.
runtime_process_run:
    push rbp
    push rbx
    sub rsp, 2144
    mov rbp, rsp
    mov [rbp], rax
    mov [rbp + 8], rcx
    mov QWORD PTR [rbp + 32], 0
    mov rdx, [rcx]
    cmp rdx, 32767
    ja runtime_process_invalid
    xor esi, esi
    xor edi, edi
    lea r8, [rcx + 8]
    lea r9, [rbp + 88]
    test rdx, rdx
    jz runtime_process_arguments_ready
runtime_process_argument:
    cmp edi, 256
    jae runtime_process_invalid
    lea rax, [r8 + rsi]
    mov [r9 + rdi*8], rax
    inc edi
runtime_process_argument_scan:
    cmp rsi, rdx
    jae runtime_process_invalid
    cmp BYTE PTR [r8 + rsi], 0
    lea rsi, [rsi + 1]
    jne runtime_process_argument_scan
    cmp rsi, rdx
    jb runtime_process_argument
runtime_process_arguments_ready:
    mov QWORD PTR [r9 + rdi*8], 0
    mov rax, [rbp]
    call runtime_path
    test rax, rax
    js runtime_process_error
    mov [rbp + 80], rax
    mov rdx, [r15]
    mov rcx, [rdx]
    lea rdx, [rdx + rcx*8 + 16]
    mov [rbp + 16], rdx
    lea rdi, [rbp + 40]
    mov esi, 0x80000
    mov eax, 293
    syscall
    test rax, rax
    js runtime_process_error
    mov eax, 57
    syscall
    test rax, rax
    js runtime_process_fork_failed
    jz runtime_process_child
    mov [rbp + 24], rax
    mov edi, [rbp + 44]
    mov eax, 3
    syscall
runtime_process_read_error_pipe:
    mov edi, [rbp + 40]
    lea rsi, [rbp + 32]
    mov edx, 8
    xor eax, eax
    syscall
    cmp rax, -4
    je runtime_process_read_error_pipe
    test rax, rax
    js runtime_process_pipe_error
    test rax, rax
    jz runtime_process_close_pipe
    cmp rax, 8
    je runtime_process_close_pipe
    mov QWORD PTR [rbp + 32], -5
    jmp runtime_process_close_pipe
runtime_process_pipe_error:
    mov [rbp + 32], rax
runtime_process_close_pipe:
    mov edi, [rbp + 40]
    mov eax, 3
    syscall
runtime_process_wait:
    mov rdi, [rbp + 24]
    lea rsi, [rbp + 48]
    xor edx, edx
    xor r10d, r10d
    mov eax, 61
    syscall
    cmp rax, -4
    je runtime_process_wait
    test rax, rax
    js runtime_process_error
    mov rax, [rbp + 32]
    test rax, rax
    js runtime_process_error
    mov eax, [rbp + 48]
    mov ecx, eax
    and ecx, 127
    jnz runtime_process_signaled
    shr eax, 8
    and eax, 255
    jmp runtime_process_ok
runtime_process_signaled:
    lea eax, [rcx + 128]
runtime_process_ok:
    mov QWORD PTR [r15 + 8], 0
    jmp runtime_process_return
runtime_process_child:
    mov edi, [rbp + 40]
    mov eax, 3
    syscall
    mov rdi, [rbp + 80]
    lea rsi, [rbp + 80]
    mov rdx, [rbp + 16]
    mov eax, 59
    syscall
    mov [rbp + 32], rax
    mov edi, [rbp + 44]
    lea rsi, [rbp + 32]
    mov edx, 8
    call runtime_io_write_all
    mov edi, 127
    mov eax, 60
    syscall
    ud2
runtime_process_fork_failed:
    mov rbx, rax
    mov edi, [rbp + 40]
    mov eax, 3
    syscall
    mov edi, [rbp + 44]
    mov eax, 3
    syscall
    mov rax, rbx
    jmp runtime_process_error
runtime_process_invalid:
    mov rax, -22
runtime_process_error:
    mov [r15 + 8], rax
runtime_process_return:
    add rsp, 2144
    pop rbx
    pop rbp
    ret

runtime_dir_create:
    call runtime_path
    test rax, rax
    js runtime_directory_create_done
    mov rsi, rax
    mov rdi, -100
    mov edx, 0755
    mov eax, 258
    syscall
runtime_directory_create_done:
    mov [r15 + 8], rax
    ret

runtime_os_run_base:
    lea rsi, [rip + runtime_run_tmpdir]
    mov eax, 6
    call runtime_buffer_literal
    call runtime_env_get
    cmp QWORD PTR [r15 + 8], -2
    je runtime_run_default_base
    cmp QWORD PTR [r15 + 8], 0
    jne runtime_run_base_error
    cmp QWORD PTR [rax], 0
    jne runtime_run_base_return
runtime_run_default_base:
    lea rsi, [rip + runtime_run_tmp]
    mov eax, 4
    jmp runtime_buffer_literal
runtime_run_base_error:
    mov rax, [r15 + 8]
runtime_run_base_return:
    ret
runtime_os_run_random:
    sub rsp, 8
runtime_run_random_retry:
    mov eax, 318
    mov rdi, rsp
    mov esi, 8
    xor edx, edx
    syscall
    cmp rax, -4
    je runtime_run_random_retry
    cmp rax, 8
    jne runtime_run_random_error
    mov rax, [rsp]
    mov QWORD PTR [r15 + 8], 0
    add rsp, 8
    ret
runtime_run_random_error:
    test rax, rax
    js runtime_run_random_failed
    mov rax, -5
runtime_run_random_failed:
    mov [r15 + 8], rax
    xor eax, eax
    add rsp, 8
    ret
runtime_os_run_mkdir:
    call runtime_path
    test rax, rax
    js runtime_run_mkdir_return
    mov rsi, rax
    mov rdi, -100
    mov edx, 0700
    mov eax, 258
    syscall
runtime_run_mkdir_return:
    ret
runtime_os_run_unlink:
    call runtime_path
    test rax, rax
    js runtime_run_unlink_return
    mov rdi, rax
    mov eax, 87
    syscall
runtime_run_unlink_return:
    ret
runtime_os_run_rmdir:
    call runtime_path
    test rax, rax
    js runtime_run_rmdir_return
    mov rdi, rax
    mov eax, 84
    syscall
runtime_run_rmdir_return:
    ret
runtime_run_tmpdir: .ascii "TMPDIR"
runtime_run_tmp: .ascii "/tmp"
