# Private packet: timeout u64, method (0 GET / 1 POST), URL length,
# header count; ASCII URL+NUL then header lines+NUL. Output: used u64 + body.
# Validate every native caller, including callers bypassing the Ramos library.
# rax packet, rcx body, rdx output -> r8 URL, r9 headers; rax 0 / negative.
runtime_http_validate:
    cmp rax, rdx
    je runtime_http_invalid
    cmp rcx, rdx
    je runtime_http_invalid
    cmp QWORD PTR [rdx], 8
    jb runtime_http_invalid
    cmp QWORD PTR [rdx], BUFFER_LIMIT
    ja runtime_http_invalid
    mov QWORD PTR [rdx + 8], 0
    cmp QWORD PTR [rax], 34
    jb runtime_http_invalid
    cmp QWORD PTR [rax], 32768
    ja runtime_http_invalid
    cmp QWORD PTR [rax + 8], 1
    jb runtime_http_invalid
    cmp QWORD PTR [rax + 8], 120000
    ja runtime_http_invalid
    cmp QWORD PTR [rax + 16], 1
    ja runtime_http_invalid
    cmp QWORD PTR [rax + 32], 64
    ja runtime_http_invalid
    mov r10, [rax + 24]
    cmp r10, 8
    jb runtime_http_invalid
    cmp r10, 8192
    ja runtime_http_invalid
    lea r8, [rax + 40]
    lea r11, [rax + 8]
    add r11, [rax]
    lea r9, [r8 + r10]
    cmp r9, r11
    jae runtime_http_invalid
    cmp BYTE PTR [r9], 0
    jne runtime_http_invalid
    cmp DWORD PTR [r8], 0x70747468   # http
    jne runtime_http_invalid
    cmp WORD PTR [r8 + 4], 0x2f3a   # :/
    jne runtime_http_scheme_https
    cmp BYTE PTR [r8 + 6], 47
    jne runtime_http_invalid
    lea rsi, [r8 + 7]
    jmp runtime_http_url_scan
runtime_http_scheme_https:
    cmp DWORD PTR [r8 + 4], 0x2f2f3a73 # s://
    jne runtime_http_invalid
    lea rsi, [r8 + 8]
runtime_http_url_scan:
    cmp rsi, r9
    jae runtime_http_invalid
    cmp BYTE PTR [rsi], 47
    je runtime_http_invalid
    cmp BYTE PTR [rsi], 63
    je runtime_http_invalid
    mov edi, 1                     # Still inside authority.
runtime_http_url_each:
    movzx edx, BYTE PTR [rsi]
    cmp edx, 33
    jb runtime_http_invalid
    cmp edx, 126
    ja runtime_http_invalid
    cmp edx, 35                    # Fragments are not sent to servers.
    je runtime_http_invalid
    cmp edx, 92                    # Backslashes normalize differently by OS.
    je runtime_http_invalid
    cmp edx, 47
    je runtime_http_authority_done
    cmp edx, 63
    je runtime_http_authority_done
    test edi, edi
    jz runtime_http_url_next
    cmp edx, 64                    # No embedded credentials.
    je runtime_http_invalid
    jmp runtime_http_url_next
runtime_http_authority_done:
    xor edi, edi
runtime_http_url_next:
    inc rsi
    cmp rsi, r9
    jb runtime_http_url_each
    inc r9
    mov rcx, [rax + 32]
    mov rsi, r9
runtime_http_header_each:
    test rcx, rcx
    jz runtime_http_header_end
    xor edi, edi                   # Colon seen?
    xor edx, edx                   # Name length.
runtime_http_header_byte:
    cmp rsi, r11
    jae runtime_http_invalid
    movzx r10d, BYTE PTR [rsi]
    inc rsi
    test r10d, r10d
    jz runtime_http_header_next
    cmp r10d, 32
    jb runtime_http_invalid
    cmp r10d, 126
    ja runtime_http_invalid
    test edi, edi
    jnz runtime_http_header_value
    cmp r10d, 58
    je runtime_http_header_colon
    # Header name must be an RFC token, never whitespace/separators.
    cmp r10d, 33
    jb runtime_http_invalid
    lea rdi, [rip + runtime_http_separators]
    push rcx
    mov ecx, 19
    mov al, r10b
    repne scasb
    pop rcx
    je runtime_http_invalid
    xor edi, edi
    inc edx
    jmp runtime_http_header_byte
runtime_http_header_value:
    cmp r10d, 32
    je runtime_http_header_byte
    mov edi, 2                     # At least one non-space value byte.
    jmp runtime_http_header_byte
runtime_http_header_colon:
    test edx, edx
    jz runtime_http_invalid
    mov edi, 1
    jmp runtime_http_header_byte
runtime_http_header_next:
    cmp edi, 2
    jne runtime_http_invalid
    dec rcx
    jmp runtime_http_header_each
runtime_http_header_end:
    cmp rsi, r11
    jne runtime_http_invalid
    xor eax, eax
    ret
runtime_http_invalid:
    mov rax, -22
    ret
runtime_http_separators: .ascii "()<>@,;:\\\"/[]?={} \t"
