runtime_os_stream_open:
    mov rcx, rax
    mov edx, 0x80000000                 # GENERIC_READ
    mov r10d, 3                        # OPEN_EXISTING
    cmp QWORD PTR [rbp + 8], 0
    je runtime_os_stream_flags_ready
    mov edx, 0x40000000                 # GENERIC_WRITE
    mov r10d, 1                        # CREATE_NEW
    cmp QWORD PTR [rbp + 8], 1
    je runtime_os_stream_flags_ready
    mov edx, 4                         # FILE_APPEND_DATA, writes atomically append
    mov r10d, 4                        # OPEN_ALWAYS
runtime_os_stream_flags_ready:
    mov r8d, 7
    xor r9d, r9d
    mov r11d, 0x80
    xor esi, esi
    API CreateFileW
    cmp rax, -1
    je runtime_os_stream_open_error
    mov [rbp + 24], rax
    mov rcx, rax
    API GetFileType
    cmp eax, 1
    jne runtime_os_stream_invalid
    mov rcx, [rbp + 24]
    lea rdx, [rbp + 48]
    API GetFileInformationByHandle
    test eax, eax
    jz runtime_os_stream_open_error
    test DWORD PTR [rbp + 48], 0x10
    jnz runtime_os_stream_invalid
    mov eax, [rbp + 76]
    mov [rbp + 176], rax
    mov eax, [rbp + 92]
    shl rax, 32
    mov edx, [rbp + 96]
    or rax, rdx
    mov [rbp + 184], rax
    xor eax, eax
    ret
runtime_os_stream_invalid:
    mov rax, -22
    ret
runtime_os_stream_open_error:
    jmp runtime_errno
runtime_os_stream_read:
    push rbp
    sub rsp, 16
    mov rbp, rsp
    mov r8, rdx
    mov rdx, rsi
    mov rcx, rdi
    lea r9, [rbp]
    xor r10d, r10d
    API ReadFile
    test eax, eax
    jz runtime_os_stream_read_error
    mov eax, [rbp]
    jmp runtime_os_stream_read_done
runtime_os_stream_read_error:
    call runtime_errno
runtime_os_stream_read_done:
    add rsp, 16
    pop rbp
    ret
runtime_os_stream_write:
    push rbp
    push rbx
    sub rsp, 16
    mov rbp, rsp
    mov rbx, rdx
runtime_os_stream_write_more:
    test rbx, rbx
    jz runtime_os_stream_write_ok
    mov rcx, rdi
    mov rdx, rsi
    mov r8, rbx
    lea r9, [rbp]
    xor r10d, r10d
    API WriteFile
    test eax, eax
    jz runtime_os_stream_write_error
    mov eax, [rbp]
    test eax, eax
    jz runtime_os_stream_write_zero
    add rsi, rax
    sub rbx, rax
    jmp runtime_os_stream_write_more
runtime_os_stream_write_error:
    call runtime_errno
    jmp runtime_os_stream_write_done
runtime_os_stream_write_zero:
    mov rax, -5
    jmp runtime_os_stream_write_done
runtime_os_stream_write_ok:
    xor eax, eax
runtime_os_stream_write_done:
    add rsp, 16
    pop rbx
    pop rbp
    ret
runtime_stdout_write:
    push rsi
    push rdx
    mov ecx, -11
    API GetStdHandle
    mov rdi, rax
    pop rdx
    pop rsi
    jmp runtime_os_stream_write
runtime_os_stream_close:
    mov rcx, rdi
    API CloseHandle
    test eax, eax
    jz runtime_os_stream_close_error
    xor eax, eax
    ret
runtime_os_stream_close_error:
    jmp runtime_errno
runtime_os_stream_seek:
    push rbp
    sub rsp, 16
    mov rbp, rsp
    mov rcx, rdi
    mov rdx, rax
    lea r8, [rbp]
    xor r9d, r9d
    API SetFilePointerEx
    test eax, eax
    jz runtime_os_stream_seek_error
    mov rax, [rbp]
    jmp runtime_os_stream_seek_done
runtime_os_stream_seek_error:
    call runtime_errno
runtime_os_stream_seek_done:
    add rsp, 16
    pop rbp
    ret
