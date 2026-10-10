emit_builtin:
    # Expressions are stacked left to right; reverse pops restore arg order.
    mov rax, QWORD PTR [r13 + 8]
    shl rax, 6
    lea rsi, [rip + builtin_signatures]
    mov rcx, QWORD PTR [rsi + rax + 16]
    lea rsi, [rip + builtin_pop_arguments + 3]
    sub rsi, rcx
    call emit_bytes
    mov eax, 0xe8
    call emit_byte
    mov rax, QWORD PTR [r13 + 8]
    shl rax, 6
    lea rcx, [rip + builtin_signatures]
    mov rax, QWORD PTR [rcx + rax + 56]
    call emit_relative
    jmp emit_push_result
emit_buffer_literal:
    call emit_string_address
    lea rsi, [rip + literal_prefix]
    mov ecx, 2
    call emit_bytes
    mov rax, QWORD PTR [r13 + 16]
    call emit_u64
    mov eax, 0xe8
    call emit_byte
    mov eax, OFFSET FLAT:RUNTIME_BUFFER_LITERAL_FILE
    call emit_relative
    jmp emit_push_result
emit_buffer_print:
    mov eax, 0x58
    call emit_byte
    mov eax, 0xe8
    call emit_byte
    mov eax, OFFSET FLAT:RUNTIME_BUFFER_PRINT_FILE
    call emit_relative
    jmp emit_ir_next
