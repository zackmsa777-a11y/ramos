# Opt-in DPI state lives after the event ring, inside the rooted GUI buffer.
.equ GUI_SCALED, 4608
.equ GUI_PREVIOUS_DPI_CONTEXT, 4616
.equ GUI_DPI, 4624
.equ GUI_OWNED_FONT, 4632
.equ GUI_GetDpiForWindow, 416
.equ GUI_SetThreadDpiAwarenessContext, 424
.equ GUI_GetDpiForSystem, 432
.equ GUI_AdjustWindowRectExForDpi, 440
.equ GUI_SetWindowPos, 448
.equ GUI_CreateFontIndirectW, 456
.equ GUI_SetMapMode, 464
.equ GUI_SetWindowExtEx, 472
.equ GUI_SetViewportExtEx, 480

# Helpers preserve coordinate argument registers. Native scales are bounded.
runtime_gui_to_pixels:
    cmp QWORD PTR [rbx + GUI_SCALED], 0
    je runtime_gui_coordinate_done
    push rcx
    push rdx
    imul rax, [rbx + GUI_DPI]
    add rax, 48
    xor edx, edx
    mov ecx, 96
    div rcx
    pop rdx
    pop rcx
runtime_gui_coordinate_done:
    ret
runtime_gui_from_pixels:
    cmp QWORD PTR [rbx + GUI_SCALED], 0
    je runtime_gui_coordinate_done
    push rcx
    push rdx
    imul rax, rax, 96
    mov rcx, [rbx + GUI_DPI]
    mov rdx, rcx
    shr rdx, 1
    add rax, rdx
    xor edx, edx
    div rcx
    pop rdx
    pop rcx
    ret

# Optional APIs are resolved only for the opt-in path. Legacy GUI still works
# on systems without per-monitor-v2 APIs. DLLs are already System32-owned.
runtime_gui_scaled_begin:
    push rbp
    push rsi
    push rdi
    sub rsp, 16
    mov rbp, rsp
    lea rdi, [rip + runtime_gui_dpi_names]
    lea rsi, [rbx + 416]
    mov QWORD PTR [rbp], 0
runtime_gui_scaled_resolve:
    mov rcx, [rbx + 56]
    cmp QWORD PTR [rbp], 5
    jb runtime_gui_scaled_resolve_api
    mov rcx, [rbx + 64]
runtime_gui_scaled_resolve_api:
    mov rdx, rdi
    API GetProcAddress
    test rax, rax
    jz runtime_gui_scaled_unsupported
    mov [rsi], rax
    add rsi, 8
runtime_gui_scaled_next_name:
    cmp BYTE PTR [rdi], 0
    lea rdi, [rdi + 1]
    jne runtime_gui_scaled_next_name
    inc QWORD PTR [rbp]
    cmp QWORD PTR [rbp], 9
    jb runtime_gui_scaled_resolve
    mov rcx, -4                         # DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2
    GUI SetThreadDpiAwarenessContext
    test rax, rax
    jz runtime_gui_scaled_unsupported
    mov [rbx + GUI_PREVIOUS_DPI_CONTEXT], rax
    mov QWORD PTR [rbx + GUI_SCALED], 1
    GUI GetDpiForSystem
    cmp eax, 96
    jb runtime_gui_scaled_range
    cmp eax, 768
    ja runtime_gui_scaled_range
    mov [rbx + GUI_DPI], rax
    call runtime_gui_scaled_font
    test rax, rax
    jnz runtime_gui_scaled_begin_cleanup
    jmp runtime_gui_scaled_begin_done
runtime_gui_scaled_range:
    mov rax, -27
runtime_gui_scaled_begin_cleanup:
    mov [rbp + 8], rax
    call runtime_gui_scaled_end
    test rax, rax
    jnz runtime_gui_scaled_begin_done
    mov rax, [rbp + 8]
    jmp runtime_gui_scaled_begin_done
runtime_gui_scaled_unsupported:
    mov rax, -38
runtime_gui_scaled_begin_done:
    add rsp, 16
    pop rdi
    pop rsi
    pop rbp
    ret

# LOGFONTW (92 bytes) with a 12-logical-unit Segoe UI font. Create first, then
# replace control references and delete the previous font. No Ramos allocation.
runtime_gui_scaled_font:
    push rbp
    push rsi
    push rdi
    sub rsp, 112
    mov rbp, rsp
    mov rdi, rbp
    xor eax, eax
    mov ecx, 14
    rep stosq
    mov eax, 12
    call runtime_gui_to_pixels
    neg eax
    mov [rbp], eax
    mov DWORD PTR [rbp + 16], 400
    mov BYTE PTR [rbp + 23], 1
    mov BYTE PTR [rbp + 26], 5
    lea rsi, [rip + runtime_gui_dpi_font]
    lea rdi, [rbp + 28]
    mov ecx, 9
    rep movsw
    mov rcx, rbp
    GUI CreateFontIndirectW
    test rax, rax
    jz runtime_gui_scaled_font_error
    mov rdi, rax
    mov rax, [rbx + GUI_OWNED_FONT]
    mov [rbp + 96], rax
    mov [rbx + GUI_OWNED_FONT], rdi
    lea rsi, [rbx + 512]
runtime_gui_scaled_font_each:
    mov rcx, [rsi]
    test rcx, rcx
    jz runtime_gui_scaled_font_next
    cmp QWORD PTR [rsi + 8], 5
    jae runtime_gui_scaled_font_next
    mov edx, 0x30
    mov r8, rdi
    mov r9d, 1
    GUI SendMessageW
runtime_gui_scaled_font_next:
    add rsi, 32
    lea rax, [rbx + 2560]
    cmp rsi, rax
    jb runtime_gui_scaled_font_each
    mov rcx, [rbp + 96]
    test rcx, rcx
    jz runtime_gui_scaled_font_success
    GUI DeleteObject
    test eax, eax
    jz runtime_gui_scaled_font_error
runtime_gui_scaled_font_success:
    xor eax, eax
    jmp runtime_gui_scaled_font_done
runtime_gui_scaled_font_error:
    mov rax, -5
runtime_gui_scaled_font_done:
    add rsp, 112
    pop rdi
    pop rsi
    pop rbp
    ret

# Called only after controls are destroyed, or before opening any controls.
# Retry restoration on a later close if a native operation failed.
runtime_gui_scaled_end:
    push rbp
    sub rsp, 8
    mov rbp, rsp
    mov QWORD PTR [rbp], 0
    mov rcx, [rbx + GUI_OWNED_FONT]
    test rcx, rcx
    jz runtime_gui_scaled_restore
    GUI DeleteObject
    test eax, eax
    jz runtime_gui_scaled_end_font_error
    mov QWORD PTR [rbx + GUI_OWNED_FONT], 0
    jmp runtime_gui_scaled_restore
runtime_gui_scaled_end_font_error:
    mov QWORD PTR [rbp], -5
runtime_gui_scaled_restore:
    mov rcx, [rbx + GUI_PREVIOUS_DPI_CONTEXT]
    test rcx, rcx
    jz runtime_gui_scaled_end_done
    GUI SetThreadDpiAwarenessContext
    test rax, rax
    jz runtime_gui_scaled_end_context_error
    mov QWORD PTR [rbx + GUI_PREVIOUS_DPI_CONTEXT], 0
    mov QWORD PTR [rbx + GUI_SCALED], 0
    mov QWORD PTR [rbx + GUI_DPI], 0
    jmp runtime_gui_scaled_end_done
runtime_gui_scaled_end_context_error:
    mov QWORD PTR [rbp], -5
runtime_gui_scaled_end_done:
    mov rax, [rbp]
    add rsp, 8
    pop rbp
    ret

runtime_gui_dpi:
    push rbx
    mov rbx, [r15 + 128]
    test rbx, rbx
    jz runtime_gui_dpi_bad
    add rbx, 8
    cmp QWORD PTR [rbx], 0
    je runtime_gui_dpi_bad
    mov eax, 96
    cmp QWORD PTR [rbx + GUI_SCALED], 0
    je runtime_gui_dpi_success
    mov rcx, [rbx]
    GUI GetDpiForWindow
    test eax, eax
    jz runtime_gui_dpi_error
runtime_gui_dpi_success:
    mov QWORD PTR [r15 + 8], 0
    pop rbx
    ret
runtime_gui_dpi_bad:
    mov rax, -9
    jmp runtime_gui_dpi_done
runtime_gui_dpi_error:
    mov rax, -5
runtime_gui_dpi_done:
    mov [r15 + 8], rax
    pop rbx
    ret

# Actual OS DPI change. Reject mismatched/unchanged messages before accessing
# their rectangle, so synthetic notifications cannot change cached scale.
runtime_gui_callback_dpi:
    cmp QWORD PTR [rbx + GUI_SCALED], 0
    je runtime_gui_callback_default
    mov rcx, [rbp]
    GUI GetDpiForWindow
    mov edx, DWORD PTR [rbp + 16]
    movzx ecx, dx
    shr edx, 16
    cmp eax, ecx
    jne runtime_gui_callback_default
    cmp eax, edx
    jne runtime_gui_callback_default
    cmp rax, [rbx + GUI_DPI]
    je runtime_gui_callback_default
    cmp eax, 96
    jb runtime_gui_callback_dpi_range
    cmp eax, 768
    ja runtime_gui_callback_dpi_range
    mov [rbx + GUI_DPI], rax
    call runtime_gui_scaled_font
    test rax, rax
    jnz runtime_gui_callback_dpi_error
    mov r12, [rbp + 24]
    test r12, r12
    jz runtime_gui_callback_dpi_native_error
    movsxd r9, DWORD PTR [r12 + 8]
    movsxd rdx, DWORD PTR [r12]
    sub r9, rdx
    movsxd r10, DWORD PTR [r12 + 12]
    movsxd r8, DWORD PTR [r12 + 4]
    sub r10, r8
    test r9, r9
    jle runtime_gui_callback_dpi_native_error
    test r10, r10
    jle runtime_gui_callback_dpi_native_error
    cmp r9, 65535
    ja runtime_gui_callback_dpi_native_error
    cmp r10, 65535
    ja runtime_gui_callback_dpi_native_error
    mov rcx, [rbp]
    xor edx, edx
    movsxd r8, DWORD PTR [r12]
    movsxd r9, DWORD PTR [r12 + 4]
    movsxd r10, DWORD PTR [r12 + 8]
    sub r10, r8
    movsxd r11, DWORD PTR [r12 + 12]
    sub r11, r9
    mov esi, 0x14                     # SWP_NOZORDER | SWP_NOACTIVATE
    GUI SetWindowPos
    test eax, eax
    jz runtime_gui_callback_dpi_native_error
    lea r12, [rbx + 512]
runtime_gui_callback_dpi_each:
    mov rcx, [r12]
    test rcx, rcx
    jz runtime_gui_callback_dpi_next
    mov r13, [r12 + 24]
    test r13, r13
    jz runtime_gui_callback_dpi_native_error
    mov rax, [r13 + 8]
    call runtime_gui_to_pixels
    mov rdx, rax
    mov rax, [r13 + 16]
    call runtime_gui_to_pixels
    mov r8, rax
    mov rax, [r13 + 24]
    add rax, [r13 + 8]
    call runtime_gui_to_pixels
    sub rax, rdx
    mov r9, rax
    mov rax, [r13 + 32]
    add rax, [r13 + 16]
    call runtime_gui_to_pixels
    sub rax, r8
    mov r10, rax
    # Finish the complete layout before repainting. MoveWindow can preserve
    # client pixels from the old scale; painting each child during the loop
    # can also clip against siblings that have not yet moved.
    xor r11d, r11d                   # bRepaint = FALSE
    GUI MoveWindow
    test eax, eax
    jz runtime_gui_callback_dpi_native_error
runtime_gui_callback_dpi_next:
    add r12, 32
    lea rax, [rbx + 2560]
    cmp r12, rax
    jb runtime_gui_callback_dpi_each
    # All geometry now uses the new DPI. Repaint the entire parent and every
    # child, including unchanged areas that otherwise retain old-scale pixels.
    # NULL rectangles invalidate full client areas. Paints run after this OS
    # callback returns; no managed allocation or Ramos callback is required.
    mov rcx, [rbp]
    xor edx, edx
    mov r8d, 1
    GUI InvalidateRect
    test eax, eax
    jz runtime_gui_callback_dpi_native_error
    lea r12, [rbx + 512]
runtime_gui_callback_dpi_invalidate_each:
    mov rcx, [r12]
    test rcx, rcx
    jz runtime_gui_callback_dpi_invalidate_next
    xor edx, edx
    mov r8d, 1
    GUI InvalidateRect
    test eax, eax
    jz runtime_gui_callback_dpi_native_error
runtime_gui_callback_dpi_invalidate_next:
    add r12, 32
    lea rax, [rbx + 2560]
    cmp r12, rax
    jb runtime_gui_callback_dpi_invalidate_each
    mov rcx, [rbp]
    lea rdx, [rbp + 32]               # Private callback stack RECT.
    GUI GetClientRect
    test eax, eax
    jz runtime_gui_callback_dpi_native_error
    lea rcx, [rbp + 32]
    mov eax, [rcx + 8]
    call runtime_gui_from_pixels
    mov rdx, rax
    mov eax, [rcx + 12]
    call runtime_gui_from_pixels
    mov r8, rax
    mov rcx, [rbx + GUI_DPI]
    mov eax, 6
    call runtime_gui_enqueue
    xor eax, eax
    jmp runtime_gui_callback_done
runtime_gui_callback_dpi_range:
    mov rax, -27
    jmp runtime_gui_callback_dpi_error
runtime_gui_callback_dpi_native_error:
    mov rax, -5
runtime_gui_callback_dpi_error:
    mov [rbx + 40], rax
    xor eax, eax
    jmp runtime_gui_callback_done
runtime_gui_dpi_names:
    .asciz "GetDpiForWindow"
    .asciz "SetThreadDpiAwarenessContext"
    .asciz "GetDpiForSystem"
    .asciz "AdjustWindowRectExForDpi"
    .asciz "SetWindowPos"
    .asciz "CreateFontIndirectW"
    .asciz "SetMapMode"
    .asciz "SetWindowExtEx"
    .asciz "SetViewportExtEx"
.balign 2
runtime_gui_dpi_font: .short 'S','e','g','o','e',' ','U','I',0

# Creation can select a monitor with a different DPI from the primary display.
# Correct the initially requested logical client size before showing the window.
# RAX=requested logical width, RCX=requested logical height.
runtime_gui_scaled_initial:
    push rbp
    sub rsp, 48
    mov rbp, rsp
    mov [rbp + 16], rax
    mov [rbp + 24], rcx
    mov rcx, [rbx]
    GUI GetDpiForWindow
    cmp eax, 96
    jb runtime_gui_scaled_initial_range
    cmp eax, 768
    ja runtime_gui_scaled_initial_range
    cmp rax, [rbx + GUI_DPI]
    je runtime_gui_scaled_initial_ok
    mov [rbx + GUI_DPI], rax
    call runtime_gui_scaled_font
    test rax, rax
    jnz runtime_gui_scaled_initial_done
    mov QWORD PTR [rbp], 0
    mov rax, [rbp + 16]
    call runtime_gui_to_pixels
    mov [rbp + 8], eax
    mov rax, [rbp + 24]
    call runtime_gui_to_pixels
    mov [rbp + 12], eax
    mov rcx, rbp
    mov edx, 0xcf0000
    xor r8d, r8d
    xor r9d, r9d
    mov r10, [rbx + GUI_DPI]
    GUI AdjustWindowRectExForDpi
    test eax, eax
    jz runtime_gui_scaled_initial_error
    movsxd r10, DWORD PTR [rbp + 8]
    movsxd rax, DWORD PTR [rbp]
    sub r10, rax
    movsxd r11, DWORD PTR [rbp + 12]
    movsxd rax, DWORD PTR [rbp + 4]
    sub r11, rax
    mov rcx, [rbx]
    xor edx, edx
    xor r8d, r8d
    xor r9d, r9d
    push rsi
    mov esi, 0x16                   # Preserve initial position/z-order/focus.
    GUI SetWindowPos
    pop rsi
    test eax, eax
    jz runtime_gui_scaled_initial_error
runtime_gui_scaled_initial_ok:
    xor eax, eax
    jmp runtime_gui_scaled_initial_done
runtime_gui_scaled_initial_error:
    mov rax, -5
    jmp runtime_gui_scaled_initial_done
runtime_gui_scaled_initial_range:
    mov rax, -27
runtime_gui_scaled_initial_done:
    add rsp, 48
    pop rbp
    ret
