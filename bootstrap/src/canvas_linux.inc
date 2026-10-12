# GTK draw callback. rdi widget, rsi borrowed Cairo context, rdx control record.
# No managed allocation or Ramos callbacks during painting.
runtime_lg_canvas_cb:
    push rbp
    push rbx
    push r12
    push r13
    push r14
    sub rsp, 32
    mov rbp, rsp
    mov [rbp], rdi
    mov [rbp + 8], rsi
    mov [rbp + 16], rdx
    mov rbx, rsi
    LG gtk_widget_get_allocated_width
    mov [rbp + 24], rax
    mov rdi, [rbp]
    LG gtk_widget_get_allocated_height
    cvtsi2sd xmm3, eax
    cvtsi2sd xmm2, QWORD PTR [rbp + 24]
    xorps xmm0, xmm0
    xorps xmm1, xmm1
    mov rdi, rbx
    LG cairo_rectangle
    mov rdi, rbx
    LG cairo_clip
    mov rdi, rbx
    mov eax, 1
    cvtsi2sd xmm0, eax
    LG cairo_set_line_width
    mov eax, 0xffffff
    call runtime_lg_canvas_color
    mov rdi, rbx
    LG cairo_paint
    mov rax, [rbp + 16]
    mov rax, [rax + 40]
    test rax, rax
    jz runtime_lg_canvas_done
    mov r13, [rax + 8]
    lea r12, [rax + 16]
runtime_lg_canvas_next:
    test r13, r13
    jz runtime_lg_canvas_done
    mov eax, [r12 + 40]
    call runtime_lg_canvas_color
    mov r14, [r12]
    cmp r14, 1
    je runtime_lg_canvas_clear
    mov rdi, rbx
    cvtsi2sd xmm0, QWORD PTR [r12 + 8]
    cvtsi2sd xmm1, QWORD PTR [r12 + 16]
    cmp r14, 4
    je runtime_lg_canvas_line
    cvtsi2sd xmm2, QWORD PTR [r12 + 24]
    cmp r14, 5
    jae runtime_lg_canvas_arc
    cvtsi2sd xmm3, QWORD PTR [r12 + 32]
    LG cairo_rectangle
    cmp r14, 2
    je runtime_lg_canvas_fill
    jmp runtime_lg_canvas_stroke
runtime_lg_canvas_arc:
    xorps xmm3, xmm3
    movsd xmm4, [rip + runtime_canvas_tau]
    LG cairo_arc
    cmp r14, 6
    je runtime_lg_canvas_fill
    jmp runtime_lg_canvas_stroke
runtime_lg_canvas_line:
    LG cairo_move_to
    mov rdi, rbx
    cvtsi2sd xmm0, QWORD PTR [r12 + 24]
    cvtsi2sd xmm1, QWORD PTR [r12 + 32]
    LG cairo_line_to
runtime_lg_canvas_stroke:
    mov rdi, rbx
    LG cairo_stroke
    jmp runtime_lg_canvas_advance
runtime_lg_canvas_fill:
    mov rdi, rbx
    LG cairo_fill
    jmp runtime_lg_canvas_advance
runtime_lg_canvas_clear:
    mov rdi, rbx
    LG cairo_paint
runtime_lg_canvas_advance:
    add r12, 48
    dec r13
    jmp runtime_lg_canvas_next
runtime_lg_canvas_done:
    mov rdi, rbx
    LG cairo_status
    test eax, eax
    jz runtime_lg_canvas_return
    mov rax, [rbp + 16]
    mov rax, [rax + 32]
    mov QWORD PTR [rax + 32], -5
runtime_lg_canvas_return:
    xor eax, eax
    add rsp, 32
    pop r14
    pop r13
    pop r12
    pop rbx
    pop rbp
    ret
# COLORREF in eax, borrowed context in rbx. Only caller-saved registers clobbered.
runtime_lg_canvas_color:
    mov ecx, eax
    and ecx, 255
    cvtsi2sd xmm0, ecx
    shr eax, 8
    mov ecx, eax
    and ecx, 255
    cvtsi2sd xmm1, ecx
    shr eax, 8
    cvtsi2sd xmm2, eax
    mov eax, 255
    cvtsi2sd xmm3, eax
    divsd xmm0, xmm3
    divsd xmm1, xmm3
    divsd xmm2, xmm3
    mov rdi, rbx
    LG cairo_set_source_rgb
    ret
runtime_canvas_tau: .double 6.283185307179586
