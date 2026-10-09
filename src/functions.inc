# Function records (64 bytes): source name offset/length, arity, return type,
# frame slots, entry label, reserved, reserved. Parameter records (32 bytes):
# name offset/length, type, reserved. Signatures are bounded and discovered
# before body checking, supporting forward calls and mutual recursion.
find_function:
    push rbx
    push r12
    push r13
    mov r12, rdi
    mov r13, rsi
    xor ebx, ebx
find_function_more:
    cmp rbx, QWORD PTR [rip + function_count]
    jae find_function_missing
    mov rax, rbx
    shl rax, 6
    lea r8, [rip + functions]
    add r8, rax
    cmp QWORD PTR [r8 + 8], r13
    jne find_function_next
    lea rdi, [rip + source_buffer]
    add rdi, QWORD PTR [r8]
    lea rsi, [rip + source_buffer]
    add rsi, r12
    mov rcx, r13
    repe cmpsb
    je find_function_found
find_function_next:
    inc rbx
    jmp find_function_more
find_function_missing:
    mov rax, -1
    jmp find_function_done
find_function_found:
    mov rax, rbx
find_function_done:
    pop r13
    pop r12
    pop rbx
    ret

parse_type:
    mov eax, TYPE_INT
    cmp QWORD PTR [rip + token], T_INT64
    je parse_type_done
    mov eax, TYPE_BOOL
    cmp QWORD PTR [rip + token], T_BOOL
    je parse_type_done
    mov eax, TYPE_VOID
    cmp QWORD PTR [rip + token], T_VOID
    jne syntax_error
parse_type_done:
    push rax
    call next_token
    pop rax
    ret

reset_lexer:
    mov QWORD PTR [rip + cursor], 0
    mov QWORD PTR [rip + line], 1
    mov QWORD PTR [rip + column], 1
    mov QWORD PTR [rip + data_length], 0
    jmp next_token

discover_functions:
    push rbx
    push r12
    push r13
    push r14
    push r15
    mov QWORD PTR [rip + main_function], -1
    call reset_lexer
discover_next:
    call skip_newlines
    cmp QWORD PTR [rip + token], T_EOF
    je discover_done
    mov edi, T_FN
    call expect_token
    call skip_newlines
    cmp QWORD PTR [rip + token], T_IDENT
    je discover_name
    cmp QWORD PTR [rip + token], T_MAIN
    jne syntax_error
discover_name:
    mov rdi, QWORD PTR [rip + identifier_offset]
    mov rsi, QWORD PTR [rip + identifier_length]
    call find_function
    cmp rax, -1
    jne function_error
    mov rbx, QWORD PTR [rip + function_count]
    cmp rbx, FUNCTION_LIMIT
    jae limit_error
    mov rax, rbx
    shl rax, 6
    lea r14, [rip + functions]
    add r14, rax
    mov rax, QWORD PTR [rip + identifier_offset]
    mov QWORD PTR [r14], rax
    mov rax, QWORD PTR [rip + identifier_length]
    mov QWORD PTR [r14 + 8], rax
    cmp QWORD PTR [rip + token], T_MAIN
    jne discover_not_main
    mov QWORD PTR [rip + main_function], rbx
discover_not_main:
    call new_label
    mov QWORD PTR [r14 + 40], rax
    inc QWORD PTR [rip + function_count]
    call next_token
    mov edi, T_LP
    call expect_token
    call skip_newlines
    xor r12d, r12d
    cmp QWORD PTR [rip + token], T_RP
    je discover_parameters_done
discover_parameter:
    cmp r12, PARAMETER_LIMIT
    jae limit_error
    cmp QWORD PTR [rip + token], T_IDENT
    jne syntax_error
    mov rax, rbx
    shl rax, 4
    add rax, r12
    shl rax, 5
    lea r15, [rip + parameters]
    add r15, rax
    mov rax, QWORD PTR [rip + identifier_offset]
    mov QWORD PTR [r15], rax
    mov rax, QWORD PTR [rip + identifier_length]
    mov QWORD PTR [r15 + 8], rax
    call next_token
    mov edi, T_COLON
    call expect_token
    call skip_newlines
    call parse_type
    cmp eax, TYPE_VOID
    je type_error
    mov QWORD PTR [r15 + 16], rax
    inc r12
    call skip_newlines
    cmp QWORD PTR [rip + token], T_COMMA
    jne discover_parameters_done
    call next_token
    call skip_newlines
    jmp discover_parameter
discover_parameters_done:
    mov QWORD PTR [r14 + 16], r12
    mov edi, T_RP
    call expect_token
    call skip_newlines
    mov eax, TYPE_VOID
    cmp QWORD PTR [rip + token], T_ARROW
    jne discover_result_done
    call next_token
    call skip_newlines
    call parse_type
discover_result_done:
    mov QWORD PTR [r14 + 24], rax
    cmp rbx, QWORD PTR [rip + main_function]
    jne discover_body
    test r12, r12
    jnz function_error
    cmp eax, TYPE_VOID
    jne function_error
discover_body:
    mov edi, T_LB
    call expect_token
    mov r13d, 1
discover_body_token:
    cmp QWORD PTR [rip + token], T_EOF
    je syntax_error
    cmp QWORD PTR [rip + token], T_LB
    jne discover_body_close
    inc r13
discover_body_close:
    cmp QWORD PTR [rip + token], T_RB
    jne discover_body_advance
    dec r13
discover_body_advance:
    call next_token
    test r13, r13
    jnz discover_body_token
    jmp discover_next
discover_done:
    cmp QWORD PTR [rip + main_function], -1
    je function_error
    pop r15
    pop r14
    pop r13
    pop r12
    pop rbx
    ret

compile_functions:
    push rbx
    push r12
    push r14
    mov QWORD PTR [rip + current_function], 0
    call reset_lexer
compile_function_next:
    call skip_newlines
    cmp QWORD PTR [rip + token], T_EOF
    je compile_functions_done
    mov rax, QWORD PTR [rip + current_function]
    shl rax, 6
    lea rbx, [rip + functions]
    add rbx, rax
    mov rax, QWORD PTR [rip + symbol_count]
    mov QWORD PTR [rip + function_symbol_base], rax
    mov QWORD PTR [rip + frame_local_count], 0
    mov QWORD PTR [rip + loop_start], 0
    mov QWORD PTR [rip + loop_end], 0
    mov rax, QWORD PTR [rbx + 24]
    mov QWORD PTR [rip + current_return_type], rax
    # Signature syntax has already been checked against these exact bytes.
compile_skip_header:
    cmp QWORD PTR [rip + token], T_LB
    je compile_parameters
    cmp QWORD PTR [rip + token], T_EOF
    je syntax_error
    call next_token
    jmp compile_skip_header
compile_parameters:
    mov QWORD PTR [rip + scope_depth], 1
    xor r12d, r12d
compile_parameter_more:
    cmp r12, QWORD PTR [rbx + 16]
    jae compile_body
    mov rax, QWORD PTR [rip + current_function]
    shl rax, 4
    add rax, r12
    shl rax, 5
    lea r14, [rip + parameters]
    add r14, rax
    mov rax, QWORD PTR [r14]
    mov QWORD PTR [rip + pending_name_offset], rax
    mov rax, QWORD PTR [r14 + 8]
    mov QWORD PTR [rip + pending_name_length], rax
    mov rax, QWORD PTR [r14 + 16]
    mov QWORD PTR [rip + expression_type], rax
    mov QWORD PTR [rip + pending_mutable], 0
    call declare_symbol
    inc r12
    jmp compile_parameter_more
compile_body:
    mov QWORD PTR [rip + scope_depth], 0
    mov edi, IR_FUNCTION
    mov rsi, QWORD PTR [rip + current_function]
    xor edx, edx
    call append_ir
    call parse_block
    mov rax, QWORD PTR [rip + frame_local_count]
    mov QWORD PTR [rbx + 32], rax
    cmp QWORD PTR [rbx + 24], TYPE_VOID
    je compile_function_end
    cmp QWORD PTR [rip + block_returns], 1
    jne return_error
compile_function_end:
    # Void fallthrough returns zero internally; value fallthrough was rejected.
    # A value function's extra epilogue is unreachable and bounds every frame.
    mov edi, IR_RETURN
    xor esi, esi
    xor edx, edx
    call append_ir
    inc QWORD PTR [rip + current_function]
    jmp compile_function_next
compile_functions_done:
    pop r14
    pop r12
    pop rbx
    ret

# Consume an identifier, then distinguish assignment from a call statement.
# Source slices and call indices live on the compiler stack, so nested calls
# never overwrite a pending declaration or an earlier argument.
parse_named_action:
    push rbx
    push r12
    push r13
    push r14
    mov r13, QWORD PTR [rip + error_line]
    mov r14, QWORD PTR [rip + error_column]
    mov rbx, QWORD PTR [rip + identifier_offset]
    mov r12, QWORD PTR [rip + identifier_length]
    call next_token
    mov rdi, rbx
    mov rsi, r12
    call find_symbol
    cmp QWORD PTR [rip + token], T_LP
    je parse_named_call
    cmp rax, -1
    je parse_named_action_undefined
    mov QWORD PTR [rip + pending_slot], rax
    shl rax, 6
    lea rcx, [rip + symbols]
    cmp QWORD PTR [rcx + rax + 24], 0
    je immutable_symbol_error
    mov edi, T_EQUAL
    call expect_token
    call parse_expression
    mov rax, QWORD PTR [rip + pending_slot]
    shl rax, 6
    lea rcx, [rip + symbols]
    mov rdx, QWORD PTR [rip + expression_type]
    cmp QWORD PTR [rcx + rax + 32], rdx
    jne type_error
    mov rsi, QWORD PTR [rcx + rax + 16]
    mov edi, IR_STORE
    xor edx, edx
    call append_ir
    jmp parse_named_done
parse_named_call:
    cmp rax, -1
    jne parse_named_action_invalid_call
    mov rdi, rbx
    mov rsi, r12
    call find_function
    cmp rax, -1
    je parse_named_action_invalid_call
    call parse_call
    mov edi, IR_DROP
    xor esi, esi
    xor edx, edx
    call append_ir
parse_named_done:
    pop r14
    pop r13
    pop r12
    pop rbx
    ret

parse_named_action_undefined:
    mov QWORD PTR [rip + error_line], r13
    mov QWORD PTR [rip + error_column], r14
    jmp undefined_symbol_error
parse_named_action_invalid_call:
    mov QWORD PTR [rip + error_line], r13
    mov QWORD PTR [rip + error_column], r14
    jmp call_error

parse_name_expression:
    push rbx
    push r12
    push r13
    push r14
    mov r13, QWORD PTR [rip + error_line]
    mov r14, QWORD PTR [rip + error_column]
    mov rbx, QWORD PTR [rip + identifier_offset]
    mov r12, QWORD PTR [rip + identifier_length]
    call next_token
    mov rdi, rbx
    mov rsi, r12
    call find_symbol
    cmp QWORD PTR [rip + token], T_LP
    je parse_name_call
    cmp rax, -1
    je parse_name_expression_undefined
    shl rax, 6
    lea rcx, [rip + symbols]
    mov rdx, QWORD PTR [rcx + rax + 32]
    mov QWORD PTR [rip + expression_type], rdx
    mov rsi, QWORD PTR [rcx + rax + 16]
    mov edi, IR_LOAD
    xor edx, edx
    call append_ir
    jmp parse_name_done
parse_name_call:
    cmp rax, -1
    jne parse_name_expression_invalid_call
    mov rdi, rbx
    mov rsi, r12
    call find_function
    cmp rax, -1
    je parse_name_expression_invalid_call
    call parse_call
    cmp QWORD PTR [rip + expression_type], TYPE_VOID
    je type_error
parse_name_done:
    pop r14
    pop r13
    pop r12
    pop rbx
    ret

parse_name_expression_undefined:
    mov QWORD PTR [rip + error_line], r13
    mov QWORD PTR [rip + error_column], r14
    jmp undefined_symbol_error
parse_name_expression_invalid_call:
    mov QWORD PTR [rip + error_line], r13
    mov QWORD PTR [rip + error_column], r14
    jmp call_error

# rax = function index; current token = opening parenthesis.
parse_call:
    push rbx
    push r12
    push r13
    mov rbx, rax
    cmp rbx, QWORD PTR [rip + main_function]
    je call_error
    mov rax, rbx
    shl rax, 6
    lea r13, [rip + functions]
    add r13, rax
    call next_token
    call skip_newlines
    xor r12d, r12d
    cmp QWORD PTR [rip + token], T_RP
    je parse_call_close
parse_call_argument:
    cmp r12, QWORD PTR [r13 + 16]
    jae call_error
    call parse_expression
    mov rax, rbx
    shl rax, 4
    add rax, r12
    shl rax, 5
    lea rcx, [rip + parameters]
    mov rdx, QWORD PTR [rip + expression_type]
    cmp QWORD PTR [rcx + rax + 16], rdx
    jne type_error
    inc r12
    call skip_newlines
    cmp QWORD PTR [rip + token], T_COMMA
    jne parse_call_close
    call next_token
    call skip_newlines
    jmp parse_call_argument
parse_call_close:
    cmp r12, QWORD PTR [r13 + 16]
    jne call_error
    mov edi, T_RP
    call expect_token
    mov edi, IR_CALL
    mov rsi, rbx
    mov rdx, r12
    call append_ir
    mov rax, QWORD PTR [r13 + 24]
    mov QWORD PTR [rip + expression_type], rax
    pop r13
    pop r12
    pop rbx
    ret

parse_return:
    call next_token
    cmp QWORD PTR [rip + current_return_type], TYPE_VOID
    jne parse_return_value
    cmp QWORD PTR [rip + token], T_NL
    je parse_return_void
    cmp QWORD PTR [rip + token], T_RB
    jne return_error
parse_return_void:
    xor esi, esi
    jmp parse_return_emit
parse_return_value:
    cmp QWORD PTR [rip + token], T_NL
    je return_error
    cmp QWORD PTR [rip + token], T_RB
    je return_error
    call parse_expression
    mov rax, QWORD PTR [rip + expression_type]
    cmp rax, QWORD PTR [rip + current_return_type]
    jne return_error
    mov esi, 1
parse_return_emit:
    mov edi, IR_RETURN
    xor edx, edx
    call append_ir
    mov QWORD PTR [rip + statement_returns], 1
    ret
function_error:
    lea rsi, [rip + function_message]
    jmp die
call_error:
    lea rsi, [rip + call_message]
    jmp die
return_error:
    lea rsi, [rip + return_message]
    jmp die
