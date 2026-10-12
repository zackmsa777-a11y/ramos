# Shared GUI command validation: bytes handle in rax, active payload size or -22.
# Revalidate every field before allocation/publication. No native pointers in packet.
runtime_canvas_validate:
    cmp QWORD PTR [rax], 8
    jb runtime_canvas_invalid
    mov r8, [rax + 8]
    cmp r8, 1024
    ja runtime_canvas_invalid
    imul r9, r8, 48
    add r9, 8
    cmp r9, [rax]
    ja runtime_canvas_invalid
    lea rsi, [rax + 16]
runtime_canvas_validate_next:
    test r8, r8
    jz runtime_canvas_valid
    mov r10, [rsi]
    cmp r10, 1
    jb runtime_canvas_invalid
    cmp r10, 6
    ja runtime_canvas_invalid
    cmp QWORD PTR [rsi + 40], 0xffffff
    ja runtime_canvas_invalid
    mov ecx, 8
runtime_canvas_coordinates:
    mov rdx, [rsi + rcx]
    cmp rdx, -8192
    jl runtime_canvas_invalid
    cmp rdx, 8192
    jg runtime_canvas_invalid
    add ecx, 8
    cmp ecx, 40
    jb runtime_canvas_coordinates
    cmp r10, 1
    je runtime_canvas_clear
    cmp r10, 4
    je runtime_canvas_advance
    cmp QWORD PTR [rsi + 24], 1
    jl runtime_canvas_invalid
    cmp r10, 5
    jae runtime_canvas_circle
    cmp QWORD PTR [rsi + 32], 1
    jl runtime_canvas_invalid
    jmp runtime_canvas_advance
runtime_canvas_circle:
    cmp QWORD PTR [rsi + 32], 0
    jne runtime_canvas_invalid
    jmp runtime_canvas_advance
runtime_canvas_clear:
    mov rdx, [rsi + 8]
    or rdx, [rsi + 16]
    or rdx, [rsi + 24]
    or rdx, [rsi + 32]
    jnz runtime_canvas_invalid
runtime_canvas_advance:
    add rsi, 48
    dec r8
    jmp runtime_canvas_validate_next
runtime_canvas_valid:
    mov rax, r9
    ret
runtime_canvas_invalid:
    mov rax, -22
    ret
runtime_canvas_copy:
    push rax                         # root input handle across managed allocation
    call runtime_canvas_validate
    test rax, rax
    js runtime_canvas_copy_done
    mov rdx, rax
    mov rsi, [rsp]
    add rsi, 8
    call runtime_buffer_literal
runtime_canvas_copy_done:
    add rsp, 8
    ret
