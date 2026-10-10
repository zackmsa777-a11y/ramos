# Native console state: active, input/output HANDLE, saved mode DWORDs,
# repeated-key count/code. State pointer in spare writable import-data slot
# lets the OS control-handler thread restore this process's console.
runtime_terminal_start:
    push rbp
    push rbx
    sub rsp, 16
    mov rbp, rsp
    mov rbx, [r15 + 112]
    test rbx, rbx
    jnz runtime_terminal_have_state
    mov eax, 64
    call runtime_buffer_new
    mov [r15 + 112], rax
    mov rbx, rax
runtime_terminal_have_state:
    add rbx, 8
    cmp QWORD PTR [rbx], 0
    jne runtime_terminal_already
    mov ecx, -10
    API GetStdHandle
    mov [rbx + 8], rax
    mov rcx, rax
    lea rdx, [rbx + 24]
    API GetConsoleMode
    test eax, eax
    jz runtime_terminal_notty
    mov ecx, -11
    API GetStdHandle
    mov [rbx + 16], rax
    mov rcx, rax
    lea rdx, [rbx + 28]
    API GetConsoleMode
    test eax, eax
    jz runtime_terminal_notty
    mov [rip + terminal_process_state], r15
    lea rcx, [rip + runtime_terminal_control]
    mov edx, 1
    API SetConsoleCtrlHandler
    test eax, eax
    jz runtime_terminal_start_os_error
    mov QWORD PTR [rbx], 1
    mov QWORD PTR [rbx + 32], 0
    mov rcx, [rbx + 16]
    mov edx, [rbx + 28]
    or edx, 5                         # VT processing and processed output
    API SetConsoleMode
    test eax, eax
    jz runtime_terminal_start_rollback
    mov rcx, [rbx + 8]
    mov edx, [rbx + 24]
    and edx, ~0x27f                   # no processed/line/echo/mouse/quickedit/VT input
    or edx, 0x80                      # ENABLE_EXTENDED_FLAGS
    API SetConsoleMode
    test eax, eax
    jz runtime_terminal_start_rollback
    xor eax, eax
    jmp runtime_terminal_start_done
runtime_terminal_start_rollback:
    call runtime_errno
    mov [rbp], rax
    call runtime_terminal_stop
    mov rax, [rbp]
    jmp runtime_terminal_start_done
runtime_terminal_start_os_error:
    call runtime_errno
    jmp runtime_terminal_start_done
runtime_terminal_notty:
    mov rax, -25
    jmp runtime_terminal_start_done
runtime_terminal_already:
    mov rax, -16
runtime_terminal_start_done:
    mov [r15 + 8], rax
    add rsp, 16
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
    lea rsi, [rip + runtime_terminal_reset]
    mov edx, runtime_terminal_reset_end - runtime_terminal_reset
    call runtime_stdout_write
    mov rcx, [rbx + 8]
    mov edx, [rbx + 24]
    API SetConsoleMode
    test eax, eax
    jnz runtime_terminal_restore_output
    call runtime_errno
    mov [rbp], rax
runtime_terminal_restore_output:
    mov rcx, [rbx + 16]
    mov edx, [rbx + 28]
    API SetConsoleMode
    test eax, eax
    jnz runtime_terminal_remove_handler
    call runtime_errno
    mov [rbp], rax
runtime_terminal_remove_handler:
    lea rcx, [rip + runtime_terminal_control]
    xor edx, edx
    API SetConsoleCtrlHandler
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
    pop QWORD PTR [r15 + 8]
    pop rdi
    pop rsi
    pop rdx
    pop rcx
    pop rax
    ret
runtime_terminal_control:
    push rbx
    push rbp
    push rsi
    push rdi
    push r12
    push r13
    push r14
    push r15
    mov r15, [rip + terminal_process_state]
    test r15, r15
    jz runtime_terminal_control_done
    call runtime_terminal_cleanup
runtime_terminal_control_done:
    pop r15
    pop r14
    pop r13
    pop r12
    pop rdi
    pop rsi
    pop rbp
    pop rbx
    xor eax, eax                       # allow the default handler to terminate
    ret
runtime_terminal_reset: .ascii "\033[0m\033[?25h\033[?1049l"
runtime_terminal_reset_end:
runtime_terminal_width:
    mov eax, 14
    mov edx, 10
    jmp runtime_terminal_dimension
runtime_terminal_height:
    mov eax, 16
    mov edx, 12
runtime_terminal_dimension:
    push rbp
    sub rsp, 40
    mov rbp, rsp
    mov [rbp + 24], rax
    mov [rbp + 32], rdx
    mov ecx, -11
    API GetStdHandle
    mov rcx, rax
    mov rdx, rbp
    API GetConsoleScreenBufferInfo
    test eax, eax
    jz runtime_terminal_dimension_error
    mov rcx, [rbp + 24]
    mov rdx, [rbp + 32]
    movsx eax, WORD PTR [rbp + rcx]
    movsx edx, WORD PTR [rbp + rdx]
    sub eax, edx
    inc eax
    mov QWORD PTR [r15 + 8], 0
    jmp runtime_terminal_dimension_done
runtime_terminal_dimension_error:
    mov QWORD PTR [r15 + 8], -25
    xor eax, eax
runtime_terminal_dimension_done:
    add rsp, 40
    pop rbp
    ret
runtime_terminal_key:
    push rbp
    push rbx
    sub rsp, 48
    mov rbp, rsp
    cmp rax, -1
    jl runtime_terminal_key_invalid
    cmp rax, 2147483647
    jg runtime_terminal_key_invalid
    mov [rbp + 24], rax
    mov rbx, [r15 + 112]
    test rbx, rbx
    jz runtime_terminal_key_notty
    add rbx, 8
    cmp QWORD PTR [rbx], 0
    je runtime_terminal_key_notty
    cmp QWORD PTR [rbx + 32], 0
    je runtime_terminal_key_clock
    dec QWORD PTR [rbx + 32]
    mov rax, [rbx + 40]
    jmp runtime_terminal_key_ok
runtime_terminal_key_clock:
    API GetTickCount64
    mov [rbp + 32], rax
runtime_terminal_key_wait:
    mov rdx, [rbp + 24]
    cmp rdx, -1
    je runtime_terminal_key_wait_ready
    API GetTickCount64
    sub rax, [rbp + 32]
    mov rdx, [rbp + 24]
    sub rdx, rax
    jns runtime_terminal_key_wait_ready
    xor edx, edx
runtime_terminal_key_wait_ready:
    mov rcx, [rbx + 8]
    API WaitForSingleObject
    cmp eax, 258
    je runtime_terminal_key_timeout
    test eax, eax
    jnz runtime_terminal_key_os_error
    mov rcx, [rbx + 8]
    mov rdx, rbp
    mov r8d, 1
    lea r9, [rbp + 20]
    API ReadConsoleInputW
    test eax, eax
    jz runtime_terminal_key_os_error
    cmp WORD PTR [rbp], 1              # KEY_EVENT
    jne runtime_terminal_key_wait
    cmp DWORD PTR [rbp + 4], 0         # key down only
    je runtime_terminal_key_wait
    movzx eax, WORD PTR [rbp + 10]     # virtual key code
    cmp eax, 0x26
    je runtime_terminal_key_up
    cmp eax, 0x28
    je runtime_terminal_key_down
    cmp eax, 0x27
    je runtime_terminal_key_right
    cmp eax, 0x25
    je runtime_terminal_key_left
    cmp eax, 0x24
    je runtime_terminal_key_home
    cmp eax, 0x23
    je runtime_terminal_key_end
    cmp eax, 0x21
    je runtime_terminal_key_pageup
    cmp eax, 0x22
    je runtime_terminal_key_pagedown
    cmp eax, 0x2e
    je runtime_terminal_key_delete
    movzx eax, WORD PTR [rbp + 14]
    test eax, eax
    jz runtime_terminal_key_wait
    cmp eax, 127                       # navigation/ASCII input in first TUI API
    ja runtime_terminal_key_wait
    jmp runtime_terminal_key_repeat
runtime_terminal_key_up: mov eax, 256
    jmp runtime_terminal_key_repeat
runtime_terminal_key_down: mov eax, 257
    jmp runtime_terminal_key_repeat
runtime_terminal_key_right: mov eax, 258
    jmp runtime_terminal_key_repeat
runtime_terminal_key_left: mov eax, 259
    jmp runtime_terminal_key_repeat
runtime_terminal_key_home: mov eax, 260
    jmp runtime_terminal_key_repeat
runtime_terminal_key_end: mov eax, 261
    jmp runtime_terminal_key_repeat
runtime_terminal_key_pageup: mov eax, 262
    jmp runtime_terminal_key_repeat
runtime_terminal_key_pagedown: mov eax, 263
    jmp runtime_terminal_key_repeat
runtime_terminal_key_delete: mov eax, 264
runtime_terminal_key_repeat:
    mov [rbx + 40], rax
    movzx edx, WORD PTR [rbp + 8]
    test edx, edx
    jz runtime_terminal_key_ok
    dec edx
    mov [rbx + 32], rdx
runtime_terminal_key_ok:
    mov QWORD PTR [r15 + 8], 0
    jmp runtime_terminal_key_done
runtime_terminal_key_invalid:
    mov rax, -22
    jmp runtime_terminal_key_error
runtime_terminal_key_notty:
    mov rax, -25
    jmp runtime_terminal_key_error
runtime_terminal_key_os_error:
    call runtime_errno
    jmp runtime_terminal_key_error
runtime_terminal_key_timeout:
    xor eax, eax
runtime_terminal_key_error:
    mov [r15 + 8], rax
    mov rax, -1
runtime_terminal_key_done:
    add rsp, 48
    pop rbx
    pop rbp
    ret
