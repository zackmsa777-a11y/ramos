# Copied contiguous, position-independent runtime. Every reference stays
# inside this region; no compiler address is embedded in generated output.
runtime_writer:
    mov edi, 1
runtime_write_fd:
    test rdx, rdx
    jz runtime_write_done
runtime_write_again:
    mov eax, 1
    syscall
    cmp rax, -4
    je runtime_write_again
    test rax, rax
    jle runtime_write_failed
    add rsi, rax
    sub rdx, rax
    jnz runtime_write_again
runtime_write_done:
    ret
runtime_write_failed:
    mov edi, 1
    mov eax, 60
    syscall
    ud2

# Format signed rax as decimal, including INT64_MIN, using a 32-byte buffer
# below the expression stack. Conversion divides the unsigned magnitude.
runtime_integer:
    sub rsp, 32
    lea rsi, [rsp + 32]
    mov r8, rsi
    dec rsi
    mov BYTE PTR [rsi], 10
    mov r10, rax
    test rax, rax
    jns runtime_integer_magnitude
    neg rax
runtime_integer_magnitude:
    mov r9d, 10
runtime_integer_digit:
    xor edx, edx
    div r9
    add dl, '0'
    dec rsi
    mov BYTE PTR [rsi], dl
    test rax, rax
    jnz runtime_integer_digit
    test r10, r10
    jns runtime_integer_write
    dec rsi
    mov BYTE PTR [rsi], '-'
runtime_integer_write:
    mov rdx, r8
    sub rdx, rsi
    call runtime_writer
    add rsp, 32
    ret
runtime_boolean:
    test rax, rax
    jz runtime_boolean_false
    lea rsi, [rip + runtime_true_text]
    mov edx, 5
    jmp runtime_writer
runtime_boolean_false:
    lea rsi, [rip + runtime_false_text]
    mov edx, 6
    jmp runtime_writer
runtime_true_text: .ascii "true\n"
runtime_false_text: .ascii "false\n"
runtime_arithmetic_error:
    lea rsi, [rip + runtime_math_message]
    mov edx, OFFSET FLAT:RUNTIME_MATH_MESSAGE_SIZE
    mov edi, 2
    call runtime_write_fd
    mov edi, 1
    mov eax, 60
    syscall
    ud2
runtime_math_message:
    .ascii "Ramos runtime error: arithmetic overflow or division by zero\n"
.equ RUNTIME_MATH_MESSAGE_SIZE, . - runtime_math_message
runtime_writer_end:
.equ RUNTIME_SIZE, runtime_writer_end - runtime_writer
.equ RUNTIME_INTEGER_FILE, CODE_OFFSET + runtime_integer - runtime_writer
.equ RUNTIME_BOOLEAN_FILE, CODE_OFFSET + runtime_boolean - runtime_writer
.equ RUNTIME_ERROR_FILE, CODE_OFFSET + runtime_arithmetic_error - runtime_writer
runtime_exit:
    mov eax, 60
    xor edi, edi
    syscall
runtime_exit_end:
.equ EXIT_SIZE, runtime_exit_end - runtime_exit

# Instruction templates are not part of the copied runtime. They are used
# by our emitter with explicit immediate and relative-address fields.
main_prologue: .byte 0x55, 0x48, 0x89, 0xe5, 0x48, 0x81, 0xec
.equ MAIN_PROLOGUE_SIZE, . - main_prologue
literal_prefix: .byte 0x48, 0xb8
load_prefix: .byte 0x48, 0x8b, 0x85
store_prefix: .byte 0x58, 0x48, 0x89, 0x85
string_lea_prefix: .byte 0x48, 0x8d, 0x35
negate_bytes: .byte 0x58, 0x48, 0xf7, 0xd8
add_bytes: .byte 0x59, 0x58, 0x48, 0x01, 0xc8
subtract_bytes: .byte 0x59, 0x58, 0x48, 0x29, 0xc8
multiply_bytes: .byte 0x59, 0x58, 0x48, 0x0f, 0xaf, 0xc1
divide_start: .byte 0x59, 0x58, 0x48, 0x85, 0xc9
division_minimum_prefix: .byte 0x48, 0xba
# JNE skips the four-byte compare and six-byte error branch that follows.
division_guard: .byte 0x48, 0x39, 0xd0, 0x75, 0x0a, 0x48, 0x83, 0xf9, 0xff
divide_bytes: .byte 0x48, 0x99, 0x48, 0xf7, 0xf9
remainder_bytes: .byte 0x48, 0x89, 0xd0

compare_bytes: .byte 0x59, 0x58, 0x48, 0x39, 0xc8, 0x0f
normalize_boolean: .byte 0xc0, 0x48, 0x0f, 0xb6, 0xc0
not_bytes: .byte 0x58, 0x48, 0x85, 0xc0, 0x0f, 0x94
conditional_jump_bytes: .byte 0x58, 0x48, 0x85, 0xc0, 0x0f, 0x84
comparison_opcodes: .byte 0x94, 0x95, 0x9c, 0x9e, 0x9f, 0x9d
