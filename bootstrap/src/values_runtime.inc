# Strings use immutable buffer handles. Scalars are counted, not graphemes.
# Validate strict UTF-8: reject overlong encodings, surrogates and > U+10FFFF.
runtime_string_validate:
    lea rsi, [rax + 8]
    mov rdi, [rax]
    add rdi, rsi
    xor ecx, ecx
runtime_utf8_next:
    cmp rsi, rdi
    jae runtime_utf8_done
    movzx edx, BYTE PTR [rsi]
    inc rsi
    inc rcx
    cmp edx, 128
    jb runtime_utf8_next
    cmp edx, 194
    jb runtime_string_encoding_error
    cmp edx, 244
    ja runtime_string_encoding_error
    mov r8d, 1
    mov r9d, 128
    mov r10d, 191
    cmp edx, 224
    jb runtime_utf8_continuation
    mov r8d, 2
    cmp edx, 224
    jne runtime_utf8_not_e0
    mov r9d, 160
runtime_utf8_not_e0:
    cmp edx, 237
    jne runtime_utf8_not_ed
    mov r10d, 159
runtime_utf8_not_ed:
    cmp edx, 240
    jb runtime_utf8_continuation
    mov r8d, 3
    mov r9d, 128
    mov r10d, 191
    cmp edx, 240
    jne runtime_utf8_not_f0
    mov r9d, 144
runtime_utf8_not_f0:
    cmp edx, 244
    jne runtime_utf8_continuation
    mov r10d, 143
runtime_utf8_continuation:
    cmp rsi, rdi
    jae runtime_string_encoding_error
    movzx edx, BYTE PTR [rsi]
    inc rsi
    cmp edx, r9d
    jb runtime_string_encoding_error
    cmp edx, r10d
    ja runtime_string_encoding_error
    mov r9d, 128
    mov r10d, 191
    dec r8d
    jnz runtime_utf8_continuation
    jmp runtime_utf8_next
runtime_utf8_done:
    ret
runtime_string_from_bytes:
    push rax
    call runtime_string_validate
    pop rax
runtime_string_to_bytes:
    lea rsi, [rax + 8]
    mov rax, [rax]
    jmp runtime_buffer_literal
runtime_string_len:
    call runtime_string_validate
    mov rax, rcx
    ret
runtime_string_slice:
    # RAX string, RCX scalar start, RDX scalar end (exclusive).
    test rcx, rcx
    js runtime_string_bounds_error
    cmp rdx, rcx
    jl runtime_string_bounds_error
    lea rsi, [rax + 8]
    mov rdi, [rax]
    add rdi, rsi
    xor r8d, r8d
    mov r9, rsi
runtime_string_slice_next:
    cmp r8, rcx
    jne runtime_string_slice_end_check
    mov r9, rsi
runtime_string_slice_end_check:
    cmp r8, rdx
    je runtime_string_slice_copy
    cmp rsi, rdi
    jae runtime_string_bounds_error
    inc rsi
runtime_string_slice_cont:
    cmp rsi, rdi
    jae runtime_string_slice_scalar
    movzx r10d, BYTE PTR [rsi]
    and r10d, 192
    cmp r10d, 128
    jne runtime_string_slice_scalar
    inc rsi
    jmp runtime_string_slice_cont
runtime_string_slice_scalar:
    inc r8
    jmp runtime_string_slice_next
runtime_string_slice_copy:
    mov rax, rsi
    sub rax, r9
    mov rsi, r9
    jmp runtime_buffer_literal
runtime_string_concat:
    push rax
    push rcx
    mov rax, [rax]
    add rax, [rcx]
    call runtime_buffer_new
    mov r8, rax
    lea rdi, [rax + 8]
    mov rsi, [rsp + 8]
    mov rcx, [rsi]
    add rsi, 8
    rep movsb
    pop rsi
    mov rcx, [rsi]
    add rsi, 8
    rep movsb
    add rsp, 8
    mov rax, r8
    ret
runtime_string_equal:
    mov rdx, [rax]
    cmp rdx, [rcx]
    jne runtime_string_unequal
    lea rsi, [rax + 8]
    lea rdi, [rcx + 8]
    mov rcx, rdx
    xor eax, eax
    test rcx, rcx
    jz runtime_string_eq_yes
    repe cmpsb
    jne runtime_string_eq_done
runtime_string_eq_yes:
    mov eax, 1
runtime_string_eq_done:
    ret
runtime_string_unequal:
    xor eax, eax
    ret
runtime_array_empty:
    xor ecx, ecx
    xor edx, edx
    jmp runtime_array_new
runtime_array_new:
    # RAX element type (compile-time checked), RCX count, RDX fill.
    cmp rcx, BUFFER_LIMIT / 8
    ja runtime_array_size_error
    push rdx
    lea rax, [rcx*8]
    call runtime_buffer_new
    pop rdx
    mov r8, rax
    mov rcx, [rax]
    shr rcx, 3
    lea rdi, [rax + 8]
    mov rax, rdx
    rep stosq
    mov rax, r8
    ret
runtime_array_len:
    mov rax, [rax]
    shr rax, 3
    ret
runtime_array_get:
    mov rdx, [rax]
    shr rdx, 3
    cmp rcx, rdx
    jae runtime_array_bounds_error
    mov rax, [rax + rcx*8 + 8]
    ret
runtime_array_set:
    mov r8, [rax]
    shr r8, 3
    cmp rcx, r8
    jae runtime_array_bounds_error
    mov [rax + rcx*8 + 8], rdx
    xor eax, eax
    ret
runtime_array_resize:
    cmp rcx, BUFFER_LIMIT / 8
    ja runtime_array_size_error
    push rax
    push rcx
    push rdx
    call runtime_array_new
    mov r8, rax
    lea rdi, [rax + 8]
    mov rsi, [rsp + 16]
    mov rcx, [rsi]
    cmp rcx, [rax]
    jbe runtime_array_resize_copy
    mov rcx, [rax]
runtime_array_resize_copy:
    shr rcx, 3
    add rsi, 8
    rep movsq
    add rsp, 24
    mov rax, r8
    ret
runtime_record_new:
    # RAX field count, RSI top of arguments (last field first).
    push rsi
    shl rax, 3
    call runtime_buffer_new
    pop rsi
    lea rdi, [rax + 8]
    mov rcx, [rax]
    shr rcx, 3
    lea rsi, [rsi + rcx*8 - 8]
runtime_record_copy:
    test rcx, rcx
    jz runtime_record_copy_done
    mov rdx, [rsi]
    mov [rdi], rdx
    sub rsi, 8
    add rdi, 8
    dec rcx
    jmp runtime_record_copy
runtime_record_copy_done:
    ret
runtime_record_get:
    jmp runtime_array_get
runtime_record_set:
    jmp runtime_array_set
runtime_string_encoding_error:
    lea rsi, [rip + string_encoding_message]
    mov edx, string_encoding_end - string_encoding_message
    jmp runtime_value_error
runtime_string_bounds_error:
    lea rsi, [rip + string_bounds_message]
    mov edx, string_bounds_end - string_bounds_message
    jmp runtime_value_error
runtime_array_size_error:
    lea rsi, [rip + array_size_message]
    mov edx, array_size_end - array_size_message
    jmp runtime_value_error
runtime_array_bounds_error:
    lea rsi, [rip + array_bounds_message]
    mov edx, array_bounds_end - array_bounds_message
    jmp runtime_value_error
string_encoding_message: .ascii "Ramos runtime error: invalid UTF-8 string\n"
string_encoding_end:
string_bounds_message: .ascii "Ramos runtime error: string slice out of bounds\n"
string_bounds_end:
array_size_message: .ascii "Ramos runtime error: array size must be between 0 and 131072\n"
array_size_end:
array_bounds_message: .ascii "Ramos runtime error: array index out of bounds\n"
array_bounds_end:
