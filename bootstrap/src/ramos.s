# Ramos 0.7 bootstrap: x86-64 Linux compiler. GNU assembler, Intel syntax.
# No libc, LLVM, C backend, or external code generation.
# Internal routines use caller-saved rax, rcx, rdx, rsi, rdi, r8-r11.
.intel_syntax noprefix
.global _start

.equ SOURCE_LIMIT, 1048576
.equ STATEMENT_LIMIT, 65536
.equ DATA_LIMIT, SOURCE_LIMIT + STATEMENT_LIMIT
.equ OUTPUT_LIMIT, 4194304
.equ CODE_OFFSET, 4096
.equ LOAD_BASE, 0x400000
.equ AT_FDCWD, -100
.equ IR_LIMIT, 262144
.equ SYMBOL_LIMIT, 4096
.equ SYMBOL_BUCKETS, 8192
.equ EXPRESSION_LIMIT, 128
.equ T_EOF, 0
.equ T_NL, 1
.equ T_FN, 2
.equ T_MAIN, 3
.equ T_PRINT, 4
.equ T_LP, 5
.equ T_RP, 6
.equ T_LB, 7
.equ T_RB, 8
.equ T_STRING, 9
.equ T_UNKNOWN, 10
.equ T_IDENT, 11
.equ T_NUMBER, 12
.equ T_PLUS, 13
.equ T_MINUS, 14
.equ T_STAR, 15
.equ T_SLASH, 16
.equ T_PERCENT, 17
.equ T_EQUAL, 18
.equ T_LET, 19
.equ T_VAR, 20
.equ T_TRUE, 21
.equ T_FALSE, 22
.equ T_IF, 23
.equ T_ELSE, 24
.equ T_WHILE, 25
.equ T_BREAK, 26
.equ T_CONTINUE, 27
.equ T_NOT, 28
.equ T_EQ, 29
.equ T_NE, 30
.equ T_LT, 31
.equ T_LE, 32
.equ T_GT, 33
.equ T_GE, 34
.equ T_COLON, 35
.equ T_COMMA, 36
.equ T_ARROW, 37
.equ T_RETURN, 38
.equ T_INT64, 39
.equ T_BOOL, 40
.equ T_VOID, 41
.equ T_BYTES, 42
.equ BUFFER_LIMIT, 1048576
.equ BUFFER_ARENA_LIMIT, 16777216
.equ FUNCTION_LIMIT, 256
.equ PARAMETER_LIMIT, 16
.equ CALL_DEPTH_LIMIT, 64
.equ BLOCK_LIMIT, 128
.equ TYPE_INT, 0
.equ TYPE_BOOL, 1
.equ TYPE_VOID, 2
.equ TYPE_BUFFER, 3
.equ IR_STRING, 1
.equ IR_LITERAL, 2
.equ IR_LOAD, 3
.equ IR_STORE, 4
.equ IR_ADD, 5
.equ IR_SUB, 6
.equ IR_MUL, 7
.equ IR_DIV, 8
.equ IR_MOD, 9
.equ IR_NEG, 10
.equ IR_PRINT_INT, 11

.equ IR_NOT, 12
.equ IR_EQ, 13
.equ IR_NE, 14
.equ IR_LT, 15
.equ IR_LE, 16
.equ IR_GT, 17
.equ IR_GE, 18
.equ IR_PRINT_BOOL, 19
.equ IR_LABEL, 20
.equ IR_JUMP, 21
.equ IR_JZ, 22
.equ IR_FUNCTION, 23
.equ IR_CALL, 24
.equ IR_RETURN, 25
.equ IR_DROP, 26
.equ IR_BUILTIN, 27
.equ IR_BUFFER_LITERAL, 28
.equ IR_PRINT_BUFFER, 29

.section .text
_start:
    cld
    mov QWORD PTR [rip + directory_fd], AT_FDCWD
    mov QWORD PTR [rip + line], 1
    mov QWORD PTR [rip + column], 1
    mov QWORD PTR [rip + error_line], 1
    mov QWORD PTR [rip + error_column], 1
    lea rax, [rip + compiler_name]
    mov QWORD PTR [rip + source_name], rax
    mov r14, rsp
    mov rax, QWORD PTR [r14]
    cmp rax, 2
    je cli_info
    cmp rax, 5
    je cli_build
    cmp rax, 6
    jne usage_error
    mov rdi, QWORD PTR [r14 + 48]
    lea rsi, [rip + arg_force]
    call string_equal
    test eax, eax
    jnz usage_error
    mov BYTE PTR [rip + force_output], 1
cli_build:
    mov rdi, QWORD PTR [r14 + 16]
    lea rsi, [rip + arg_build]
    call string_equal
    test eax, eax
    jnz usage_error
    mov rdi, QWORD PTR [r14 + 32]
    lea rsi, [rip + arg_output]
    call string_equal
    test eax, eax
    jnz usage_error
    mov rax, QWORD PTR [r14 + 24]
    mov QWORD PTR [rip + source_name], rax
    mov rax, QWORD PTR [r14 + 40]
    mov QWORD PTR [rip + destination_name], rax
    call read_source
    call validate_utf8
    call parse_program
    call generate_executable
    call publish_executable
    xor edi, edi
    jmp exit_process
cli_info:
    mov rdi, QWORD PTR [r14 + 16]
    lea rsi, [rip + arg_help]
    call string_equal
    test eax, eax
    jz show_help
    mov rdi, QWORD PTR [r14 + 16]
    lea rsi, [rip + arg_version]
    call string_equal
    test eax, eax
    jnz usage_error
    lea rsi, [rip + version_message]
    jmp info_message
show_help:
    lea rsi, [rip + help_message]
info_message:
    mov edi, 1
    call write_cstring
    test rax, rax
    js output_error
    xor edi, edi
    jmp exit_process
usage_error:
    lea rsi, [rip + usage_message]
    jmp die

# Return eax=0 when the two NUL-terminated strings are equal.
string_equal:
    xor ecx, ecx
string_equal_loop:
    mov al, BYTE PTR [rdi + rcx]
    cmp al, BYTE PTR [rsi + rcx]
    jne string_not_equal
    test al, al
    jz string_is_equal
    inc rcx
    jmp string_equal_loop
string_not_equal:
    mov eax, 1
    ret
string_is_equal:
    xor eax, eax
    ret

# fd=rdi, bytes=rsi, length=rdx. Return 0 or a negative Linux errno.
write_all:
    test rdx, rdx
    jz write_finished
write_again:
    mov eax, 1
    syscall
    cmp rax, -4
    je write_again
    test rax, rax
    js write_return
    jz write_zero
    add rsi, rax
    sub rdx, rax
    jnz write_again
write_finished:
    xor eax, eax
write_return:
    ret
write_zero:
    mov rax, -5
    ret

write_cstring:
    xor edx, edx
cstring_length:
    cmp BYTE PTR [rsi + rdx], 0
    je write_all
    inc rdx
    jmp cstring_length

# Convert unsigned rax to decimal in number_buffer, return rsi and rdx.
decimal_string:
    lea rsi, [rip + number_buffer + 32]
    mov r8, rsi
    mov r9d, 10
decimal_digit:
    xor edx, edx
    div r9
    add dl, '0'
    dec rsi
    mov BYTE PTR [rsi], dl
    test rax, rax
    jnz decimal_digit
    mov rdx, r8
    sub rdx, rsi
    ret

# A fatal error also removes any unpublished temporary file.
die:
    push rsi
    cmp BYTE PTR [rip + temporary_active], 0
    je error_diagnostic
    mov eax, 263
    mov rdi, QWORD PTR [rip + directory_fd]
    lea rsi, [rip + temporary_path]
    xor edx, edx
    syscall
error_diagnostic:
    mov edi, 2
    mov rsi, QWORD PTR [rip + source_name]
    call write_cstring
    mov edi, 2
    lea rsi, [rip + colon]
    call write_cstring
    mov rax, QWORD PTR [rip + error_line]
    call decimal_string
    mov edi, 2
    call write_all
    mov edi, 2
    lea rsi, [rip + colon]
    call write_cstring
    mov rax, QWORD PTR [rip + error_column]
    call decimal_string
    mov edi, 2
    call write_all
    mov edi, 2
    lea rsi, [rip + error_prefix]
    call write_cstring
    pop rsi
    mov edi, 2
    call write_cstring
    mov edi, 2
    lea rsi, [rip + newline_text]
    call write_cstring
    mov edi, 1
exit_process:
    mov eax, 60
    syscall
    ud2
input_error:
    lea rsi, [rip + input_message]
    jmp die
output_error:
    lea rsi, [rip + output_message]
    jmp die
limit_error:
    lea rsi, [rip + limit_message]
    jmp die
syntax_error:
    lea rsi, [rip + syntax_message]
    jmp die

read_source:
    push rbx
    push r12
    mov eax, 257
    mov rdi, AT_FDCWD
    mov rsi, QWORD PTR [rip + source_name]
    # O_CLOEXEC | O_NONBLOCK: reject FIFOs via fstat without blocking open.
    mov edx, 0x80800
    xor r10d, r10d
    syscall
    test rax, rax
    js input_error
    mov r12, rax
    mov eax, 5
    mov rdi, r12
    lea rsi, [rip + source_stat]
    syscall
    test rax, rax
    js input_error
    mov eax, DWORD PTR [rip + source_stat + 24]
    and eax, 0xf000
    cmp eax, 0x8000
    jne input_error
    cmp QWORD PTR [rip + source_stat + 48], SOURCE_LIMIT
    ja limit_error
    xor ebx, ebx
read_more:
    xor eax, eax
    mov rdi, r12
    lea rsi, [rip + source_buffer]
    add rsi, rbx
    mov edx, SOURCE_LIMIT + 1
    sub rdx, rbx
    syscall
    cmp rax, -4
    je read_more
    test rax, rax
    js input_error
    jz read_complete
    add rbx, rax
    cmp rbx, SOURCE_LIMIT
    ja limit_error
    jmp read_more
read_complete:
    mov QWORD PTR [rip + source_length], rbx
    mov eax, 3
    mov rdi, r12
    syscall
    test rax, rax
    js input_error
    pop r12
    pop rbx
    ret

# Validate canonical UTF-8, rejecting NUL, overlong forms, surrogate code
# points, truncated sequences, and code points beyond U+10FFFF.
validate_utf8:
    push rbx
    push r12
    push r13
    xor ebx, ebx
    mov r12d, 1
    mov r13d, 1
    lea rdi, [rip + source_buffer]
utf8_next:
    cmp rbx, QWORD PTR [rip + source_length]
    jae utf8_complete
    movzx eax, BYTE PTR [rdi + rbx]
    test al, al
    jz utf8_error
    cmp al, 0x80
    jb utf8_ascii
    cmp al, 0xc2
    jb utf8_error
    mov edx, 2
    cmp al, 0xdf
    jbe utf8_check_length
    mov edx, 3
    cmp al, 0xef
    jbe utf8_check_length
    mov edx, 4
    cmp al, 0xf4
    ja utf8_error
utf8_check_length:
    lea rcx, [rbx + rdx]
    cmp rcx, QWORD PTR [rip + source_length]
    ja utf8_error
    movzx r8d, BYTE PTR [rdi + rbx + 1]
    cmp al, 0xe0
    jne utf8_not_e0
    cmp r8b, 0xa0
    jb utf8_error
utf8_not_e0:
    cmp al, 0xed
    jne utf8_not_ed
    cmp r8b, 0x9f
    ja utf8_error
utf8_not_ed:
    cmp al, 0xf0
    jne utf8_not_f0
    cmp r8b, 0x90
    jb utf8_error
utf8_not_f0:
    cmp al, 0xf4
    jne utf8_continuations
    cmp r8b, 0x8f
    ja utf8_error
utf8_continuations:
    lea r8, [rdi + rbx]
    mov ecx, 1
utf8_continuation:
    movzx eax, BYTE PTR [r8 + rcx]
    cmp al, 0x80
    jb utf8_error
    cmp al, 0xbf
    ja utf8_error
    inc rcx
    cmp rcx, rdx
    jb utf8_continuation
    add rbx, rdx
    add r13, rdx
    jmp utf8_next
utf8_ascii:
    inc rbx
    cmp al, 10
    je utf8_line
    inc r13
    jmp utf8_next
utf8_line:
    inc r12
    mov r13d, 1
    jmp utf8_next
utf8_error:
    mov QWORD PTR [rip + error_line], r12
    mov QWORD PTR [rip + error_column], r13
    lea rsi, [rip + utf8_message]
    jmp die
utf8_complete:
    pop r13
    pop r12
    pop rbx
    ret

.macro STEP_BYTE
    inc rbx
    inc QWORD PTR [rip + column]
.endm

# The lexer streams tokens. Strings are decoded into a bounded arena;
# the parser emits bounded, typed expression and control-flow IR.
next_token:
    push rbx
    push r12
    push r13
    mov rbx, QWORD PTR [rip + cursor]
    lea r12, [rip + source_buffer]
lex_whitespace:
    cmp rbx, QWORD PTR [rip + source_length]
    jae lex_eof
    mov al, BYTE PTR [r12 + rbx]
    cmp al, ' '
    je lex_space
    cmp al, 9
    jne lex_start
lex_space:
    STEP_BYTE
    jmp lex_whitespace
lex_start:
    mov rax, QWORD PTR [rip + line]
    mov QWORD PTR [rip + error_line], rax
    mov rax, QWORD PTR [rip + column]
    mov QWORD PTR [rip + error_column], rax
    mov al, BYTE PTR [r12 + rbx]
    cmp al, 10
    je lex_newline
    cmp al, 13
    je lex_crlf
    cmp al, ':'
    je lex_colon
    cmp al, ','
    je lex_comma
    cmp al, '('
    je lex_lp
    cmp al, ')'
    je lex_rp
    cmp al, '{'
    je lex_lb
    cmp al, '}'
    je lex_rb
    cmp al, '"'
    je lex_string
    cmp al, '+'
    je lex_plus
    cmp al, '-'
    je lex_minus
    cmp al, '*'
    je lex_star
    cmp al, '/'
    je lex_slash
    cmp al, '%'
    je lex_percent
    cmp al, '='
    je lex_equal
    cmp al, '!'
    je lex_not
    cmp al, '<'
    je lex_lt
    cmp al, '>'
    je lex_gt
    cmp al, '0'
    jb lex_not_digit
    cmp al, '9'
    jbe lex_number
lex_not_digit:
    cmp al, '_'
    je lex_identifier
    cmp al, 'A'
    jb lex_unknown
    cmp al, 'Z'
    jbe lex_identifier
    cmp al, 'a'
    jb lex_unknown
    cmp al, 'z'
    jbe lex_identifier
lex_unknown:
    mov eax, T_UNKNOWN
    jmp lex_single
lex_plus:
    mov eax, T_PLUS
    jmp lex_single
lex_minus:
    mov eax, T_MINUS
    lea rcx, [rbx + 1]
    cmp rcx, QWORD PTR [rip + source_length]
    jae lex_single
    cmp BYTE PTR [r12 + rcx], '>'
    jne lex_single
    STEP_BYTE
    mov eax, T_ARROW
    jmp lex_single
lex_colon:
    mov eax, T_COLON
    jmp lex_single
lex_comma:
    mov eax, T_COMMA
    jmp lex_single
lex_star:
    mov eax, T_STAR
    jmp lex_single
lex_slash:
    mov eax, T_SLASH
    jmp lex_single
lex_percent:
    mov eax, T_PERCENT
    jmp lex_single
# Two-character operators check the source bound before lookahead.
lex_equal:
    mov eax, T_EQUAL
    mov edx, T_EQ
    jmp lex_optional_equal
lex_not:
    mov eax, T_NOT
    mov edx, T_NE
    jmp lex_optional_equal
lex_lt:
    mov eax, T_LT
    mov edx, T_LE
    jmp lex_optional_equal
lex_gt:
    mov eax, T_GT
    mov edx, T_GE
lex_optional_equal:
    lea rcx, [rbx + 1]
    cmp rcx, QWORD PTR [rip + source_length]
    jae lex_single
    cmp BYTE PTR [r12 + rcx], '='
    jne lex_single
    STEP_BYTE
    mov eax, edx
    jmp lex_single
lex_lp:
    mov eax, T_LP
    jmp lex_single
lex_rp:
    mov eax, T_RP
    jmp lex_single
lex_lb:
    mov eax, T_LB
    jmp lex_single
lex_rb:
    mov eax, T_RB
lex_single:
    STEP_BYTE
    jmp lex_return
lex_crlf:
    inc rbx
    cmp rbx, QWORD PTR [rip + source_length]
    jae syntax_error
    cmp BYTE PTR [r12 + rbx], 10
    jne syntax_error
lex_newline:
    inc rbx
    inc QWORD PTR [rip + line]
    mov QWORD PTR [rip + column], 1
    mov eax, T_NL
    jmp lex_return
lex_eof:
    mov rax, QWORD PTR [rip + line]
    mov QWORD PTR [rip + error_line], rax
    mov rax, QWORD PTR [rip + column]
    mov QWORD PTR [rip + error_column], rax
    mov eax, T_EOF
    jmp lex_return
lex_identifier:
    mov r13, rbx
lex_identifier_more:
    STEP_BYTE
    cmp rbx, QWORD PTR [rip + source_length]
    jae lex_keyword
    mov al, BYTE PTR [r12 + rbx]
    cmp al, '_'
    je lex_identifier_more
    cmp al, '0'
    jb lex_keyword
    cmp al, '9'
    jbe lex_identifier_more
    cmp al, 'A'
    jb lex_keyword
    cmp al, 'Z'
    jbe lex_identifier_more
    cmp al, 'a'
    jb lex_keyword
    cmp al, 'z'
    jbe lex_identifier_more
lex_keyword:
    mov rdx, rbx
    sub rdx, r13
    mov QWORD PTR [rip + identifier_offset], r13
    mov QWORD PTR [rip + identifier_length], rdx
    mov eax, T_IDENT
    cmp rdx, 2
    jne lex_keyword_next_0
    cmp BYTE PTR [r12 + r13 + 0], 'f'
    jne lex_keyword_next_0
    cmp BYTE PTR [r12 + r13 + 1], 'n'
    jne lex_keyword_next_0
    mov eax, T_FN
    jmp lex_return
lex_keyword_next_0:
    cmp rdx, 4
    jne lex_keyword_next_1
    cmp BYTE PTR [r12 + r13 + 0], 'm'
    jne lex_keyword_next_1
    cmp BYTE PTR [r12 + r13 + 1], 'a'
    jne lex_keyword_next_1
    cmp BYTE PTR [r12 + r13 + 2], 'i'
    jne lex_keyword_next_1
    cmp BYTE PTR [r12 + r13 + 3], 'n'
    jne lex_keyword_next_1
    mov eax, T_MAIN
    jmp lex_return
lex_keyword_next_1:
    cmp rdx, 5
    jne lex_keyword_next_2
    cmp BYTE PTR [r12 + r13 + 0], 'p'
    jne lex_keyword_next_2
    cmp BYTE PTR [r12 + r13 + 1], 'r'
    jne lex_keyword_next_2
    cmp BYTE PTR [r12 + r13 + 2], 'i'
    jne lex_keyword_next_2
    cmp BYTE PTR [r12 + r13 + 3], 'n'
    jne lex_keyword_next_2
    cmp BYTE PTR [r12 + r13 + 4], 't'
    jne lex_keyword_next_2
    mov eax, T_PRINT
    jmp lex_return
lex_keyword_next_2:
    cmp rdx, 3
    jne lex_keyword_next_3
    cmp BYTE PTR [r12 + r13 + 0], 'l'
    jne lex_keyword_next_3
    cmp BYTE PTR [r12 + r13 + 1], 'e'
    jne lex_keyword_next_3
    cmp BYTE PTR [r12 + r13 + 2], 't'
    jne lex_keyword_next_3
    mov eax, T_LET
    jmp lex_return
lex_keyword_next_3:
    cmp rdx, 3
    jne lex_keyword_next_4
    cmp BYTE PTR [r12 + r13 + 0], 'v'
    jne lex_keyword_next_4
    cmp BYTE PTR [r12 + r13 + 1], 'a'
    jne lex_keyword_next_4
    cmp BYTE PTR [r12 + r13 + 2], 'r'
    jne lex_keyword_next_4
    mov eax, T_VAR
    jmp lex_return
lex_keyword_next_4:
    cmp rdx, 4
    jne lex_keyword_next_5
    cmp BYTE PTR [r12 + r13 + 0], 't'
    jne lex_keyword_next_5
    cmp BYTE PTR [r12 + r13 + 1], 'r'
    jne lex_keyword_next_5
    cmp BYTE PTR [r12 + r13 + 2], 'u'
    jne lex_keyword_next_5
    cmp BYTE PTR [r12 + r13 + 3], 'e'
    jne lex_keyword_next_5
    mov eax, T_TRUE
    jmp lex_return
lex_keyword_next_5:
    cmp rdx, 5
    jne lex_keyword_next_6
    cmp BYTE PTR [r12 + r13 + 0], 'f'
    jne lex_keyword_next_6
    cmp BYTE PTR [r12 + r13 + 1], 'a'
    jne lex_keyword_next_6
    cmp BYTE PTR [r12 + r13 + 2], 'l'
    jne lex_keyword_next_6
    cmp BYTE PTR [r12 + r13 + 3], 's'
    jne lex_keyword_next_6
    cmp BYTE PTR [r12 + r13 + 4], 'e'
    jne lex_keyword_next_6
    mov eax, T_FALSE
    jmp lex_return
lex_keyword_next_6:
    cmp rdx, 2
    jne lex_keyword_next_7
    cmp BYTE PTR [r12 + r13 + 0], 'i'
    jne lex_keyword_next_7
    cmp BYTE PTR [r12 + r13 + 1], 'f'
    jne lex_keyword_next_7
    mov eax, T_IF
    jmp lex_return
lex_keyword_next_7:
    cmp rdx, 4
    jne lex_keyword_next_8
    cmp BYTE PTR [r12 + r13 + 0], 'e'
    jne lex_keyword_next_8
    cmp BYTE PTR [r12 + r13 + 1], 'l'
    jne lex_keyword_next_8
    cmp BYTE PTR [r12 + r13 + 2], 's'
    jne lex_keyword_next_8
    cmp BYTE PTR [r12 + r13 + 3], 'e'
    jne lex_keyword_next_8
    mov eax, T_ELSE
    jmp lex_return
lex_keyword_next_8:
    cmp rdx, 5
    jne lex_keyword_next_9
    cmp BYTE PTR [r12 + r13 + 0], 'w'
    jne lex_keyword_next_9
    cmp BYTE PTR [r12 + r13 + 1], 'h'
    jne lex_keyword_next_9
    cmp BYTE PTR [r12 + r13 + 2], 'i'
    jne lex_keyword_next_9
    cmp BYTE PTR [r12 + r13 + 3], 'l'
    jne lex_keyword_next_9
    cmp BYTE PTR [r12 + r13 + 4], 'e'
    jne lex_keyword_next_9
    mov eax, T_WHILE
    jmp lex_return
lex_keyword_next_9:
    cmp rdx, 5
    jne lex_keyword_next_10
    cmp BYTE PTR [r12 + r13 + 0], 'b'
    jne lex_keyword_next_10
    cmp BYTE PTR [r12 + r13 + 1], 'r'
    jne lex_keyword_next_10
    cmp BYTE PTR [r12 + r13 + 2], 'e'
    jne lex_keyword_next_10
    cmp BYTE PTR [r12 + r13 + 3], 'a'
    jne lex_keyword_next_10
    cmp BYTE PTR [r12 + r13 + 4], 'k'
    jne lex_keyword_next_10
    mov eax, T_BREAK
    jmp lex_return
lex_keyword_next_10:
    cmp rdx, 8
    jne lex_keyword_next_11
    cmp BYTE PTR [r12 + r13 + 0], 'c'
    jne lex_keyword_next_11
    cmp BYTE PTR [r12 + r13 + 1], 'o'
    jne lex_keyword_next_11
    cmp BYTE PTR [r12 + r13 + 2], 'n'
    jne lex_keyword_next_11
    cmp BYTE PTR [r12 + r13 + 3], 't'
    jne lex_keyword_next_11
    cmp BYTE PTR [r12 + r13 + 4], 'i'
    jne lex_keyword_next_11
    cmp BYTE PTR [r12 + r13 + 5], 'n'
    jne lex_keyword_next_11
    cmp BYTE PTR [r12 + r13 + 6], 'u'
    jne lex_keyword_next_11
    cmp BYTE PTR [r12 + r13 + 7], 'e'
    jne lex_keyword_next_11
    mov eax, T_CONTINUE
    jmp lex_return
lex_keyword_next_11:
    cmp rdx, 6
    jne lex_keyword_next_12
    cmp BYTE PTR [r12 + r13 + 0], 'r'
    jne lex_keyword_next_12
    cmp BYTE PTR [r12 + r13 + 1], 'e'
    jne lex_keyword_next_12
    cmp BYTE PTR [r12 + r13 + 2], 't'
    jne lex_keyword_next_12
    cmp BYTE PTR [r12 + r13 + 3], 'u'
    jne lex_keyword_next_12
    cmp BYTE PTR [r12 + r13 + 4], 'r'
    jne lex_keyword_next_12
    cmp BYTE PTR [r12 + r13 + 5], 'n'
    jne lex_keyword_next_12
    mov eax, T_RETURN
    jmp lex_return
lex_keyword_next_12:
    cmp rdx, 5
    jne lex_keyword_next_13
    cmp BYTE PTR [r12 + r13 + 0], 'i'
    jne lex_keyword_next_13
    cmp BYTE PTR [r12 + r13 + 1], 'n'
    jne lex_keyword_next_13
    cmp BYTE PTR [r12 + r13 + 2], 't'
    jne lex_keyword_next_13
    cmp BYTE PTR [r12 + r13 + 3], '6'
    jne lex_keyword_next_13
    cmp BYTE PTR [r12 + r13 + 4], '4'
    jne lex_keyword_next_13
    mov eax, T_INT64
    jmp lex_return
lex_keyword_next_13:
    cmp rdx, 4
    jne lex_keyword_next_14
    cmp BYTE PTR [r12 + r13 + 0], 'b'
    jne lex_keyword_next_14
    cmp BYTE PTR [r12 + r13 + 1], 'o'
    jne lex_keyword_next_14
    cmp BYTE PTR [r12 + r13 + 2], 'o'
    jne lex_keyword_next_14
    cmp BYTE PTR [r12 + r13 + 3], 'l'
    jne lex_keyword_next_14
    mov eax, T_BOOL
    jmp lex_return
lex_keyword_next_14:
    cmp rdx, 4
    jne lex_keyword_next_15
    cmp BYTE PTR [r12 + r13 + 0], 'v'
    jne lex_keyword_next_15
    cmp BYTE PTR [r12 + r13 + 1], 'o'
    jne lex_keyword_next_15
    cmp BYTE PTR [r12 + r13 + 2], 'i'
    jne lex_keyword_next_15
    cmp BYTE PTR [r12 + r13 + 3], 'd'
    jne lex_keyword_next_15
    mov eax, T_VOID
    jmp lex_return
lex_keyword_next_15:
    cmp rdx, 5
    jne lex_keyword_next_16
    cmp BYTE PTR [r12 + r13], 'b'
    jne lex_keyword_next_16
    cmp BYTE PTR [r12 + r13 + 1], 'y'
    jne lex_keyword_next_16
    cmp BYTE PTR [r12 + r13 + 2], 't'
    jne lex_keyword_next_16
    cmp BYTE PTR [r12 + r13 + 3], 'e'
    jne lex_keyword_next_16
    cmp BYTE PTR [r12 + r13 + 4], 's'
    jne lex_keyword_next_16
    mov eax, T_BYTES
lex_keyword_next_16:
    jmp lex_return
lex_number:
    xor r13d, r13d
lex_number_digit:
    mov rdx, 922337203685477580
    cmp r13, rdx
    ja number_range_error
    jne lex_number_accumulate
    cmp al, '8'
    ja number_range_error
lex_number_accumulate:
    imul r13, r13, 10
    movzx edx, al
    sub edx, '0'
    add r13, rdx
    STEP_BYTE
    cmp rbx, QWORD PTR [rip + source_length]
    jae lex_number_end
    mov al, BYTE PTR [r12 + rbx]
    cmp al, '0'
    jb lex_number_end
    cmp al, '9'
    jbe lex_number_digit
lex_number_end:
    mov QWORD PTR [rip + number_value], r13
    mov eax, T_NUMBER
    jmp lex_return
number_range_error:
    lea rsi, [rip + number_message]
    jmp die
lex_string:
    STEP_BYTE
    mov r13, QWORD PTR [rip + data_length]
    mov QWORD PTR [rip + string_offset], r13
lex_string_byte:
    cmp rbx, QWORD PTR [rip + source_length]
    jae string_error
    mov al, BYTE PTR [r12 + rbx]
    cmp al, '"'
    je lex_string_end
    cmp al, 10
    je string_error
    cmp al, 13
    je string_error
    cmp al, 92
    je lex_escape
    call append_data_byte
    STEP_BYTE
    jmp lex_string_byte
lex_escape:
    STEP_BYTE
    cmp rbx, QWORD PTR [rip + source_length]
    jae string_error
    mov al, BYTE PTR [r12 + rbx]
    cmp al, 'n'
    je escape_newline
    cmp al, 't'
    je escape_tab
    cmp al, 'r'
    je escape_cr
    cmp al, '0'
    je escape_zero
    cmp al, '"'
    je escape_emit
    cmp al, 92
    jne string_error
    jmp escape_emit
escape_newline:
    mov al, 10
    jmp escape_emit
escape_tab:
    mov al, 9
    jmp escape_emit
escape_cr:
    mov al, 13
    jmp escape_emit
escape_zero:
    xor eax, eax
escape_emit:
    call append_data_byte
    STEP_BYTE
    jmp lex_string_byte
lex_string_end:
    STEP_BYTE
    mov rax, QWORD PTR [rip + data_length]
    sub rax, r13
    mov QWORD PTR [rip + string_length], rax
    mov eax, T_STRING
lex_return:
    mov QWORD PTR [rip + cursor], rbx
    mov QWORD PTR [rip + token], rax
    pop r13
    pop r12
    pop rbx
    ret
string_error:
    lea rsi, [rip + string_message]
    jmp die
append_data_byte:
    mov rcx, QWORD PTR [rip + data_length]
    cmp rcx, DATA_LIMIT
    jae limit_error
    lea rdi, [rip + data_buffer]
    mov BYTE PTR [rdi + rcx], al
    inc QWORD PTR [rip + data_length]
    ret

skip_newlines:
    cmp QWORD PTR [rip + token], T_NL
    jne newlines_done
    call next_token
    jmp skip_newlines
newlines_done:
    ret
expect_token:
    push rdi
    call skip_newlines
    pop rdi
    cmp QWORD PTR [rip + token], rdi
    jne syntax_error
    jmp next_token

.include "bootstrap/src/parsing.inc"
.include "bootstrap/src/functions.inc"
.include "bootstrap/src/buffers.inc"

.include "bootstrap/src/codegen.inc"
.include "bootstrap/src/function_codegen.inc"
.include "bootstrap/src/buffer_codegen.inc"

# Refuse aliases to the source, even with --force. Existing destinations
# require --force; renameat2(RENAME_NOREPLACE) also protects against races.
check_destination:
    mov eax, 262
    mov rdi, QWORD PTR [rip + directory_fd]
    mov rsi, QWORD PTR [rip + destination_basename]
    lea rdx, [rip + destination_stat]
    xor r10d, r10d
    syscall
    cmp rax, -2
    je destination_ok
    test rax, rax
    js output_error
    mov rax, QWORD PTR [rip + source_stat]
    cmp rax, QWORD PTR [rip + destination_stat]
    jne destination_exists
    mov rax, QWORD PTR [rip + source_stat + 8]
    cmp rax, QWORD PTR [rip + destination_stat + 8]
    je source_destination_error
destination_exists:
    cmp BYTE PTR [rip + force_output], 0
    je destination_exists_error
destination_ok:
    ret
source_destination_error:
    lea rsi, [rip + alias_message]
    jmp die
destination_exists_error:
    lea rsi, [rip + exists_message]
    jmp die

publish_executable:
    # Anchor publication to an opened destination directory. Use a short
    # independent temporary basename, preserving NAME_MAX-sized outputs.
    mov rsi, QWORD PTR [rip + destination_name]
    xor ecx, ecx
    xor edx, edx
scan_destination_path:
    cmp ecx, 4096
    jae output_error
    mov al, BYTE PTR [rsi + rcx]
    test al, al
    jz split_destination_path
    cmp al, '/'
    jne scan_destination_next
    lea edx, [ecx + 1]
scan_destination_next:
    inc ecx
    jmp scan_destination_path
split_destination_path:
    test ecx, ecx
    jz output_error
    lea rax, [rsi + rdx]
    cmp BYTE PTR [rax], 0
    je output_error
    mov QWORD PTR [rip + destination_basename], rax
    lea rdi, [rip + directory_path]
    test edx, edx
    jz current_destination_directory
    mov ecx, edx
    rep movsb
    mov BYTE PTR [rdi], 0
    jmp open_destination_directory
current_destination_directory:
    mov WORD PTR [rdi], 0x002e
open_destination_directory:
    mov eax, 257
    mov rdi, AT_FDCWD
    lea rsi, [rip + directory_path]
    # O_PATH | O_DIRECTORY | O_CLOEXEC; no read permission is needed.
    mov edx, 0x290000
    xor r10d, r10d
    syscall
    test rax, rax
    js output_error
    mov QWORD PTR [rip + directory_fd], rax
    call check_destination
    lea rdi, [rip + temporary_path]
    lea rsi, [rip + temporary_suffix]
    mov ecx, OFFSET FLAT:TEMPORARY_SUFFIX_SIZE
    rep movsb
    mov r12, rdi
    mov eax, 39
    syscall
    call decimal_string
    mov rdi, r12
    mov rcx, rdx
    rep movsb
    mov WORD PTR [rdi], 0x302d
    mov BYTE PTR [rdi + 2], 0
    inc rdi
    mov QWORD PTR [rip + temporary_digit], rdi
reserve_temporary_file:
    mov rdi, QWORD PTR [rip + destination_basename]
    lea rsi, [rip + temporary_path]
    call string_equal
    test eax, eax
    jz next_temporary_name
    mov eax, 257
    mov rdi, QWORD PTR [rip + directory_fd]
    lea rsi, [rip + temporary_path]
    mov edx, 0xa00c1
    mov r10d, 0x180
    syscall
    cmp rax, -17
    je next_temporary_name
    test rax, rax
    js output_error
    mov r12, rax
    mov BYTE PTR [rip + temporary_active], 1
    mov rdi, r12
    lea rsi, [rip + executable_buffer]
    mov rdx, QWORD PTR [rip + executable_length]
    call write_all
    test rax, rax
    js output_error
    mov eax, 91
    mov rdi, r12
    mov esi, 0x1ed
    syscall
    test rax, rax
    js output_error
    mov eax, 3
    mov rdi, r12
    syscall
    test rax, rax
    js output_error
    call check_destination
    mov eax, 316
    mov rdi, QWORD PTR [rip + directory_fd]
    lea rsi, [rip + temporary_path]
    mov rdx, rdi
    mov r10, QWORD PTR [rip + destination_basename]
    mov r8d, 1
    cmp BYTE PTR [rip + force_output], 0
    je publish_rename
    xor r8d, r8d
publish_rename:
    syscall
    cmp rax, -17
    je destination_exists_error
    test rax, rax
    js output_error
    mov BYTE PTR [rip + temporary_active], 0
    ret
next_temporary_name:
    mov rdi, QWORD PTR [rip + temporary_digit]
    cmp BYTE PTR [rdi], '9'
    jae output_error
    inc BYTE PTR [rdi]
    jmp reserve_temporary_file

.section .rodata
compiler_name: .asciz "ramos"
arg_build: .asciz "build"
arg_output: .asciz "-o"
arg_force: .asciz "--force"
arg_help: .asciz "--help"
arg_version: .asciz "--version"
colon: .asciz ":"
newline_text: .asciz "\n"
error_prefix: .asciz ": error: "
version_message: .asciz "Ramos 0.11.0 — native assembly bootstrap (0.7 grammar)\n"
help_message: .asciz "Usage: ramos build SOURCE.ramos -o EXECUTABLE [--force]\n       ramos --help | --version\nSupports main, strings, checked int64 arithmetic, let, var, bool, comparisons, if/else, while, break, continue, typed functions, return, and bounded byte buffers.\nTarget: x86-64 Linux. Existing output requires --force.\n"
usage_message: .asciz "usage: ramos build SOURCE.ramos -o EXECUTABLE [--force]"
input_message: .asciz "cannot read input (a readable regular file is required)"
output_message: .asciz "cannot write or publish output"
limit_message: .asciz "compiler limit exceeded (source, statements, variables, nesting, functions, parameters, IR, or output)"
syntax_message: .asciz "unexpected token in function, statement, or expression"
utf8_message: .asciz "source must be valid UTF-8 without NUL bytes"
string_message: .asciz "invalid string: check closing quote, escapes, and line breaks"
separator_message: .asciz "expected a newline or closing brace after statement"
number_message: .asciz "integer literal is outside the signed 64-bit range"
undefined_message: .asciz "variable is not declared before use"
duplicate_message: .asciz "variable is already declared in this scope"
immutable_message: .asciz "cannot assign to a let binding; use var for mutable variables"
type_message: .asciz "type mismatch: expected compatible int64, bool or bytes values"
function_message: .asciz "invalid or duplicate function; exactly one parameterless void main is required"
call_message: .asciz "invalid function call: check name, shadowing, argument count and types"
return_message: .asciz "invalid return or value function may reach its end without returning"
loop_message: .asciz "break and continue require an enclosing while loop"
alias_message: .asciz "output must not replace the source file or an alias of it"
exists_message: .asciz "output already exists; use --force to replace it"
temporary_suffix: .ascii ".ramos-tmp-"
.equ TEMPORARY_SUFFIX_SIZE, . - temporary_suffix

.include "bootstrap/src/runtime.inc"

.balign 8
elf_header:
    .byte 0x7f
    .ascii "ELF"
    .byte 2, 1, 1, 0
    .zero 8
    .short 2, 62
    .long 1
    .quad LOAD_BASE + CODE_OFFSET + RUNTIME_SIZE
    .quad 64
    .quad 0
    .long 0
    .short 64, 56, 3, 0, 0, 0
    # PT_LOAD: ELF headers and program instructions, read/execute.
    .long 1, 5
    .quad 0, LOAD_BASE, LOAD_BASE, 0, 0, 4096
    # PT_LOAD: immutable string bytes, read-only.
    .long 1, 4
    .quad 0, 0, 0, 0, 0, 4096
    # PT_GNU_STACK: read/write, explicitly not executable.
    .long 0x6474e551, 6
    .quad 0, 0, 0, 0, 0, 16
elf_header_end:
.equ ELF_HEADER_SIZE, elf_header_end - elf_header

.section .bss
.balign 16
source_name: .skip 8
destination_name: .skip 8
destination_basename: .skip 8
directory_fd: .skip 8
temporary_digit: .skip 8
source_length: .skip 8
cursor: .skip 8
line: .skip 8
column: .skip 8
error_line: .skip 8
error_column: .skip 8
token: .skip 8
number_value: .skip 8
identifier_offset: .skip 8
identifier_length: .skip 8
pending_name_offset: .skip 8
pending_name_length: .skip 8
pending_mutable: .skip 8
pending_slot: .skip 8
expression_depth: .skip 8
symbol_count: .skip 8
expression_type: .skip 8
scope_depth: .skip 8
loop_start: .skip 8
loop_end: .skip 8
label_count: .skip 8
branch_count: .skip 8
function_count: .skip 8
main_function: .skip 8
current_function: .skip 8
function_symbol_base: .skip 8
frame_local_count: .skip 8
current_return_type: .skip 8
block_returns: .skip 8
statement_returns: .skip 8
ir_count: .skip 8
fixup_count: .skip 8
code_cursor: .skip 8
string_offset: .skip 8
string_length: .skip 8
statement_count: .skip 8
data_length: .skip 8
rx_length: .skip 8
data_file_offset: .skip 8
executable_length: .skip 8
force_output: .skip 1
temporary_active: .skip 1
.balign 16
number_buffer: .skip 32
source_stat: .skip 144
destination_stat: .skip 144
temporary_path: .skip 4096
directory_path: .skip 4096
source_buffer: .skip SOURCE_LIMIT + 1
.balign 16
string_fixups: .skip STATEMENT_LIMIT * 16
ir_buffer: .skip IR_LIMIT * 24
symbols: .skip SYMBOL_LIMIT * 64
functions: .skip FUNCTION_LIMIT * 64
parameters: .skip FUNCTION_LIMIT * PARAMETER_LIMIT * 32
label_offsets: .skip (IR_LIMIT + 1) * 8
branch_fixups: .skip IR_LIMIT * 16
symbol_buckets: .skip SYMBOL_BUCKETS * 8
data_buffer: .skip DATA_LIMIT
.balign 4096
executable_buffer: .skip OUTPUT_LIMIT

.section .note.GNU-stack,"",@progbits
