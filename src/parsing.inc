# Statement parsing, typed integer expression IR, and local symbol table.
# Expressions emit postfix IR; generated programs evaluate it as native code.

append_ir:
    mov rax, QWORD PTR [rip + ir_count]
    cmp rax, IR_LIMIT
    jae limit_error
    lea rcx, [rax + rax * 2]
    shl rcx, 3
    lea r8, [rip + ir_buffer]
    mov QWORD PTR [r8 + rcx], rdi
    mov QWORD PTR [r8 + rcx + 8], rsi
    mov QWORD PTR [r8 + rcx + 16], rdx
    inc QWORD PTR [rip + ir_count]
    ret

parse_program:
    call next_token
    mov edi, T_FN
    call expect_token
    mov edi, T_MAIN
    call expect_token
    mov edi, T_LP
    call expect_token
    mov edi, T_RP
    call expect_token
    mov edi, T_LB
    call expect_token
parse_statement:
    call skip_newlines
    mov rax, QWORD PTR [rip + token]
    cmp rax, T_RB
    je parse_end
    cmp QWORD PTR [rip + statement_count], STATEMENT_LIMIT
    jae limit_error
    cmp rax, T_PRINT
    je parse_print
    cmp rax, T_LET
    je parse_let
    cmp rax, T_VAR
    je parse_var
    cmp rax, T_IDENT
    je parse_assignment
    jmp syntax_error
parse_print:
    call next_token
    mov edi, T_LP
    call expect_token
    call skip_newlines
    cmp QWORD PTR [rip + token], T_STRING
    jne parse_print_integer
    mov edi, IR_STRING
    mov rsi, QWORD PTR [rip + string_offset]
    mov rdx, QWORD PTR [rip + string_length]
    inc rdx
    call append_ir
    mov al, 10
    call append_data_byte
    call next_token
    jmp parse_print_close
parse_print_integer:
    call parse_expression
    mov edi, IR_PRINT_INT
    xor esi, esi
    xor edx, edx
    call append_ir
parse_print_close:
    mov edi, T_RP
    call expect_token
    jmp finish_statement
parse_let:
    mov QWORD PTR [rip + pending_mutable], 0
    jmp parse_declaration
parse_var:
    mov QWORD PTR [rip + pending_mutable], 1
parse_declaration:
    call next_token
    call skip_newlines
    cmp QWORD PTR [rip + token], T_IDENT
    jne syntax_error
    mov rdi, QWORD PTR [rip + identifier_offset]
    mov QWORD PTR [rip + pending_name_offset], rdi
    mov rsi, QWORD PTR [rip + identifier_length]
    mov QWORD PTR [rip + pending_name_length], rsi
    call find_symbol
    cmp rax, -1
    jne duplicate_symbol_error
    call next_token
    mov edi, T_EQUAL
    call expect_token
    call parse_expression
    call declare_symbol
    mov rsi, rax
    mov edi, IR_STORE
    xor edx, edx
    call append_ir
    jmp finish_statement
parse_assignment:
    mov rdi, QWORD PTR [rip + identifier_offset]
    mov rsi, QWORD PTR [rip + identifier_length]
    call find_symbol
    cmp rax, -1
    je undefined_symbol_error
    mov QWORD PTR [rip + pending_slot], rax
    mov rcx, rax
    shl rcx, 5
    lea rdx, [rip + symbols]
    cmp QWORD PTR [rdx + rcx + 24], 0
    je immutable_symbol_error
    call next_token
    mov edi, T_EQUAL
    call expect_token
    call parse_expression
    mov edi, IR_STORE
    mov rsi, QWORD PTR [rip + pending_slot]
    xor edx, edx
    call append_ir
finish_statement:
    inc QWORD PTR [rip + statement_count]
    cmp QWORD PTR [rip + token], T_NL
    je parse_statement
    cmp QWORD PTR [rip + token], T_RB
    je parse_end
    lea rsi, [rip + separator_message]
    jmp die
parse_end:
    call next_token
    call skip_newlines
    cmp QWORD PTR [rip + token], T_EOF
    jne syntax_error
    ret

# Normal precedence and left associativity. Newlines after an operator or
# opening parenthesis are allowed; other newlines terminate the expression.
parse_expression:
    push rbx
    call parse_product
parse_sum_more:
    mov rax, QWORD PTR [rip + token]
    mov ebx, IR_ADD
    cmp rax, T_PLUS
    je parse_sum_operator
    mov ebx, IR_SUB
    cmp rax, T_MINUS
    jne parse_sum_done
parse_sum_operator:
    call next_token
    call parse_product
    mov edi, ebx
    xor esi, esi
    xor edx, edx
    call append_ir
    jmp parse_sum_more
parse_sum_done:
    pop rbx
    ret
parse_product:
    push rbx
    call parse_unary
parse_product_more:
    mov rax, QWORD PTR [rip + token]
    mov ebx, IR_MUL
    cmp rax, T_STAR
    je parse_product_operator
    mov ebx, IR_DIV
    cmp rax, T_SLASH
    je parse_product_operator
    mov ebx, IR_MOD
    cmp rax, T_PERCENT
    jne parse_product_done
parse_product_operator:
    call next_token
    call parse_unary
    mov edi, ebx
    xor esi, esi
    xor edx, edx
    call append_ir
    jmp parse_product_more
parse_product_done:
    pop rbx
    ret
parse_unary:
    inc QWORD PTR [rip + expression_depth]
    cmp QWORD PTR [rip + expression_depth], EXPRESSION_LIMIT
    ja limit_error
    call skip_newlines
    cmp QWORD PTR [rip + token], T_PLUS
    je parse_unary_plus
    cmp QWORD PTR [rip + token], T_MINUS
    je parse_unary_minus
    call parse_primary
    jmp parse_unary_done
parse_unary_plus:
    call next_token
    call parse_unary
    jmp parse_unary_done
parse_unary_minus:
    call next_token
    call skip_newlines
    cmp QWORD PTR [rip + token], T_NUMBER
    jne parse_unary_general_negative
    mov rsi, QWORD PTR [rip + number_value]
    test rsi, rsi
    jns parse_unary_general_negative
    # Only the directly negated magnitude 2^63 is accepted as INT64_MIN.
    mov edi, IR_LITERAL
    xor edx, edx
    call append_ir
    call next_token
    jmp parse_unary_done
parse_unary_general_negative:
    call parse_unary
    mov edi, IR_NEG
    xor esi, esi
    xor edx, edx
    call append_ir
parse_unary_done:
    dec QWORD PTR [rip + expression_depth]
    ret
parse_primary:
    mov rax, QWORD PTR [rip + token]
    cmp rax, T_NUMBER
    je parse_integer_literal
    cmp rax, T_IDENT
    je parse_integer_name
    cmp rax, T_LP
    jne syntax_error
    call next_token
    call parse_expression
    mov edi, T_RP
    jmp expect_token
parse_integer_literal:
    mov rsi, QWORD PTR [rip + number_value]
    test rsi, rsi
    js number_range_error
    mov edi, IR_LITERAL
    xor edx, edx
    call append_ir
    jmp next_token
parse_integer_name:
    mov rdi, QWORD PTR [rip + identifier_offset]
    mov rsi, QWORD PTR [rip + identifier_length]
    call find_symbol
    cmp rax, -1
    je undefined_symbol_error
    mov rsi, rax
    mov edi, IR_LOAD
    xor edx, edx
    call append_ir
    jmp next_token

# FNV-1a hash plus bounded open addressing. Names are source slices, so the
# compiler does not copy or truncate identifiers. Return symbol index in rax
# (or -1) and the matching/empty bucket index in rdx.
find_symbol:
    push rbx
    push r12
    push r13
    push r14
    push r15
    mov r12, rdi
    mov r13, rsi
    lea r14, [rip + source_buffer]
    add r14, r12
    mov rax, 0xcbf29ce484222325
    mov rcx, 0x100000001b3
    xor ebx, ebx
symbol_hash_byte:
    cmp rbx, r13
    jae symbol_hash_done
    movzx edx, BYTE PTR [r14 + rbx]
    xor rax, rdx
    imul rax, rcx
    inc rbx
    jmp symbol_hash_byte
symbol_hash_done:
    and eax, SYMBOL_BUCKETS - 1
    mov r15, rax
    xor r11d, r11d
symbol_probe:
    lea r8, [rip + symbol_buckets]
    mov rax, QWORD PTR [r8 + r15 * 8]
    test rax, rax
    jz symbol_not_found
    dec rax
    mov rbx, rax
    shl rax, 5
    lea r8, [rip + symbols]
    add r8, rax
    cmp QWORD PTR [r8 + 8], r13
    jne symbol_next_bucket
    lea rdi, [rip + source_buffer]
    add rdi, QWORD PTR [r8]
    xor ecx, ecx
symbol_compare_byte:
    cmp rcx, r13
    jae symbol_found
    mov al, BYTE PTR [rdi + rcx]
    cmp al, BYTE PTR [r14 + rcx]
    jne symbol_next_bucket
    inc rcx
    jmp symbol_compare_byte
symbol_next_bucket:
    inc r15
    and r15d, SYMBOL_BUCKETS - 1
    inc r11
    cmp r11, SYMBOL_BUCKETS
    jae limit_error
    jmp symbol_probe
symbol_not_found:
    mov rax, -1
    jmp symbol_return
symbol_found:
    mov rax, rbx
symbol_return:
    mov rdx, r15
    pop r15
    pop r14
    pop r13
    pop r12
    pop rbx
    ret

declare_symbol:
    mov rdi, QWORD PTR [rip + pending_name_offset]
    mov rsi, QWORD PTR [rip + pending_name_length]
    call find_symbol
    cmp rax, -1
    jne duplicate_symbol_error
    mov rcx, rdx
    mov rax, QWORD PTR [rip + symbol_count]
    cmp rax, SYMBOL_LIMIT
    jae limit_error
    mov rdx, rax
    shl rdx, 5
    lea r8, [rip + symbols]
    add r8, rdx
    mov rdx, QWORD PTR [rip + pending_name_offset]
    mov QWORD PTR [r8], rdx
    mov rdx, QWORD PTR [rip + pending_name_length]
    mov QWORD PTR [r8 + 8], rdx
    mov QWORD PTR [r8 + 16], rax
    mov rdx, QWORD PTR [rip + pending_mutable]
    mov QWORD PTR [r8 + 24], rdx
    lea r8, [rip + symbol_buckets]
    lea rdx, [rax + 1]
    mov QWORD PTR [r8 + rcx * 8], rdx
    inc QWORD PTR [rip + symbol_count]
    ret
undefined_symbol_error:
    lea rsi, [rip + undefined_message]
    jmp die
duplicate_symbol_error:
    lea rsi, [rip + duplicate_message]
    jmp die
immutable_symbol_error:
    lea rsi, [rip + immutable_message]
    jmp die
