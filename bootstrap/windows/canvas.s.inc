# Owner-draw STATIC canvas. rax control record, r12 DRAWITEMSTRUCT, rbx GUI state.
# Borrow stock GDI objects and restore all DC state including clipping/color.
# No managed allocation, no application callback, no persistent GDI allocation.
runtime_gui_canvas_paint:
    push rbp
    push rsi
    push rdi
    push r12
    push r13
    push r14
    sub rsp, 48
    mov rbp, rsp
    mov [rbp], r12
    mov rcx, [r12 + 32]
    mov [rbp + 8], rcx
    mov rax, [rax + 16]
    xor r13d, r13d
    xor r14d, r14d
    test rax, rax
    jz runtime_gui_canvas_saved
    mov r14, [rax + 8]
    lea r13, [rax + 16]
runtime_gui_canvas_saved:
    GUI SaveDC
    test eax, eax
    jz runtime_gui_canvas_error_no_restore
    mov [rbp + 16], rax
    mov rax, [rbp]
    mov rcx, [rbp + 8]
    mov edx, [rax + 40]
    mov r8d, [rax + 44]
    mov r9d, [rax + 48]
    mov r10d, [rax + 52]
    GUI IntersectClipRect
    test eax, eax
    jz runtime_gui_canvas_error
    mov ecx, 19                    # DC_PEN, borrowed
    GUI GetStockObject
    test rax, rax
    jz runtime_gui_canvas_error
    mov rcx, [rbp + 8]
    mov rdx, rax
    GUI SelectObject
    test rax, rax
    jz runtime_gui_canvas_error
    mov ecx, 18                    # DC_BRUSH, borrowed
    GUI GetStockObject
    test rax, rax
    jz runtime_gui_canvas_error
    mov rsi, rax
    mov rcx, [rbp + 8]
    mov rdx, rsi
    GUI SelectObject
    test rax, rax
    jz runtime_gui_canvas_error
    mov ecx, 5                     # HOLLOW_BRUSH, borrowed
    GUI GetStockObject
    test rax, rax
    jz runtime_gui_canvas_error
    mov rdi, rax
    mov rcx, [rbp + 8]
    mov edx, 0xffffff
    GUI SetDCBrushColor
    cmp eax, -1
    je runtime_gui_canvas_error
    call runtime_gui_canvas_clear
    test eax, eax
    jz runtime_gui_canvas_error
runtime_gui_canvas_next:
    test r14, r14
    jz runtime_gui_canvas_restore
    mov rcx, [rbp + 8]
    mov edx, [r13 + 40]
    GUI SetDCPenColor
    cmp eax, -1
    je runtime_gui_canvas_error
    mov rcx, [rbp + 8]
    mov edx, [r13 + 40]
    GUI SetDCBrushColor
    cmp eax, -1
    je runtime_gui_canvas_error
    cmp QWORD PTR [r13], 1
    je runtime_gui_canvas_background
    cmp QWORD PTR [r13], 4
    je runtime_gui_canvas_line
    mov rcx, [rbp + 8]
    mov rdx, rsi
    cmp QWORD PTR [r13], 3
    je runtime_gui_canvas_hollow
    cmp QWORD PTR [r13], 5
    jne runtime_gui_canvas_select
runtime_gui_canvas_hollow:
    mov rdx, rdi
runtime_gui_canvas_select:
    GUI SelectObject
    test rax, rax
    jz runtime_gui_canvas_error
    mov rcx, [rbp + 8]
    mov edx, [r13 + 8]
    mov r8d, [r13 + 16]
    mov r9d, edx
    mov r10d, r8d
    add r9d, [r13 + 24]
    cmp QWORD PTR [r13], 5
    jae runtime_gui_canvas_ellipse
    add r10d, [r13 + 32]
    cmp QWORD PTR [r13], 2
    je runtime_gui_canvas_rectangle_fill
    GUI Rectangle
    jmp runtime_gui_canvas_check
runtime_gui_canvas_rectangle_fill:
    mov [rbp + 24], edx
    mov [rbp + 28], r8d
    mov [rbp + 32], r9d
    mov [rbp + 36], r10d
    lea rdx, [rbp + 24]
    mov r8, rsi
    GUI FillRect
    jmp runtime_gui_canvas_check
runtime_gui_canvas_ellipse:
    sub edx, [r13 + 24]
    sub r8d, [r13 + 24]
    add r10d, [r13 + 24]
    inc r9d
    inc r10d
    GUI Ellipse
    jmp runtime_gui_canvas_check
runtime_gui_canvas_line:
    mov rcx, [rbp + 8]
    mov edx, [r13 + 8]
    mov r8d, [r13 + 16]
    xor r9d, r9d
    GUI MoveToEx
    test eax, eax
    jz runtime_gui_canvas_error
    mov rcx, [rbp + 8]
    mov edx, [r13 + 24]
    mov r8d, [r13 + 32]
    GUI LineTo
    jmp runtime_gui_canvas_check
runtime_gui_canvas_background:
    call runtime_gui_canvas_clear
runtime_gui_canvas_check:
    test eax, eax
    jz runtime_gui_canvas_error
    add r13, 48
    dec r14
    jmp runtime_gui_canvas_next
runtime_gui_canvas_error:
    mov QWORD PTR [rbx + 40], -5
runtime_gui_canvas_restore:
    mov rcx, [rbp + 8]
    mov edx, [rbp + 16]
    GUI RestoreDC
    test eax, eax
    jnz runtime_gui_canvas_done
runtime_gui_canvas_error_no_restore:
    mov QWORD PTR [rbx + 40], -5
runtime_gui_canvas_done:
    add rsp, 48
    pop r14
    pop r13
    pop r12
    pop rdi
    pop rsi
    pop rbp
    ret
runtime_gui_canvas_clear:
    mov rcx, [rbp + 8]
    mov rdx, [rbp]
    add rdx, 40
    mov r8, rsi
    GUI FillRect
    ret
