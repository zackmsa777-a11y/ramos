# Intrinsic records: name pointer/length, arity, result type, three argument
# types, runtime file offset. Name resolution preserves local shadowing.
.equ BUILTIN_COUNT, 17
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
arg_count_name: .ascii "arg_count"
arg_name: .ascii "arg"
read_file_name: .ascii "read_file"
write_file_name: .ascii "write_file"
io_error_name: .ascii "io_error"
stderr_name: .ascii "stderr"
exit_name: .ascii "exit"
platform_name: .ascii "platform"
read_line_name: .ascii "read_line"
stdin_eof_name: .ascii "stdin_eof"
int_to_text_name: .ascii "int_to_text"
text_to_int_name: .ascii "text_to_int"
parse_error_name: .ascii "parse_error"
.balign 8
builtin_signatures:
    .quad buffer_name, 6, 1, TYPE_BUFFER, TYPE_INT, 0, 0, RUNTIME_BUFFER_NEW_FILE
    .quad buffer_len_name, 10, 1, TYPE_INT, TYPE_BUFFER, 0, 0, RUNTIME_BUFFER_LEN_FILE
    .quad buffer_get_name, 10, 2, TYPE_INT, TYPE_BUFFER, TYPE_INT, 0, RUNTIME_BUFFER_GET_FILE
    .quad buffer_set_name, 10, 3, TYPE_VOID, TYPE_BUFFER, TYPE_INT, TYPE_INT, RUNTIME_BUFFER_SET_FILE
    .quad arg_count_name, 9, 0, TYPE_INT, 0, 0, 0, RUNTIME_ARG_COUNT_FILE
    .quad arg_name, 3, 1, TYPE_BUFFER, TYPE_INT, 0, 0, RUNTIME_ARG_FILE
    .quad read_file_name, 9, 1, TYPE_BUFFER, TYPE_BUFFER, 0, 0, RUNTIME_READ_FILE_FILE
    .quad write_file_name, 10, 3, TYPE_INT, TYPE_BUFFER, TYPE_BUFFER, TYPE_INT, RUNTIME_WRITE_FILE_FILE
    .quad io_error_name, 8, 0, TYPE_INT, 0, 0, 0, RUNTIME_IO_ERROR_FILE
    .quad stderr_name, 6, 1, TYPE_VOID, TYPE_BUFFER, 0, 0, RUNTIME_STDERR_FILE
    .quad exit_name, 4, 1, TYPE_VOID, TYPE_INT, 0, 0, RUNTIME_EXIT_FILE
    .quad platform_name, 8, 0, TYPE_INT, 0, 0, 0, RUNTIME_PLATFORM_FILE
    .quad read_line_name, 9, 0, TYPE_BUFFER, 0, 0, 0, RUNTIME_READ_LINE_FILE
    .quad stdin_eof_name, 9, 0, TYPE_BOOL, 0, 0, 0, RUNTIME_STDIN_EOF_FILE
    .quad int_to_text_name, 11, 1, TYPE_BUFFER, TYPE_INT, 0, 0, RUNTIME_INT_TO_TEXT_FILE
    .quad text_to_int_name, 11, 1, TYPE_INT, TYPE_BUFFER, 0, 0, RUNTIME_TEXT_TO_INT_FILE
    .quad parse_error_name, 11, 0, TYPE_INT, 0, 0, 0, RUNTIME_PARSE_ERROR_FILE
.section .text
