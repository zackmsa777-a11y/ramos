# rax = a bounded parser-created label. Record the current rel32 field.
record_branch:
    mov rcx, QWORD PTR [rip + branch_count]
    cmp rcx, IR_LIMIT
    jae limit_error
    shl rcx, 4
    lea rdx, [rip + branch_fixups]
    mov QWORD PTR [rdx + rcx + 8], rax
    mov rax, QWORD PTR [rip + code_cursor]
    sub rax, r14
    mov QWORD PTR [rdx + rcx], rax
    inc QWORD PTR [rip + branch_count]
    xor eax, eax
    jmp emit_u32

emit_function:
    push rbx
    push r12
    mov rax, QWORD PTR [r13 + 8]
    shl rax, 6
    lea rbx, [rip + functions]
    add rbx, rax
    mov rax, QWORD PTR [rip + code_cursor]
    sub rax, r14
    mov rcx, QWORD PTR [rbx + 40]
    lea rdx, [rip + label_offsets]
    mov QWORD PTR [rdx + rcx * 8], rax
    lea rsi, [rip + function_depth_guard]
    mov ecx, 9
    call emit_bytes
    mov eax, OFFSET FLAT:RUNTIME_DEPTH_FILE
    call emit_relative
    lea rsi, [rip + function_prologue]
    mov ecx, OFFSET FLAT:FUNCTION_PROLOGUE_SIZE
    call emit_bytes
    mov rax, QWORD PTR [rbx + 32]
    shl rax, 3
    add rax, 15
    and rax, -16
    call emit_u32
    xor r12d, r12d
emit_parameter:
    cmp r12, QWORD PTR [rbx + 16]
    jae emit_function_done
    lea rsi, [rip + load_prefix]
    mov ecx, 3
    call emit_bytes
    mov rax, QWORD PTR [rbx + 16]
    sub rax, r12
    dec rax
    shl rax, 3
    add rax, 16
    call emit_u32
    lea rsi, [rip + parameter_store_prefix]
    mov ecx, 3
    call emit_bytes
    lea rax, [r12 + 1]
    shl rax, 3
    neg rax
    call emit_u32
    inc r12
    jmp emit_parameter
emit_function_done:
    pop r12
    pop rbx
    jmp emit_ir_next

emit_call:
    mov eax, 0xe8
    call emit_byte
    mov rax, QWORD PTR [r13 + 8]
    shl rax, 6
    lea rcx, [rip + functions]
    mov rax, QWORD PTR [rcx + rax + 40]
    call record_branch
    cmp QWORD PTR [r13 + 16], 0
    je emit_push_result
    lea rsi, [rip + argument_cleanup_prefix]
    mov ecx, 3
    call emit_bytes
    mov rax, QWORD PTR [r13 + 16]
    shl rax, 3
    call emit_u32
    jmp emit_push_result

emit_return:
    cmp QWORD PTR [r13 + 8], 0
    je emit_return_void
    mov eax, 0x58
    call emit_byte
    jmp emit_return_epilogue
emit_return_void:
    mov eax, 0x31
    call emit_byte
    mov eax, 0xc0
    call emit_byte
emit_return_epilogue:
    lea rsi, [rip + function_epilogue]
    mov ecx, 5
    call emit_bytes
    jmp emit_ir_next
emit_drop:
    mov eax, 0x58
    call emit_byte
    jmp emit_ir_next
