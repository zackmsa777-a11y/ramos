# Intrinsic records: name pointer/length, arity, result type, three argument
# types, runtime file offset. Name resolution preserves local shadowing.
.equ BUILTIN_COUNT, 4
find_builtin:
    push rbx
    push r12
    push r13
    mov r12, rdi
    mov r13, rsi
    xor ebx, ebx
find_builtin_more:
    cmp ebx, BUILTIN_COUNT
    jae find_builtin_missing
    mov rax, rbx
    shl rax, 6
    lea r8, [rip + builtin_signatures]
    add r8, rax
    cmp QWORD PTR [r8 + 8], r13
    jne find_builtin_next
    mov rsi, QWORD PTR [r8]
    lea rdi, [rip + source_buffer]
    add rdi, r12
    mov rcx, r13
    repe cmpsb
    je find_builtin_found
find_builtin_next:
    inc ebx
    jmp find_builtin_more
find_builtin_missing:
    mov rax, -1
    jmp find_builtin_done
find_builtin_found:
    mov eax, ebx
find_builtin_done:
    pop r13
    pop r12
    pop rbx
    ret

# Return user index or FUNCTION_LIMIT+intrinsic index, or -1.
find_callable:
    push rdi
    push rsi
    call find_function
    pop rsi
    pop rdi
    cmp rax, -1
    jne find_callable_done
    call find_builtin
    cmp rax, -1
    je find_callable_done
    add rax, FUNCTION_LIMIT
find_callable_done:
    ret

parse_builtin_call:
    push rbx
    push r12
    push r13
    sub rax, FUNCTION_LIMIT
    mov rbx, rax
    shl rax, 6
    lea r13, [rip + builtin_signatures]
    add r13, rax
    call next_token
    call skip_newlines
    xor r12d, r12d
    cmp QWORD PTR [rip + token], T_RP
    je parse_builtin_close
parse_builtin_argument:
    cmp r12, QWORD PTR [r13 + 16]
    jae call_error
    call parse_expression
    mov rax, QWORD PTR [rip + expression_type]
    cmp rax, QWORD PTR [r13 + r12 * 8 + 32]
    jne type_error
    inc r12
    call skip_newlines
    cmp QWORD PTR [rip + token], T_COMMA
    jne parse_builtin_close
    call next_token
    call skip_newlines
    jmp parse_builtin_argument
parse_builtin_close:
    cmp r12, QWORD PTR [r13 + 16]
    jne call_error
    mov edi, T_RP
    call expect_token
    mov edi, IR_BUILTIN
    mov rsi, rbx
    xor edx, edx
    call append_ir
    mov rax, QWORD PTR [r13 + 24]
    mov QWORD PTR [rip + expression_type], rax
    pop r13
    pop r12
    pop rbx
    ret

.section .rodata
buffer_name: .ascii "buffer"
buffer_len_name: .ascii "buffer_len"
buffer_get_name: .ascii "buffer_get"
buffer_set_name: .ascii "buffer_set"
.balign 8
builtin_signatures:
    .quad buffer_name, 6, 1, TYPE_BUFFER, TYPE_INT, 0, 0, RUNTIME_BUFFER_NEW_FILE
    .quad buffer_len_name, 10, 1, TYPE_INT, TYPE_BUFFER, 0, 0, RUNTIME_BUFFER_LEN_FILE
    .quad buffer_get_name, 10, 2, TYPE_INT, TYPE_BUFFER, TYPE_INT, 0, RUNTIME_BUFFER_GET_FILE
    .quad buffer_set_name, 10, 3, TYPE_VOID, TYPE_BUFFER, TYPE_INT, TYPE_INT, RUNTIME_BUFFER_SET_FILE
.section .text
