# Synchronous native WinHTTP. API table is lazily rooted in system state;
# per-request session/connection/request handles close on every return path.
.equ WH_WinHttpOpen, 4224
.equ WH_WinHttpConnect, 4232
.equ WH_WinHttpCrackUrl, 4240
.equ WH_WinHttpOpenRequest, 4248
.equ WH_WinHttpSetTimeouts, 4256
.equ WH_WinHttpSetOption, 4264
.equ WH_WinHttpAddRequestHeaders, 4272
.equ WH_WinHttpSendRequest, 4280
.equ WH_WinHttpReceiveResponse, 4288
.equ WH_WinHttpQueryHeaders, 4296
.equ WH_WinHttpReadData, 4304
.equ WH_WinHttpCloseHandle, 4312
.macro WH name
    mov rax, [r15 + 136]
    mov rax, [rax + 8 + WH_\name]
    call runtime_api
.endm
runtime_http_windows_initialize:
    push rbp
    push rbx
    push rsi
    push rdi
    call runtime_system_table
    lea rdi, [rax + 8 + 4224]
    cmp QWORD PTR [rdi + 88], 0
    jne runtime_http_windows_initialized
    # Keep exactly one process-owned DLL reference, including partial API
    # initialization. Retrying an unavailable export must not reload the DLL.
    mov rbx, [rdi + 96]
    test rbx, rbx
    jnz runtime_http_windows_have_module
    lea rcx, [rip + runtime_http_dll]
    xor edx, edx
    mov r8d, 0x800                  # System32 only.
    API LoadLibraryExW
    test rax, rax
    jz runtime_http_windows_missing
    mov rbx, rax
    mov [rdi + 96], rax
runtime_http_windows_have_module:
    lea rsi, [rip + runtime_http_windows_names]
runtime_http_windows_load:
    mov rcx, rbx
    mov rdx, rsi
    API GetProcAddress
    test rax, rax
    jz runtime_http_windows_missing
    mov [rdi], rax
    add rdi, 8
runtime_http_windows_load_next:
    cmp BYTE PTR [rsi], 0
    lea rsi, [rsi + 1]
    jne runtime_http_windows_load_next
    cmp BYTE PTR [rsi], 0
    jne runtime_http_windows_load
runtime_http_windows_initialized:
    xor eax, eax
    jmp runtime_http_windows_init_done
runtime_http_windows_missing:
    mov rax, -38
runtime_http_windows_init_done:
    pop rdi
    pop rsi
    pop rbx
    pop rbp
    ret
runtime_http_request:
    push rbp
    push rbx
    push rsi
    push rdi
    sub rsp, 320
    mov rbp, rsp
    mov [rbp], rax
    mov [rbp + 8], rcx
    mov [rbp + 16], rdx
    mov QWORD PTR [rbp + 48], 0
    mov QWORD PTR [rbp + 56], 0
    mov QWORD PTR [rbp + 64], 0
    call runtime_http_validate
    test rax, rax
    js runtime_http_windows_done
    call runtime_http_windows_initialize
    test rax, rax
    js runtime_http_windows_done
    # The validated packet text is ASCII. Convert all terminated fields in one
    # rooted buffer; body bytes are never text-decoded.
    mov rax, [rbp]
    mov rax, [rax]
    sub rax, 32
    shl rax, 1
    call runtime_buffer_new
    mov [rbp + 24], rax
    lea rdi, [rax + 8]
    mov rax, [rbp]
    mov rcx, [rax]
    sub rcx, 32
    lea rsi, [rax + 40]
runtime_http_windows_wide:
    lodsb
    movzx eax, al
    stosw
    loop runtime_http_windows_wide
    lea rdi, [rbp + 128]
    mov ecx, 13
    xor eax, eax
    rep stosq
    mov DWORD PTR [rbp + 128], 104
    mov DWORD PTR [rbp + 160], -1    # Host length.
    mov DWORD PTR [rbp + 208], -1    # Path length.
    mov DWORD PTR [rbp + 224], -1    # Extra/query length.
    mov rcx, [rbp + 24]
    add rcx, 8
    xor edx, edx
    xor r8d, r8d
    lea r9, [rbp + 128]
    WH WinHttpCrackUrl
    test eax, eax
    jz runtime_http_windows_invalid
    mov eax, [rbp + 148]            # Scheme HTTP=1 / HTTPS=2.
    cmp eax, 1
    je runtime_http_windows_host
    cmp eax, 2
    jne runtime_http_windows_invalid
runtime_http_windows_host:
    mov eax, [rbp + 160]
    test eax, eax
    jz runtime_http_windows_invalid
    lea rax, [rax*2 + 2]
    call runtime_buffer_new
    mov [rbp + 32], rax
    lea rdi, [rax + 8]
    mov rsi, [rbp + 152]
    mov ecx, [rbp + 160]
    rep movsw
    mov eax, [rbp + 208]
    add eax, [rbp + 224]
    lea rax, [rax*2 + 4]
    call runtime_buffer_new
    mov [rbp + 40], rax
    lea rdi, [rax + 8]
    cmp DWORD PTR [rbp + 208], 0
    jne runtime_http_windows_path
    mov ax, 47
    stosw
runtime_http_windows_path:
    mov rsi, [rbp + 200]
    mov ecx, [rbp + 208]
    rep movsw
    mov rsi, [rbp + 216]
    mov ecx, [rbp + 224]
    rep movsw
    lea rcx, [rip + runtime_http_agent]
    mov edx, 1                     # Direct; no implicit proxy configuration.
    xor r8d, r8d
    xor r9d, r9d
    xor r10d, r10d
    WH WinHttpOpen
    test rax, rax
    jz runtime_http_windows_native_error
    mov [rbp + 48], rax
    mov rcx, rax
    mov rax, [rbp]
    mov edx, [rax + 8]
    mov r8d, edx
    mov r9d, edx
    mov r10d, edx
    WH WinHttpSetTimeouts
    test eax, eax
    jz runtime_http_windows_native_error
    mov DWORD PTR [rbp + 96], 0x2800 # TLS 1.2/1.3; older OS may only know 1.2.
    mov rcx, [rbp + 48]
    mov edx, 84
    lea r8, [rbp + 96]
    mov r9d, 4
    WH WinHttpSetOption
    test eax, eax
    jnz runtime_http_windows_connect
    API GetLastError
    cmp eax, 87
    jne runtime_http_windows_native_error
    mov DWORD PTR [rbp + 96], 0x800
    mov rcx, [rbp + 48]
    mov edx, 84
    lea r8, [rbp + 96]
    mov r9d, 4
    WH WinHttpSetOption
    test eax, eax
    jz runtime_http_windows_native_error
runtime_http_windows_connect:
    mov rcx, [rbp + 48]
    mov rdx, [rbp + 32]
    add rdx, 8
    movzx r8d, WORD PTR [rbp + 164]
    xor r9d, r9d
    WH WinHttpConnect
    test rax, rax
    jz runtime_http_windows_native_error
    mov [rbp + 56], rax
    mov rcx, rax
    lea rdx, [rip + runtime_http_get]
    mov rax, [rbp]
    cmp QWORD PTR [rax + 16], 0
    je runtime_http_windows_open
    lea rdx, [rip + runtime_http_post]
runtime_http_windows_open:
    mov r8, [rbp + 40]
    add r8, 8
    xor r9d, r9d
    xor r10d, r10d
    xor r11d, r11d
    xor esi, esi
    cmp DWORD PTR [rbp + 148], 2
    jne runtime_http_windows_open_call
    mov esi, 0x800000               # WINHTTP_FLAG_SECURE.
runtime_http_windows_open_call:
    WH WinHttpOpenRequest
    test rax, rax
    jz runtime_http_windows_native_error
    mov [rbp + 64], rax
    # Do not disable certificate chain/name checks. Never follow redirects.
    mov DWORD PTR [rbp + 96], 0
    mov rcx, rax
    mov edx, 88                     # WINHTTP_OPTION_REDIRECT_POLICY.
    lea r8, [rbp + 96]
    mov r9d, 4
    WH WinHttpSetOption
    test eax, eax
    jz runtime_http_windows_native_error
    mov DWORD PTR [rbp + 96], 4      # Disable automatic authentication retries.
    mov rcx, [rbp + 64]
    mov edx, 63
    lea r8, [rbp + 96]
    mov r9d, 4
    WH WinHttpSetOption
    test eax, eax
    jz runtime_http_windows_native_error
    mov rax, [rbp]
    mov rcx, [rax + 24]
    inc rcx
    mov rdx, [rbp + 24]
    lea rdx, [rdx + rcx*2 + 8]
    mov [rbp + 80], rdx
    mov rax, [rax + 32]
    mov [rbp + 88], rax
runtime_http_windows_header_each:
    cmp QWORD PTR [rbp + 88], 0
    je runtime_http_windows_send
    mov rcx, [rbp + 64]
    mov rdx, [rbp + 80]
    mov r8d, -1
    mov r9d, 0x20000000             # Add this validated header line.
    WH WinHttpAddRequestHeaders
    test eax, eax
    jz runtime_http_windows_native_error
    mov rdx, [rbp + 80]
runtime_http_windows_header_skip:
    cmp WORD PTR [rdx], 0
    lea rdx, [rdx + 2]
    jne runtime_http_windows_header_skip
    mov [rbp + 80], rdx
    dec QWORD PTR [rbp + 88]
    jmp runtime_http_windows_header_each
runtime_http_windows_send:
    mov rcx, [rbp + 64]
    xor edx, edx
    xor r8d, r8d
    mov rax, [rbp + 8]
    lea r9, [rax + 8]
    mov r10, [rax]
    mov r11, r10
    mov rax, [rbp]
    cmp QWORD PTR [rax + 16], 1
    je runtime_http_windows_send_call
    xor r9d, r9d
    xor r10d, r10d
    xor r11d, r11d
runtime_http_windows_send_call:
    xor esi, esi
    WH WinHttpSendRequest
    test eax, eax
    jz runtime_http_windows_native_error
    mov rcx, [rbp + 64]
    xor edx, edx
    WH WinHttpReceiveResponse
    test eax, eax
    jz runtime_http_windows_native_error
    mov DWORD PTR [rbp + 244], 4
    mov rcx, [rbp + 64]
    mov edx, 0x20000013
    xor r8d, r8d
    lea r9, [rbp + 240]
    lea r10, [rbp + 244]
    xor r11d, r11d
    WH WinHttpQueryHeaders
    test eax, eax
    jz runtime_http_windows_native_error
runtime_http_windows_read:
    mov rax, [rbp + 16]
    mov r8, [rax]
    sub r8, 8
    sub r8, [rax + 8]
    cmp r8, 16384
    jbe runtime_http_windows_read_size
    mov r8d, 16384
runtime_http_windows_read_size:
    lea rdx, [rax + 16]
    add rdx, [rax + 8]
    mov [rbp + 256], r8
    test r8, r8
    jnz runtime_http_windows_read_call
    lea rdx, [rbp + 112]            # Probe one byte to distinguish EOF/full.
    mov r8d, 1
runtime_http_windows_read_call:
    mov rcx, [rbp + 64]
    lea r9, [rbp + 248]
    WH WinHttpReadData
    test eax, eax
    jz runtime_http_windows_native_error
    mov eax, [rbp + 248]
    test eax, eax
    jz runtime_http_windows_success
    cmp rax, [rbp + 256]
    ja runtime_http_windows_large
    mov rdx, [rbp + 16]
    add [rdx + 8], rax
    jmp runtime_http_windows_read
runtime_http_windows_success:
    mov eax, [rbp + 240]
    jmp runtime_http_windows_done
runtime_http_windows_native_error:
    API GetLastError
    cmp eax, 12002
    je runtime_http_windows_timeout
    cmp eax, 12175
    je runtime_http_windows_tls
    cmp eax, 12007
    je runtime_http_windows_dns
    cmp eax, 12029
    je runtime_http_windows_connect_error
    mov rax, -5
    jmp runtime_http_windows_done
runtime_http_windows_timeout:
    mov rax, -110
    jmp runtime_http_windows_done
runtime_http_windows_tls:
    mov rax, -13
    jmp runtime_http_windows_done
runtime_http_windows_dns:
    mov rax, -113
    jmp runtime_http_windows_done
runtime_http_windows_connect_error:
    mov rax, -111
    jmp runtime_http_windows_done
runtime_http_windows_large:
    mov rax, -27
    jmp runtime_http_windows_done
runtime_http_windows_invalid:
    mov rax, -22
runtime_http_windows_done:
    mov [rbp + 72], rax
    mov rcx, [rbp + 64]
    test rcx, rcx
    jz runtime_http_windows_close_connection
    WH WinHttpCloseHandle
runtime_http_windows_close_connection:
    mov rcx, [rbp + 56]
    test rcx, rcx
    jz runtime_http_windows_close_session
    WH WinHttpCloseHandle
runtime_http_windows_close_session:
    mov rcx, [rbp + 48]
    test rcx, rcx
    jz runtime_http_windows_return
    WH WinHttpCloseHandle
runtime_http_windows_return:
    mov rax, [rbp + 72]
    mov QWORD PTR [r15 + 8], 0
    test rax, rax
    jns runtime_http_windows_ok
    mov [r15 + 8], rax
    mov rdx, [rbp + 16]
    cmp QWORD PTR [rdx], 8
    jb runtime_http_windows_ok
    mov QWORD PTR [rdx + 8], 0
runtime_http_windows_ok:
    add rsp, 320
    pop rdi
    pop rsi
    pop rbx
    pop rbp
    ret
runtime_http_windows_names:
.asciz "WinHttpOpen", "WinHttpConnect", "WinHttpCrackUrl", "WinHttpOpenRequest"
.asciz "WinHttpSetTimeouts", "WinHttpSetOption", "WinHttpAddRequestHeaders"
.asciz "WinHttpSendRequest", "WinHttpReceiveResponse", "WinHttpQueryHeaders"
.asciz "WinHttpReadData", "WinHttpCloseHandle"
.byte 0
.balign 2
runtime_http_dll: .short 119,105,110,104,116,116,112,46,100,108,108,0
runtime_http_agent: .short 82,97,109,111,115,47,48,46,50,54,0
runtime_http_get: .short 71,69,84,0
runtime_http_post: .short 80,79,83,84,0
