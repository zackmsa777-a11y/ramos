# Block parsing, typed expression/control-flow IR, and scoped symbol table.
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

# Recursive blocks save their own symbol boundary. Slots are never reused;
# leaving a scope restores hash buckets to the shadowed outer declarations.
parse_program:
    call discover_functions
    jmp compile_functions
parse_block:
    push rbx
    push r12
    push r13
    xor r13d, r13d
    inc QWORD PTR [rip + scope_depth]
    cmp QWORD PTR [rip + scope_depth], BLOCK_LIMIT
    ja limit_error
    mov r12, QWORD PTR [rip + symbol_count]
    cmp QWORD PTR [rip + scope_depth], 1
    jne parse_block_boundary
    mov r12, QWORD PTR [rip + function_symbol_base]
parse_block_boundary:
    mov edi, T_LB
    call expect_token
parse_statement:
    call skip_newlines
    mov rax, QWORD PTR [rip + token]
    cmp rax, T_RB
    je parse_end
    cmp QWORD PTR [rip + statement_count], STATEMENT_LIMIT
    jae limit_error
    inc QWORD PTR [rip + statement_count]
    mov QWORD PTR [rip + statement_returns], 0
    cmp rax, T_PRINT
    je parse_print
    cmp rax, T_LET
    je parse_let
    cmp rax, T_VAR
    je parse_var
    cmp rax, T_IDENT
    je parse_named_statement
    cmp rax, T_RETURN
    je parse_return_statement
    cmp rax, T_IF
    je parse_if_statement
    cmp rax, T_WHILE
    je parse_while_statement
    cmp rax, T_BREAK
    je parse_break_statement
    cmp rax, T_CONTINUE
    je parse_continue_statement
    jmp syntax_error
parse_return_statement:
    call parse_return
    jmp finish_statement
parse_if_statement:
    call parse_if
    test eax, eax
    jz finish_statement
    or r13, QWORD PTR [rip + statement_returns]
    jmp parse_statement
parse_while_statement:
    call parse_while
    jmp finish_statement
parse_break_statement:
    mov rsi, QWORD PTR [rip + loop_end]
    jmp parse_loop_jump
parse_continue_statement:
    mov rsi, QWORD PTR [rip + loop_start]
parse_loop_jump:
    test rsi, rsi
    jz loop_error
    mov edi, IR_JUMP
    xor edx, edx
    call append_ir
    call next_token
    jmp finish_statement
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
    cmp QWORD PTR [rip + expression_type], TYPE_BOOL
    jne parse_print_emit
    mov edi, IR_PRINT_BOOL
parse_print_emit:
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
    je parse_declaration_new
    shl rax, 6
    lea rcx, [rip + symbols]
    mov rdx, QWORD PTR [rip + scope_depth]
    cmp QWORD PTR [rcx + rax + 40], rdx
    je duplicate_symbol_error
parse_declaration_new:
    call next_token
    mov edi, T_EQUAL
    call expect_token
    call parse_expression
    call declare_symbol
    shl rax, 6
    lea rcx, [rip + symbols]
    mov rsi, QWORD PTR [rcx + rax + 16]
    mov edi, IR_STORE
    xor edx, edx
    call append_ir
    jmp finish_statement
parse_named_statement:
    call parse_named_action
    jmp finish_statement
finish_statement:
    or r13, QWORD PTR [rip + statement_returns]
    cmp QWORD PTR [rip + token], T_NL
    je parse_statement
    cmp QWORD PTR [rip + token], T_RB
    je parse_end
    lea rsi, [rip + separator_message]
    jmp die
parse_end:
    mov rbx, QWORD PTR [rip + symbol_count]
parse_scope_restore:
    cmp rbx, r12
    jbe parse_scope_done
    dec rbx
    mov rax, rbx
    shl rax, 6
    lea rcx, [rip + symbols]
    add rcx, rax
    mov rdx, QWORD PTR [rip + scope_depth]
    cmp QWORD PTR [rcx + 40], rdx
    jne parse_scope_restore
    mov rax, QWORD PTR [rcx + 56]
    mov rdx, QWORD PTR [rcx + 48]
    lea rcx, [rip + symbol_buckets]
    mov QWORD PTR [rcx + rax * 8], rdx
    jmp parse_scope_restore
parse_scope_done:
    dec QWORD PTR [rip + scope_depth]
    call next_token
    mov QWORD PTR [rip + block_returns], r13
    pop r13
    pop r12
    pop rbx
    ret

new_label:
    mov rax, QWORD PTR [rip + label_count]
    cmp rax, IR_LIMIT
    jae limit_error
    inc rax
    mov QWORD PTR [rip + label_count], rax
    ret
append_label:
    mov edi, IR_LABEL
    mov rsi, rax
    xor edx, edx
    jmp append_ir

parse_if:
    push rbx
    push r12
    push r13
    push r14
    call next_token
    call parse_expression
    call require_bool
    call new_label
    mov rbx, rax
    mov rsi, rax
    mov edi, IR_JZ
    xor edx, edx
    call append_ir
    call parse_block
    mov r14, QWORD PTR [rip + block_returns]
    xor r13d, r13d
    cmp QWORD PTR [rip + token], T_NL
    jne parse_if_lookahead
    mov r13d, 1
parse_if_lookahead:
    call skip_newlines
    cmp QWORD PTR [rip + token], T_ELSE
    jne parse_if_no_else
    call new_label
    mov r12, rax
    mov rsi, rax
    mov edi, IR_JUMP
    xor edx, edx
    call append_ir
    mov rax, rbx
    call append_label
    call next_token
    call parse_block
    and r14, QWORD PTR [rip + block_returns]
    mov rax, r12
    call append_label
    xor r13d, r13d
    jmp parse_if_done
parse_if_no_else:
    xor r14d, r14d
    mov rax, rbx
    call append_label
parse_if_done:
    mov QWORD PTR [rip + statement_returns], r14
    mov eax, r13d
    pop r14
    pop r13
    pop r12
    pop rbx
    ret

parse_while:
    push rbx
    push r12
    push QWORD PTR [rip + loop_start]
    push QWORD PTR [rip + loop_end]
    call new_label
    mov rbx, rax
    call append_label
    call new_label
    mov r12, rax
    call next_token
    call parse_expression
    call require_bool
    mov rsi, r12
    mov edi, IR_JZ
    xor edx, edx
    call append_ir
    mov QWORD PTR [rip + loop_start], rbx
    mov QWORD PTR [rip + loop_end], r12
    call parse_block
    mov rsi, rbx
    mov edi, IR_JUMP
    xor edx, edx
    call append_ir
    mov rax, r12
    call append_label
    mov QWORD PTR [rip + statement_returns], 0
    pop QWORD PTR [rip + loop_end]
    pop QWORD PTR [rip + loop_start]
    pop r12
    pop rbx
    ret

# Recursive precedence levels maintain an explicit inferred expression type.
parse_expression:
    push rbx
    push r12
    call parse_ordering
parse_equality_more:
    mov ebx, IR_EQ
    cmp QWORD PTR [rip + token], T_EQ
    je parse_equality_operator
    mov ebx, IR_NE
    cmp QWORD PTR [rip + token], T_NE
    jne parse_equality_done
parse_equality_operator:
    mov r12, QWORD PTR [rip + expression_type]
    call next_token
    call parse_ordering
    cmp r12, QWORD PTR [rip + expression_type]
    jne type_error
    mov edi, ebx
    xor esi, esi
    xor edx, edx
    call append_ir
    mov QWORD PTR [rip + expression_type], TYPE_BOOL
    jmp parse_equality_more
parse_equality_done:
    pop r12
    pop rbx
    ret
parse_ordering:
    push rbx
    call parse_sum
parse_ordering_more:
    mov rax, QWORD PTR [rip + token]
    cmp rax, T_LT
    jb parse_ordering_done
    cmp rax, T_GE
    ja parse_ordering_done
    sub eax, T_LT
    add eax, IR_LT
    mov ebx, eax
    call require_integer
    call next_token
    call parse_sum
    call require_integer
    mov edi, ebx
    xor esi, esi
    xor edx, edx
    call append_ir
    mov QWORD PTR [rip + expression_type], TYPE_BOOL
    jmp parse_ordering_more
parse_ordering_done:
    pop rbx
    ret
parse_sum:
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
    call require_integer
    call next_token
    call parse_product
    call require_integer
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
    call require_integer
    call next_token
    call parse_unary
    call require_integer
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
    cmp QWORD PTR [rip + token], T_NOT
    je parse_unary_not
    call parse_primary
    jmp parse_unary_done
parse_unary_plus:
    call next_token
    call parse_unary
    call require_integer
    jmp parse_unary_done
parse_unary_minus:
    call next_token
    call skip_newlines
    cmp QWORD PTR [rip + token], T_NUMBER
    jne parse_unary_general_negative
    mov rsi, QWORD PTR [rip + number_value]
    test rsi, rsi
    jns parse_unary_general_negative
    mov QWORD PTR [rip + expression_type], TYPE_INT
    # Only the directly negated magnitude 2^63 is accepted as INT64_MIN.
    mov edi, IR_LITERAL
    xor edx, edx
    call append_ir
    call next_token
    jmp parse_unary_done
parse_unary_general_negative:
    call parse_unary
    call require_integer
    mov edi, IR_NEG
    xor esi, esi
    xor edx, edx
    call append_ir
    jmp parse_unary_done
parse_unary_not:
    call next_token
    call parse_unary
    call require_bool
    mov edi, IR_NOT
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
    je parse_name_expression
    cmp rax, T_TRUE
    je parse_boolean_literal
    cmp rax, T_FALSE
    je parse_boolean_literal
    cmp rax, T_LP
    jne syntax_error
    call next_token
    call parse_expression
    mov edi, T_RP
    jmp expect_token
parse_boolean_literal:
    cmp rax, T_TRUE
    sete sil
    movzx esi, sil
    mov QWORD PTR [rip + expression_type], TYPE_BOOL
    mov edi, IR_LITERAL
    xor edx, edx
    call append_ir
    jmp next_token
parse_integer_literal:
    mov QWORD PTR [rip + expression_type], TYPE_INT
    mov rsi, QWORD PTR [rip + number_value]
    test rsi, rsi
    js number_range_error
    mov edi, IR_LITERAL
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
    shl rax, 6
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
    # Parameters use this path directly; locals also check at their declaration.
    cmp rax, -1
    je declare_symbol_new
    shl rax, 6
    lea rcx, [rip + symbols]
    mov r8, QWORD PTR [rip + scope_depth]
    cmp QWORD PTR [rcx + rax + 40], r8
    je duplicate_symbol_error
declare_symbol_new:
    mov rcx, rdx
    mov rax, QWORD PTR [rip + symbol_count]
    cmp rax, SYMBOL_LIMIT
    jae limit_error
    mov rdx, rax
    shl rdx, 6
    lea r8, [rip + symbols]
    add r8, rdx
    mov rdx, QWORD PTR [rip + pending_name_offset]
    mov QWORD PTR [r8], rdx
    mov rdx, QWORD PTR [rip + pending_name_length]
    mov QWORD PTR [r8 + 8], rdx
    mov rdx, QWORD PTR [rip + frame_local_count]
    mov QWORD PTR [r8 + 16], rdx
    inc QWORD PTR [rip + frame_local_count]
    mov rdx, QWORD PTR [rip + pending_mutable]
    mov QWORD PTR [r8 + 24], rdx
    mov rdx, QWORD PTR [rip + expression_type]
    mov QWORD PTR [r8 + 32], rdx
    mov rdx, QWORD PTR [rip + scope_depth]
    mov QWORD PTR [r8 + 40], rdx
    mov QWORD PTR [r8 + 56], rcx
    lea r9, [rip + symbol_buckets]
    mov rdx, QWORD PTR [r9 + rcx * 8]
    mov QWORD PTR [r8 + 48], rdx
    mov r8, r9
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

require_integer:
    cmp QWORD PTR [rip + expression_type], TYPE_INT
    jne type_error
    ret
require_bool:
    cmp QWORD PTR [rip + expression_type], TYPE_BOOL
    jne type_error
    ret
type_error:
    lea rsi, [rip + type_message]
    jmp die
loop_error:
    lea rsi, [rip + loop_message]
    jmp die
