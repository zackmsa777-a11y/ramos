# Linux x86-64 tty boundary. Managed 256-byte saved state is rooted at +112.
# State payload: active +0, original termios +8, working termios +48,
# old sigactions +96/+128/+160, installed count +192.
runtime_terminal_start:
    push rbp
    push rbx
    sub rsp, 80
    mov rbp, rsp
    mov rbx, [r15 + 112]
    test rbx, rbx
    jnz runtime_terminal_have_state
    mov eax, 256
    call runtime_buffer_new
    mov [r15 + 112], rax
    mov rbx, rax
runtime_terminal_have_state:
    add rbx, 8
    cmp QWORD PTR [rbx], 0
    jne runtime_terminal_already
    mov eax, 16
    xor edi, edi
    mov esi, 0x5401
    lea rdx, [rbx + 8]
    syscall
    test rax, rax
    js runtime_terminal_start_done
    mov eax, 16
    mov edi, 1
    mov esi, 0x5401
    lea rdx, [rbp + 40]
    syscall
    test rax, rax
    js runtime_terminal_start_done
    lea rsi, [rbx + 8]
    lea rdi, [rbx + 48]
    mov ecx, 36
    rep movsb
    and DWORD PTR [rbx + 48], ~0x56b
    and DWORD PTR [rbx + 60], ~0x800b
    mov BYTE PTR [rbx + 70], 0          # VTIME
    mov BYTE PTR [rbx + 71], 1          # VMIN
    lea rax, [rip + runtime_terminal_signal]
    mov [rbp], rax
    mov QWORD PTR [rbp + 8], 0x4000000  # SA_RESTORER
    lea rax, [rip + runtime_signal_restorer]
    mov [rbp + 16], rax
    mov QWORD PTR [rbp + 24], 0
    mov QWORD PTR [rbx], 1
    mov QWORD PTR [rbx + 192], 0
runtime_terminal_install_signal:
    mov rcx, [rbx + 192]
    cmp rcx, 3
    jae runtime_terminal_set_mode
    lea rax, [rip + runtime_terminal_signals]
    mov edi, [rax + rcx*4]
    shl rcx, 5
    lea rdx, [rbx + rcx + 96]
    mov rsi, rbp
    mov r10d, 8
    mov eax, 13
    syscall
    test rax, rax
    js runtime_terminal_start_rollback
    inc QWORD PTR [rbx + 192]
    jmp runtime_terminal_install_signal
runtime_terminal_set_mode:
    mov eax, 16
    xor edi, edi
    mov esi, 0x5402
    lea rdx, [rbx + 48]
    syscall
    test rax, rax
    js runtime_terminal_start_rollback
    xor eax, eax
    jmp runtime_terminal_start_done
runtime_terminal_start_rollback:
    mov [rbp + 32], rax
    call runtime_terminal_stop
    mov rax, [rbp + 32]
    jmp runtime_terminal_start_done
runtime_terminal_already:
    mov rax, -16
runtime_terminal_start_done:
    mov [r15 + 8], rax
    add rsp, 80
    pop rbx
    pop rbp
    ret
runtime_terminal_stop:
    push rbp
    push rbx
    sub rsp, 16
    mov rbp, rsp
    mov QWORD PTR [rbp], 0
    mov rbx, [r15 + 112]
    test rbx, rbx
    jz runtime_terminal_stop_done
    add rbx, 8
    cmp QWORD PTR [rbx], 0
    je runtime_terminal_stop_done
    mov QWORD PTR [rbx], 0
    mov eax, 16
    xor edi, edi
    mov esi, 0x5402
    lea rdx, [rbx + 8]
    syscall
    mov [rbp], rax
runtime_terminal_restore_signals:
    mov rcx, [rbx + 192]
    test rcx, rcx
    jz runtime_terminal_restore_screen
    dec rcx
    mov [rbx + 192], rcx
    lea rax, [rip + runtime_terminal_signals]
    mov edi, [rax + rcx*4]
    shl rcx, 5
    lea rsi, [rbx + rcx + 96]
    xor edx, edx
    mov r10d, 8
    mov eax, 13
    syscall
    jmp runtime_terminal_restore_signals
runtime_terminal_restore_screen:
    lea rsi, [rip + runtime_terminal_reset]
    mov edx, runtime_terminal_reset_end - runtime_terminal_reset
    call runtime_stdout_write
runtime_terminal_stop_done:
    mov rax, [rbp]
    mov [r15 + 8], rax
    add rsp, 16
    pop rbx
    pop rbp
    ret
runtime_terminal_cleanup:
    push rax
    push rcx
    push rdx
    push rsi
    push rdi
    push QWORD PTR [r15 + 8]
    call runtime_terminal_stop
    call runtime_gui_cleanup
    pop QWORD PTR [r15 + 8]
    pop rdi
    pop rsi
    pop rdx
    pop rcx
    pop rax
    ret
runtime_terminal_signal:
    push rdi
    call runtime_terminal_stop
    pop rdi
    add edi, 128
    mov eax, 231
    syscall
    ud2
runtime_signal_restorer:
    mov eax, 15
    syscall
    ud2
runtime_terminal_signals: .long 1, 2, 15
runtime_terminal_reset: .ascii "\033[0m\033[?25h\033[?1049l"
runtime_terminal_reset_end:
runtime_terminal_width:
    mov ecx, 2
    jmp runtime_terminal_dimension
runtime_terminal_height:
    xor ecx, ecx
runtime_terminal_dimension:
    push rcx
    sub rsp, 8
    mov eax, 16
    mov edi, 1
    mov esi, 0x5413
    mov rdx, rsp
    syscall
    test rax, rax
    js runtime_terminal_dimension_error
    mov rcx, [rsp + 8]
    movzx eax, WORD PTR [rsp + rcx]
    mov QWORD PTR [r15 + 8], 0
    jmp runtime_terminal_dimension_done
runtime_terminal_dimension_error:
    mov [r15 + 8], rax
    xor eax, eax
runtime_terminal_dimension_done:
    add rsp, 16
    ret
runtime_terminal_key:
    push rbp
    sub rsp, 16
    mov rbp, rsp
    cmp rax, -1
    jl runtime_terminal_key_invalid
    cmp rax, 2147483647
    jg runtime_terminal_key_invalid
    mov [rbp + 8], rax
    mov rcx, [r15 + 112]
    test rcx, rcx
    jz runtime_terminal_key_notty
    cmp QWORD PTR [rcx + 8], 0
    je runtime_terminal_key_notty
    mov rax, 0x100000000
    mov [rbp], rax   # fd=0, events=POLLIN, revents=0
runtime_terminal_key_poll:
    mov rdi, rbp
    mov esi, 1
    mov rdx, [rbp + 8]
    mov eax, 7
    syscall
    cmp rax, -4
    je runtime_terminal_key_poll
    test rax, rax
    js runtime_terminal_key_error
    jz runtime_terminal_key_timeout
runtime_terminal_key_read:
    xor edi, edi
    mov rsi, rbp
    mov edx, 1
    xor eax, eax
    syscall
    cmp rax, -4
    je runtime_terminal_key_read
    test rax, rax
    js runtime_terminal_key_error
    jz runtime_terminal_key_eof
    movzx eax, BYTE PTR [rbp]
    mov QWORD PTR [r15 + 8], 0
    jmp runtime_terminal_key_done
runtime_terminal_key_invalid:
    mov rax, -22
    jmp runtime_terminal_key_error
runtime_terminal_key_notty:
    mov rax, -25
    jmp runtime_terminal_key_error
runtime_terminal_key_eof:
    mov rax, -32
    jmp runtime_terminal_key_error
runtime_terminal_key_timeout:
    xor eax, eax
runtime_terminal_key_error:
    mov [r15 + 8], rax
    mov rax, -1
runtime_terminal_key_done:
    add rsp, 16
    pop rbp
    ret

# Nonnegative CLOCK_MONOTONIC milliseconds; -1 and io_error on OS/range failure.
# No allocation, console requirement, wall-clock epoch or dynamic dependency.
runtime_monotonic_ms:
    sub rsp, 16
    mov eax, 228
    mov edi, 1
    mov rsi, rsp
    syscall
    test rax, rax
    js runtime_monotonic_ms_fail
    mov rax, [rsp]
    test rax, rax
    js runtime_monotonic_ms_range
    imul rax, rax, 1000
    jo runtime_monotonic_ms_range
    mov rcx, rax
    mov rax, [rsp + 8]
    cmp rax, 1000000000
    jae runtime_monotonic_ms_range
    xor edx, edx
    mov esi, 1000000
    div rsi
    add rax, rcx
    jo runtime_monotonic_ms_range
    mov QWORD PTR [r15 + 8], 0
    add rsp, 16
    ret
runtime_monotonic_ms_range:
    mov rax, -75
runtime_monotonic_ms_fail:
    mov [r15 + 8], rax
    mov rax, -1
    add rsp, 16
    ret
