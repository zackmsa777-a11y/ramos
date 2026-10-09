# Native instruction emission. No invocation of an assembler for Ramos input.
# All emission goes through reserve_code, which checks the output arena bound.
reserve_code:
    mov rdi, QWORD PTR [rip + code_cursor]
    mov rdx, rdi
    add rdx, rcx
    lea r8, [rip + executable_buffer + OUTPUT_LIMIT]
    cmp rdx, r8
    ja limit_error
    mov QWORD PTR [rip + code_cursor], rdx
    ret
emit_bytes:
    call reserve_code
    rep movsb
    ret
emit_byte:
    mov ecx, 1
    call reserve_code
    mov BYTE PTR [rdi], al
    ret
emit_u32:
    mov ecx, 4
    call reserve_code
    mov DWORD PTR [rdi], eax
    ret
emit_u64:
    mov ecx, 8
    call reserve_code
    mov QWORD PTR [rdi], rax
    ret
# rax is a target file offset; current cursor points to the rel32 field.
emit_relative:
    mov rdx, QWORD PTR [rip + code_cursor]
    lea rcx, [rip + executable_buffer]
    sub rdx, rcx
    add rdx, 4
    sub rax, rdx
    jmp emit_u32
# edi is the second Jcc opcode byte (0x80=overflow, 0x84=zero).
emit_failure_branch:
    push rbx
    mov ebx, edi
    mov eax, 0x0f
    call emit_byte
    mov eax, ebx
    call emit_byte
    mov eax, OFFSET FLAT:RUNTIME_ERROR_FILE
    call emit_relative
    pop rbx
    ret

generate_executable:
    lea r14, [rip + executable_buffer]
    lea rax, [r14 + CODE_OFFSET]
    mov QWORD PTR [rip + code_cursor], rax
    lea rsi, [rip + runtime_writer]
    mov ecx, OFFSET FLAT:RUNTIME_SIZE
    call emit_bytes
    lea rsi, [rip + main_prologue]
    mov ecx, OFFSET FLAT:MAIN_PROLOGUE_SIZE
    call emit_bytes
    mov rax, QWORD PTR [rip + symbol_count]
    shl rax, 3
    add rax, 15
    and rax, -16
    call emit_u32
    lea r13, [rip + ir_buffer]
    mov rbx, QWORD PTR [rip + ir_count]
emit_ir:
    test rbx, rbx
    jz emit_program_exit
    mov r15, QWORD PTR [r13]
    cmp r15, IR_STRING
    je emit_string_print
    cmp r15, IR_LITERAL
    je emit_integer_literal
    cmp r15, IR_LOAD
    je emit_local_load
    cmp r15, IR_STORE
    je emit_local_store
    cmp r15, IR_PRINT_INT
    je emit_integer_print
    cmp r15, IR_NEG
    je emit_negation
    cmp r15, IR_ADD
    je emit_addition
    cmp r15, IR_SUB
    je emit_subtraction
    cmp r15, IR_MUL
    je emit_multiplication
    cmp r15, IR_DIV
    je emit_division
    cmp r15, IR_MOD
    je emit_division
    cmp r15, IR_NOT
    je emit_not
    cmp r15, IR_EQ
    jb emit_control_dispatch
    cmp r15, IR_GE
    jbe emit_comparison
emit_control_dispatch:
    cmp r15, IR_PRINT_BOOL
    je emit_boolean_print
    cmp r15, IR_LABEL
    je emit_label
    cmp r15, IR_JUMP
    je emit_jump
    cmp r15, IR_JZ
    je emit_conditional_jump
    jmp syntax_error
emit_label:
    mov rax, QWORD PTR [rip + code_cursor]
    sub rax, r14
    mov rcx, QWORD PTR [r13 + 8]
    lea rdx, [rip + label_offsets]
    mov QWORD PTR [rdx + rcx * 8], rax
    jmp emit_ir_next
emit_jump:
    mov eax, 0xe9
    call emit_byte
    jmp emit_branch_record
emit_conditional_jump:
    lea rsi, [rip + conditional_jump_bytes]
    mov ecx, 6
    call emit_bytes
emit_branch_record:
    mov rcx, QWORD PTR [rip + branch_count]
    cmp rcx, IR_LIMIT
    jae limit_error
    shl rcx, 4
    lea rdx, [rip + branch_fixups]
    mov rax, QWORD PTR [rip + code_cursor]
    sub rax, r14
    mov QWORD PTR [rdx + rcx], rax
    mov rax, QWORD PTR [r13 + 8]
    mov QWORD PTR [rdx + rcx + 8], rax
    inc QWORD PTR [rip + branch_count]
    xor eax, eax
    call emit_u32
    jmp emit_ir_next
emit_comparison:
    lea rsi, [rip + compare_bytes]
    mov ecx, 6
    call emit_bytes
    mov rax, r15
    sub rax, IR_EQ
    lea rsi, [rip + comparison_opcodes]
    movzx eax, BYTE PTR [rsi + rax]
    call emit_byte
    jmp emit_boolean_normalize
emit_not:
    lea rsi, [rip + not_bytes]
    mov ecx, 6
    call emit_bytes
emit_boolean_normalize:
    lea rsi, [rip + normalize_boolean]
    mov ecx, 5
    call emit_bytes
    jmp emit_push_result
emit_boolean_print:
    mov eax, 0x58
    call emit_byte
    mov eax, 0xe8
    call emit_byte
    mov eax, OFFSET FLAT:RUNTIME_BOOLEAN_FILE
    call emit_relative
    jmp emit_ir_next
emit_integer_literal:
    lea rsi, [rip + literal_prefix]
    mov ecx, 2
    call emit_bytes
    mov rax, QWORD PTR [r13 + 8]
    call emit_u64
    jmp emit_push_result
emit_local_load:
    lea rsi, [rip + load_prefix]
    mov ecx, 3
    call emit_bytes
    call emit_slot_displacement
    jmp emit_push_result
emit_local_store:
    lea rsi, [rip + store_prefix]
    mov ecx, 4
    call emit_bytes
    call emit_slot_displacement
    jmp emit_ir_next
emit_slot_displacement:
    mov rax, QWORD PTR [r13 + 8]
    inc rax
    shl rax, 3
    neg rax
    jmp emit_u32
emit_integer_print:
    mov eax, 0x58
    call emit_byte
    mov eax, 0xe8
    call emit_byte
    mov eax, OFFSET FLAT:RUNTIME_INTEGER_FILE
    call emit_relative
    jmp emit_ir_next
emit_string_print:
    lea rsi, [rip + string_lea_prefix]
    mov ecx, 3
    call emit_bytes
    mov rcx, QWORD PTR [rip + fixup_count]
    cmp rcx, STATEMENT_LIMIT
    jae limit_error
    shl rcx, 4
    lea rdx, [rip + string_fixups]
    mov rax, QWORD PTR [rip + code_cursor]
    sub rax, r14
    mov QWORD PTR [rdx + rcx], rax
    mov rax, QWORD PTR [r13 + 8]
    mov QWORD PTR [rdx + rcx + 8], rax
    inc QWORD PTR [rip + fixup_count]
    xor eax, eax
    call emit_u32
    mov eax, 0xba
    call emit_byte
    mov rax, QWORD PTR [r13 + 16]
    call emit_u32
    mov eax, 0xe8
    call emit_byte
    mov eax, CODE_OFFSET
    call emit_relative
    jmp emit_ir_next
emit_negation:
    lea rsi, [rip + negate_bytes]
    mov ecx, 4
    call emit_bytes
    jmp emit_check_overflow
emit_addition:
    lea rsi, [rip + add_bytes]
    mov ecx, 5
    call emit_bytes
    jmp emit_check_overflow
emit_subtraction:
    lea rsi, [rip + subtract_bytes]
    mov ecx, 5
    call emit_bytes
    jmp emit_check_overflow
emit_multiplication:
    lea rsi, [rip + multiply_bytes]
    mov ecx, 6
    call emit_bytes
emit_check_overflow:
    mov edi, 0x80
    call emit_failure_branch
    jmp emit_push_result
emit_division:
    lea rsi, [rip + divide_start]
    mov ecx, 5
    call emit_bytes
    mov edi, 0x84
    call emit_failure_branch
    lea rsi, [rip + division_minimum_prefix]
    mov ecx, 2
    call emit_bytes
    mov rax, 0x8000000000000000
    call emit_u64
    lea rsi, [rip + division_guard]
    mov ecx, 9
    call emit_bytes
    mov edi, 0x84
    call emit_failure_branch
    lea rsi, [rip + divide_bytes]
    mov ecx, 5
    call emit_bytes
    cmp r15, IR_MOD
    jne emit_push_result
    lea rsi, [rip + remainder_bytes]
    mov ecx, 3
    call emit_bytes
emit_push_result:
    mov eax, 0x50
    call emit_byte
emit_ir_next:
    add r13, 24
    dec rbx
    jmp emit_ir
emit_program_exit:
    lea rsi, [rip + runtime_exit]
    mov ecx, OFFSET FLAT:EXIT_SIZE
    call emit_bytes
    # Every label and branch was allocated in the bounded parser IR.
    lea r13, [rip + branch_fixups]
    mov rbx, QWORD PTR [rip + branch_count]
resolve_branch:
    test rbx, rbx
    jz branches_done
    mov rcx, QWORD PTR [r13 + 8]
    lea rdx, [rip + label_offsets]
    mov rax, QWORD PTR [rdx + rcx * 8]
    test rax, rax
    jz syntax_error
    mov rdx, QWORD PTR [r13]
    sub rax, rdx
    sub rax, 4
    mov DWORD PTR [r14 + rdx], eax
    add r13, 16
    dec rbx
    jmp resolve_branch
branches_done:
    mov rax, QWORD PTR [rip + code_cursor]
    sub rax, r14
    mov QWORD PTR [rip + rx_length], rax
    add rax, 4095
    and rax, -4096
    mov QWORD PTR [rip + data_file_offset], rax
    add rax, QWORD PTR [rip + data_length]
    cmp rax, OUTPUT_LIMIT
    ja limit_error
    mov QWORD PTR [rip + executable_length], rax
    mov rdi, r14
    lea rsi, [rip + elf_header]
    mov ecx, OFFSET FLAT:ELF_HEADER_SIZE
    rep movsb
    mov rax, QWORD PTR [rip + rx_length]
    mov QWORD PTR [r14 + 96], rax
    mov QWORD PTR [r14 + 104], rax
    mov rax, QWORD PTR [rip + data_file_offset]
    mov QWORD PTR [r14 + 128], rax
    add rax, LOAD_BASE
    mov QWORD PTR [r14 + 136], rax
    mov QWORD PTR [r14 + 144], rax
    mov rax, QWORD PTR [rip + data_length]
    mov QWORD PTR [r14 + 152], rax
    mov QWORD PTR [r14 + 160], rax
    lea r13, [rip + string_fixups]
    mov rbx, QWORD PTR [rip + fixup_count]
resolve_string:
    test rbx, rbx
    jz copy_string_data
    mov rdx, QWORD PTR [r13]
    mov rax, QWORD PTR [rip + data_file_offset]
    add rax, QWORD PTR [r13 + 8]
    sub rax, rdx
    sub rax, 4
    mov DWORD PTR [r14 + rdx], eax
    add r13, 16
    dec rbx
    jmp resolve_string
copy_string_data:
    mov rdi, QWORD PTR [rip + data_file_offset]
    add rdi, r14
    lea rsi, [rip + data_buffer]
    mov rcx, QWORD PTR [rip + data_length]
    rep movsb
    ret
