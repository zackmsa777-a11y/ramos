# Linux HTTP uses libcurl directly through the optional ELF import table.
# Callbacks only copy into caller-owned bounded buffers; no Ramos allocation.
.equ HC_curl_global_init, 0x600000 + 520
.equ HC_curl_global_cleanup, 0x600000 + 528
.equ HC_curl_easy_init, 0x600000 + 536
.equ HC_curl_easy_setopt, 0x600000 + 544
.equ HC_curl_easy_perform, 0x600000 + 552
.equ HC_curl_easy_getinfo, 0x600000 + 560
.equ HC_curl_easy_cleanup, 0x600000 + 568
.equ HC_curl_slist_append, 0x600000 + 576
.equ HC_curl_slist_free_all, 0x600000 + 584
.equ HC_getenv, 0x600000 + 592
.macro HC name
    mov r11d, HC_\name
    call runtime_lg_call
.endm
.macro HTTP_OPTION number
    mov rdi, rbx
    mov esi, \number
    xor eax, eax                    # SysV variadic SSE argument count.
    HC curl_easy_setopt
    test eax, eax
    jnz runtime_http_linux_io
.endm
runtime_http_request:
    push rbp
    push rbx
    sub rsp, 128
    mov rbp, rsp
    mov [rbp], rax                  # Managed headers stay rooted on stack.
    mov [rbp + 8], rcx
    mov [rbp + 16], rdx
    mov QWORD PTR [rbp + 24], 0      # Header slist.
    mov QWORD PTR [rbp + 32], 0      # Write callback: output handle.
    mov QWORD PTR [rbp + 40], 0      # Write overflow flag.
    mov QWORD PTR [rbp + 48], 0      # Curl handle.
    mov QWORD PTR [rbp + 56], 0      # Global init succeeded.
    mov QWORD PTR [rbp + 64], 0      # Result / error.
    call runtime_http_validate
    test rax, rax
    js runtime_http_linux_done
    mov [rbp + 72], r8
    mov [rbp + 80], r9
    mov rax, [rbp + 16]
    mov [rbp + 32], rax
    mov edi, 3
    HC curl_global_init
    test eax, eax
    jnz runtime_http_linux_unavailable
    mov QWORD PTR [rbp + 56], 1
    HC curl_easy_init
    test rax, rax
    jz runtime_http_linux_io
    mov rbx, rax
    mov [rbp + 48], rax
    lea rdx, [rip + runtime_http_direct]
    HTTP_OPTION 10004               # No implicit environment proxy.
    mov rdx, [rbp + 72]
    HTTP_OPTION 10002               # URL.
    lea rdx, [rip + runtime_http_write]
    HTTP_OPTION 20011
    lea rdx, [rbp + 32]
    HTTP_OPTION 10001
    mov rax, [rbp]
    mov rdx, [rax + 8]
    HTTP_OPTION 155                 # Total transfer timeout in ms.
    mov edx, 1
    HTTP_OPTION 99                  # NOSIGNAL.
    mov edx, 1
    HTTP_OPTION 64                  # SSL_VERIFYPEER.
    mov edx, 2
    HTTP_OPTION 81                  # SSL_VERIFYHOST.
    mov edx, 6
    HTTP_OPTION 32                  # TLS 1.2 minimum; allow newer versions.
    mov edx, 3
    HTTP_OPTION 181                 # Only HTTP / HTTPS, not file/FTP/etc.
    xor edx, edx
    HTTP_OPTION 52                  # No automatic redirects.
    lea rdi, [rip + runtime_http_ca_env]
    HC getenv
    test rax, rax
    jz runtime_http_linux_headers
    cmp BYTE PTR [rax], 0
    je runtime_http_linux_headers
    mov rdx, rax
    HTTP_OPTION 10065               # Explicit trust bundle, verification stays on.
runtime_http_linux_headers:
    mov rax, [rbp]
    mov rax, [rax + 32]
    mov [rbp + 88], rax
runtime_http_linux_header_each:
    cmp QWORD PTR [rbp + 88], 0
    je runtime_http_linux_headers_done
    mov rdi, [rbp + 24]
    mov rsi, [rbp + 80]
    HC curl_slist_append
    test rax, rax
    jz runtime_http_linux_io
    mov [rbp + 24], rax
    mov rsi, [rbp + 80]
runtime_http_linux_header_skip:
    cmp BYTE PTR [rsi], 0
    lea rsi, [rsi + 1]
    jne runtime_http_linux_header_skip
    mov [rbp + 80], rsi
    dec QWORD PTR [rbp + 88]
    jmp runtime_http_linux_header_each
runtime_http_linux_headers_done:
    # Prevent an implicit Expect/100-continue delay on small API POSTs.
    mov rdi, [rbp + 24]
    lea rsi, [rip + runtime_http_expect]
    HC curl_slist_append
    test rax, rax
    jz runtime_http_linux_io
    mov [rbp + 24], rax
    mov rdx, rax
    HTTP_OPTION 10023
    mov rax, [rbp]
    cmp QWORD PTR [rax + 16], 0
    je runtime_http_linux_perform
    mov edx, 1
    HTTP_OPTION 47                  # POST.
    mov rax, [rbp + 8]
    mov rdx, [rax]
    HTTP_OPTION 60                  # Exact binary body length, including zero.
    mov rax, [rbp + 8]
    lea rdx, [rax + 8]
    HTTP_OPTION 10015
runtime_http_linux_perform:
    mov rdi, rbx
    HC curl_easy_perform
    test eax, eax
    jnz runtime_http_linux_error
    mov rdi, rbx
    mov esi, 0x200002               # CURLINFO_RESPONSE_CODE.
    lea rdx, [rbp + 96]
    xor eax, eax
    HC curl_easy_getinfo
    test eax, eax
    jnz runtime_http_linux_io
    mov rax, [rbp + 96]
    jmp runtime_http_linux_done
runtime_http_linux_error:
    cmp QWORD PTR [rbp + 40], 0
    jne runtime_http_linux_large
    cmp eax, 3
    je runtime_http_linux_invalid
    cmp eax, 77
    je runtime_http_linux_tls
    cmp eax, 28
    je runtime_http_linux_timeout
    cmp eax, 60
    je runtime_http_linux_tls
    cmp eax, 35
    je runtime_http_linux_tls
    cmp eax, 6
    je runtime_http_linux_dns
    cmp eax, 7
    je runtime_http_linux_connect
runtime_http_linux_invalid:
    mov rax, -22
    jmp runtime_http_linux_done
runtime_http_linux_io:
    mov rax, -5
    jmp runtime_http_linux_done
runtime_http_linux_unavailable:
    mov rax, -38
    jmp runtime_http_linux_done
runtime_http_linux_large:
    mov rax, -27
    jmp runtime_http_linux_done
runtime_http_linux_timeout:
    mov rax, -110
    jmp runtime_http_linux_done
runtime_http_linux_tls:
    mov rax, -13
    jmp runtime_http_linux_done
runtime_http_linux_dns:
    mov rax, -113
    jmp runtime_http_linux_done
runtime_http_linux_connect:
    mov rax, -111
runtime_http_linux_done:
    mov [rbp + 64], rax
    cmp QWORD PTR [rbp + 48], 0
    je runtime_http_linux_free_headers
    mov rdi, [rbp + 48]
    HC curl_easy_cleanup
runtime_http_linux_free_headers:
    mov rdi, [rbp + 24]
    test rdi, rdi
    jz runtime_http_linux_free_global
    HC curl_slist_free_all
runtime_http_linux_free_global:
    cmp QWORD PTR [rbp + 56], 0
    je runtime_http_linux_return
    HC curl_global_cleanup
runtime_http_linux_return:
    mov rax, [rbp + 64]
    mov QWORD PTR [r15 + 8], 0
    test rax, rax
    jns runtime_http_linux_ok
    mov [r15 + 8], rax
    mov rdx, [rbp + 16]
    cmp QWORD PTR [rdx], 8
    jb runtime_http_linux_ok
    mov QWORD PTR [rdx + 8], 0
runtime_http_linux_ok:
    add rsp, 128
    pop rbx
    pop rbp
    ret
runtime_http_write:
    mov rax, rsi
    mul rdx
    test rdx, rdx
    jnz runtime_http_write_large
    mov r8, [rcx]
    mov r9, [r8]
    sub r9, 8
    sub r9, [r8 + 8]
    cmp rax, r9
    ja runtime_http_write_large
    mov rsi, rdi
    lea rdi, [r8 + 16]
    add rdi, [r8 + 8]
    add [r8 + 8], rax
    mov rcx, rax
    rep movsb
    ret
runtime_http_write_large:
    mov QWORD PTR [rcx + 8], 1
    xor eax, eax
    ret
runtime_http_expect: .asciz "Expect:"
runtime_http_ca_env: .asciz "SSL_CERT_FILE"

runtime_http_direct: .byte 0
