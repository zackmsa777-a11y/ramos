# Native Windows GUI boundary. One parent window, 64 child controls, and a
# 64-event checked ring. Public code gets IDs, never HWNDs or addresses.
# The heap root at process+128 owns state; callbacks never allocate Ramos data.
# USER32/GDI32 load from System32 only, on the first GUI operation.
.equ GUI_RegisterClassExW, 128
.equ GUI_CreateWindowExW, 136
.equ GUI_DefWindowProcW, 144
.equ GUI_DestroyWindow, 152
.equ GUI_ShowWindow, 160
.equ GUI_AdjustWindowRectEx, 168
.equ GUI_GetClientRect, 176
.equ GUI_PeekMessageW, 184
.equ GUI_TranslateMessage, 192
.equ GUI_DispatchMessageW, 200
.equ GUI_MsgWaitForMultipleObjectsEx, 208
.equ GUI_IsDialogMessageW, 216
.equ GUI_SendMessageW, 224
.equ GUI_SetWindowTextW, 232
.equ GUI_GetWindowTextLengthW, 240
.equ GUI_GetWindowTextW, 248
.equ GUI_MoveWindow, 256
.equ GUI_LoadCursorW, 264
.equ GUI_FillRect, 272
.equ GUI_GetStockObject, 280
.equ GUI_CreateSolidBrush, 288
.equ GUI_DeleteObject, 296
.equ GUI_SelectObject, 304
.equ GUI_SetDCPenColor, 312
.equ GUI_SetDCBrushColor, 320
.equ GUI_Rectangle, 328
.equ GUI_MoveToEx, 336
.equ GUI_LineTo, 344
.equ GUI_Ellipse, 352
.equ GUI_SaveDC, 360
.equ GUI_IntersectClipRect, 368
.equ GUI_RestoreDC, 376
.equ GUI_InvalidateRect, 384
.macro GUI name
    mov rax, [rbx + GUI_\name]
    call runtime_api
.endm
runtime_gui_table:
    mov rax, [r15 + 128]
    test rax, rax
    jnz runtime_gui_table_ready
    mov eax, 5120
    call runtime_buffer_new
    mov [r15 + 128], rax
runtime_gui_table_ready:
    lea rbx, [rax + 8]
    mov [rip + gui_process_state], r15
    ret
# UTF-8 buffer -> independently allocated terminated UTF-16 buffer. Empty text
# is valid. NUL, malformed UTF-8 and >32767 bytes return EINVAL, no trap.
runtime_gui_utf16:
    push rbp
    sub rsp, 32
    mov rbp, rsp
    mov [rbp], rax
    mov r9, [rax]
    cmp r9, 32767
    ja runtime_gui_utf16_invalid
    xor ecx, ecx
runtime_gui_utf16_scan:
    cmp rcx, r9
    jae runtime_gui_utf16_convert
    cmp BYTE PTR [rax + rcx + 8], 0
    je runtime_gui_utf16_invalid
    inc rcx
    jmp runtime_gui_utf16_scan
runtime_gui_utf16_convert:
    test r9, r9
    jz runtime_gui_utf16_empty
    lea r8, [rax + 8]
    mov ecx, 65001
    mov edx, 8
    xor r10d, r10d
    xor r11d, r11d
    API MultiByteToWideChar
    test eax, eax
    jz runtime_gui_utf16_invalid
    mov [rbp + 8], rax
    lea rax, [rax*2 + 2]
    call runtime_buffer_new
    mov [rbp + 16], rax
    lea r10, [rax + 8]
    mov r11, [rbp + 8]
    mov r8, [rbp]
    mov r9, [r8]
    add r8, 8
    mov ecx, 65001
    mov edx, 8
    API MultiByteToWideChar
    test eax, eax
    jz runtime_gui_utf16_invalid
    mov rax, [rbp + 16]
    jmp runtime_gui_utf16_done
runtime_gui_utf16_empty:
    mov eax, 2
    call runtime_buffer_new
    jmp runtime_gui_utf16_done
runtime_gui_utf16_invalid:
    mov rax, -22
runtime_gui_utf16_done:
    add rsp, 32
    pop rbp
    ret
# CreateWindowExW has twelve arguments. RAX points at twelve qwords; this
# private adapter preserves Win64 alignment/shadow space and all stack args.
runtime_gui_create:
    push rbp
    mov rbp, rsp
    and rsp, -16
    sub rsp, 96
    mov rcx, [rax]
    mov rdx, [rax + 8]
    mov r8, [rax + 16]
    mov r9, [rax + 24]
    mov r10d, 32
runtime_gui_create_stack:
    mov r11, [rax + r10]
    mov [rsp + r10], r11
    add r10, 8
    cmp r10, 96
    jb runtime_gui_create_stack
    call QWORD PTR [rbx + GUI_CreateWindowExW]
    mov rsp, rbp
    pop rbp
    ret
runtime_gui_open:
    push rbp
    push rbx
    sub rsp, 240
    mov rbp, rsp
    mov [rbp], rax
    mov [rbp + 8], rcx
    mov [rbp + 16], rdx
    cmp rcx, 160
    jl runtime_gui_open_invalid
    cmp rcx, 4096
    jg runtime_gui_open_invalid
    cmp rdx, 80
    jl runtime_gui_open_invalid
    cmp rdx, 4096
    jg runtime_gui_open_invalid
    cmp QWORD PTR [rax], 4095
    ja runtime_gui_open_invalid
    call runtime_gui_utf16
    test rax, rax
    js runtime_gui_open_done
    mov [rbp + 24], rax
    call runtime_gui_table
    cmp QWORD PTR [rbx], 0
    jne runtime_gui_open_busy
    cmp QWORD PTR [rbx + 56], 0
    jne runtime_gui_open_loaded
    lea rcx, [rip + runtime_gui_user_dll]
    xor edx, edx
    mov r8d, 0x800                       # LOAD_LIBRARY_SEARCH_SYSTEM32
    API LoadLibraryExW
    test rax, rax
    jz runtime_gui_open_os_error
    mov [rbx + 56], rax
    lea rcx, [rip + runtime_gui_gdi_dll]
    xor edx, edx
    mov r8d, 0x800
    API LoadLibraryExW
    test rax, rax
    jz runtime_gui_open_load_failed
    mov [rbx + 64], rax
    lea rdi, [rip + runtime_gui_names]
    lea rsi, [rbx + 128]
    mov QWORD PTR [rbp + 32], 0
runtime_gui_open_resolve:
    mov rcx, [rbx + 56]
    cmp QWORD PTR [rbp + 32], 32
    je runtime_gui_open_resolve_user
    cmp QWORD PTR [rbp + 32], 19
    jb runtime_gui_open_resolve_user
    mov rcx, [rbx + 64]
runtime_gui_open_resolve_user:
    mov rdx, rdi
    API GetProcAddress
    test rax, rax
    jz runtime_gui_open_load_failed
    mov [rsi], rax
    add rsi, 8
runtime_gui_open_next_name:
    cmp BYTE PTR [rdi], 0
    lea rdi, [rdi + 1]
    jne runtime_gui_open_next_name
    inc QWORD PTR [rbp + 32]
    cmp QWORD PTR [rbp + 32], 33
    jb runtime_gui_open_resolve
runtime_gui_open_loaded:
    cmp QWORD PTR [rbx + 8], 0
    jne runtime_gui_open_registered
    xor ecx, ecx
    API GetModuleHandleW
    mov [rbx + 16], rax
    mov rdi, rbp
    add rdi, 48
    xor eax, eax
    mov ecx, 10
    rep stosq
    mov DWORD PTR [rbp + 48], 80
    lea rax, [rip + runtime_gui_callback]
    mov [rbp + 56], rax
    mov rax, [rbx + 16]
    mov [rbp + 72], rax
    xor ecx, ecx
    mov edx, 32512                       # IDC_ARROW
    GUI LoadCursorW
    mov [rbp + 88], rax
    mov QWORD PTR [rbp + 96], 16         # COLOR_BTNFACE + 1
    lea rax, [rip + runtime_gui_class]
    mov [rbp + 112], rax
    lea rcx, [rbp + 48]
    GUI RegisterClassExW
    test eax, eax
    jz runtime_gui_open_os_error
    mov [rbx + 8], rax
    mov ecx, 17                         # DEFAULT_GUI_FONT (borrowed stock object)
    GUI GetStockObject
    mov [rbx + 72], rax
runtime_gui_open_registered:
    mov QWORD PTR [rbx + 24], 0
    mov QWORD PTR [rbx + 32], 0
    mov QWORD PTR [rbx + 40], 0
    mov QWORD PTR [rbx + 48], 0
    mov QWORD PTR [rbp + 48], 0
    mov eax, [rbp + 8]
    mov [rbp + 56], eax
    mov eax, [rbp + 16]
    mov [rbp + 60], eax
    lea rcx, [rbp + 48]
    mov edx, 0xcf0000                   # WS_OVERLAPPEDWINDOW
    xor r8d, r8d
    xor r9d, r9d
    GUI AdjustWindowRectEx
    test eax, eax
    jz runtime_gui_open_os_error
    movsxd rax, DWORD PTR [rbp + 56]
    movsxd rcx, DWORD PTR [rbp + 48]
    sub rax, rcx
    mov [rbp + 96], rax
    movsxd rax, DWORD PTR [rbp + 60]
    movsxd rcx, DWORD PTR [rbp + 52]
    sub rax, rcx
    mov [rbp + 104], rax
    mov QWORD PTR [rbp + 48], 0
    lea rax, [rip + runtime_gui_class]
    mov [rbp + 56], rax
    mov rax, [rbp + 24]
    add rax, 8
    mov [rbp + 64], rax
    mov QWORD PTR [rbp + 72], 0xcf0000
    mov QWORD PTR [rbp + 80], -2147483648 # CW_USEDEFAULT
    mov QWORD PTR [rbp + 88], -2147483648
    mov QWORD PTR [rbp + 112], 0
    mov QWORD PTR [rbp + 120], 0
    mov rax, [rbx + 16]
    mov [rbp + 128], rax
    mov QWORD PTR [rbp + 136], 0
    lea rax, [rbp + 48]
    call runtime_gui_create
    test rax, rax
    jz runtime_gui_open_os_error
    mov [rbx], rax
    mov rcx, rax
    mov edx, 5
    GUI ShowWindow
    xor eax, eax
    jmp runtime_gui_open_done
runtime_gui_open_busy:
    mov rax, -16
    jmp runtime_gui_open_done
runtime_gui_open_invalid:
    mov rax, -22
    jmp runtime_gui_open_done
runtime_gui_open_load_failed:
    # Keep process-owned DLL references, but require a full resolve on retry.
    mov QWORD PTR [rbx + 56], 0
runtime_gui_open_os_error:
    call runtime_errno
    test rax, rax
    js runtime_gui_open_done
    mov rax, -5
runtime_gui_open_done:
    mov [r15 + 8], rax
    add rsp, 240
    pop rbx
    pop rbp
    ret
# Find one registered control ID (1..64). RAX=id, RBX=state payload.
runtime_gui_lookup:
    dec rax
    cmp rax, 63
    ja runtime_gui_lookup_bad
    shl rax, 5
    lea rax, [rbx + rax + 512]
    ret
runtime_gui_lookup_bad:
    mov rax, -9
    ret
# props: seven int64 words: operation, id, x, y, w, h, COLORREF.
# 1 label, 2 button, 3 line edit, 4 multiline edit, 5 color panel;
# 6 update text, 7 move/resize. Every boundary rechecks raw library input.
runtime_gui_control:
    push rbp
    push rbx
    sub rsp, 192
    mov rbp, rsp
    mov [rbp], rax
    mov [rbp + 8], rcx
    cmp QWORD PTR [rax], 56
    jne runtime_gui_control_invalid
    add rax, 8
    mov [rbp], rax
    mov rcx, [rax]
    cmp rcx, 1
    jl runtime_gui_control_invalid
    cmp rcx, 9
    jg runtime_gui_control_invalid
    mov rbx, [r15 + 128]
    test rbx, rbx
    jz runtime_gui_control_bad
    add rbx, 8
    cmp QWORD PTR [rbx], 0
    je runtime_gui_control_bad
    mov rax, [rax + 8]
    call runtime_gui_lookup
    test rax, rax
    js runtime_gui_control_done
    mov [rbp + 16], rax
    mov rcx, [rbp]
    cmp QWORD PTR [rcx], 6
    je runtime_gui_control_update
    cmp QWORD PTR [rcx], 9
    je runtime_gui_control_present
    mov edx, 16
runtime_gui_control_geometry:
    mov rax, [rcx + rdx]
    cmp rax, 8192
    ja runtime_gui_control_invalid
    cmp edx, 32
    jb runtime_gui_control_geometry_next
    test rax, rax
    jz runtime_gui_control_invalid
runtime_gui_control_geometry_next:
    add edx, 8
    cmp edx, 48
    jb runtime_gui_control_geometry
    cmp QWORD PTR [rcx + 48], 0xffffff
    ja runtime_gui_control_invalid
    cmp QWORD PTR [rcx], 7
    je runtime_gui_control_move
    mov rax, [rbp + 16]
    cmp QWORD PTR [rax], 0
    jne runtime_gui_control_exists
    mov rax, [rbp + 8]
    call runtime_gui_utf16
    test rax, rax
    js runtime_gui_control_done
    mov [rbp + 24], rax
    mov rdx, [rbp]
    mov rcx, [rdx]
    lea rax, [rip + runtime_gui_static]
    mov QWORD PTR [rbp + 72], 0x50000000 # WS_CHILD | WS_VISIBLE
    mov QWORD PTR [rbp + 48], 0
    cmp rcx, 1
    je runtime_gui_control_class
    cmp rcx, 5
    je runtime_gui_control_panel
    cmp rcx, 8
    je runtime_gui_control_panel
    or QWORD PTR [rbp + 72], 0x10000     # WS_TABSTOP
    lea rax, [rip + runtime_gui_button]
    cmp rcx, 2
    je runtime_gui_control_class
    lea rax, [rip + runtime_gui_edit]
    mov QWORD PTR [rbp + 48], 0x200     # WS_EX_CLIENTEDGE
    or QWORD PTR [rbp + 72], 0x80      # ES_AUTOHSCROLL
    cmp rcx, 3
    je runtime_gui_control_class
    mov QWORD PTR [rbp + 72], 0x50211044 # multiline, vertical scroll, want return
    jmp runtime_gui_control_class
runtime_gui_control_panel:
    or QWORD PTR [rbp + 72], 13         # SS_OWNERDRAW
runtime_gui_control_class:
    mov [rbp + 56], rax
    mov rax, [rbp + 24]
    add rax, 8
    mov [rbp + 64], rax
    mov rax, [rdx + 16]
    mov [rbp + 80], rax
    mov rax, [rdx + 24]
    mov [rbp + 88], rax
    mov rax, [rdx + 32]
    mov [rbp + 96], rax
    mov rax, [rdx + 40]
    mov [rbp + 104], rax
    mov rax, [rbx]
    mov [rbp + 112], rax
    mov rax, [rdx + 8]
    mov [rbp + 120], rax
    mov rax, [rbx + 16]
    mov [rbp + 128], rax
    mov QWORD PTR [rbp + 136], 0
    lea rax, [rbp + 48]
    call runtime_gui_create
    test rax, rax
    jz runtime_gui_control_os_error
    mov rcx, [rbp + 16]
    mov [rcx], rax
    mov rdx, [rbp]
    mov r8, [rdx]
    mov [rcx + 8], r8
    cmp r8, 8
    je runtime_gui_control_move
    cmp r8, 5
    je runtime_gui_control_brush
    mov rcx, rax
    mov edx, 0x30                     # WM_SETFONT
    mov r8, [rbx + 72]
    mov r9d, 1
    GUI SendMessageW
    mov rdx, [rbp]
    cmp QWORD PTR [rdx], 3
    jb runtime_gui_control_success
    cmp QWORD PTR [rdx], 4
    ja runtime_gui_control_success
    mov rax, [rbp + 16]
    mov rcx, [rax]
    mov edx, 0xc5                     # EM_SETLIMITTEXT, UTF-16 units
    mov r8d, 32767
    xor r9d, r9d
    GUI SendMessageW
    jmp runtime_gui_control_success
runtime_gui_control_brush:
    mov rcx, [rdx + 48]
    GUI CreateSolidBrush
    test rax, rax
    jz runtime_gui_control_brush_failed
    mov rcx, [rbp + 16]
    mov [rcx + 16], rax
    # MoveWindow(repaint) schedules the initial owner-drawn colored panel.
    jmp runtime_gui_control_move
runtime_gui_control_brush_failed:
    mov rax, [rbp + 16]
    mov rcx, [rax]
    GUI DestroyWindow
    mov rax, [rbp + 16]
    mov QWORD PTR [rax], 0
    jmp runtime_gui_control_os_error
runtime_gui_control_update:
    mov rax, [rbp + 16]
    cmp QWORD PTR [rax], 0
    je runtime_gui_control_bad
    cmp QWORD PTR [rax + 8], 5
    jae runtime_gui_control_invalid
    mov rax, [rbp + 8]
    call runtime_gui_utf16
    test rax, rax
    js runtime_gui_control_done
    mov [rbp + 24], rax
    lea rdx, [rax + 8]
    mov rax, [rbp + 16]
    mov rcx, [rax]
    GUI SetWindowTextW
    test eax, eax
    jz runtime_gui_control_os_error
    jmp runtime_gui_control_success
runtime_gui_control_present:
    mov rax, [rbp + 16]
    cmp QWORD PTR [rax], 0
    je runtime_gui_control_bad
    cmp QWORD PTR [rax + 8], 8
    jne runtime_gui_control_bad
    mov rax, [rbp + 8]
    call runtime_canvas_copy
    test rax, rax
    js runtime_gui_control_done
    mov [rbp + 24], rax
    mov rax, [rbp + 16]
    mov rcx, [rax]
    xor edx, edx
    xor r8d, r8d
    GUI InvalidateRect
    test eax, eax
    jz runtime_gui_control_os_error
    mov rax, [rbp + 16]
    mov rcx, [rbp + 24]
    mov [rax + 16], rcx
    jmp runtime_gui_control_success
runtime_gui_control_move:
    mov rax, [rbp + 16]
    cmp QWORD PTR [rax], 0
    je runtime_gui_control_bad
    mov rcx, [rax]
    mov rax, [rbp]
    mov rdx, [rax + 16]
    mov r8, [rax + 24]
    mov r9, [rax + 32]
    mov r10, [rax + 40]
    mov r11d, 1
    GUI MoveWindow
    test eax, eax
    jz runtime_gui_control_os_error
runtime_gui_control_success:
    xor eax, eax
    jmp runtime_gui_control_done
runtime_gui_control_exists:
    mov rax, -17
    jmp runtime_gui_control_done
runtime_gui_control_invalid:
    mov rax, -22
    jmp runtime_gui_control_done
runtime_gui_control_bad:
    mov rax, -9
    jmp runtime_gui_control_done
runtime_gui_control_os_error:
    call runtime_errno
    test rax, rax
    js runtime_gui_control_done
    mov rax, -5
runtime_gui_control_done:
    mov [r15 + 8], rax
    add rsp, 192
    pop rbx
    pop rbp
    ret
runtime_gui_text:
    push rbp
    push rbx
    sub rsp, 40
    mov rbp, rsp
    mov rbx, [r15 + 128]
    test rbx, rbx
    jz runtime_gui_text_bad
    add rbx, 8
    cmp QWORD PTR [rbx], 0
    je runtime_gui_text_bad
    call runtime_gui_lookup
    test rax, rax
    js runtime_gui_text_error
    mov rcx, [rax]
    test rcx, rcx
    jz runtime_gui_text_bad
    cmp QWORD PTR [rax + 8], 5
    jae runtime_gui_text_bad
    mov [rbp], rcx
    GUI GetWindowTextLengthW
    cmp eax, 32767
    ja runtime_gui_text_too_big
    mov [rbp + 8], rax
    lea rax, [rax*2 + 2]
    call runtime_buffer_new
    mov [rbp + 16], rax
    lea rdx, [rax + 8]
    mov r8, [rbp + 8]
    inc r8
    mov rcx, [rbp]
    GUI GetWindowTextW
    mov [rbp + 8], rax
    test eax, eax
    jz runtime_gui_text_empty
    mov r8, [rbp + 16]
    add r8, 8
    mov r9d, eax
    mov ecx, 65001
    mov edx, 0x80                     # WC_ERR_INVALID_CHARS
    xor r10d, r10d
    xor r11d, r11d
    xor esi, esi
    xor edi, edi
    API WideCharToMultiByte
    test eax, eax
    jz runtime_gui_text_invalid
    mov [rbp + 24], rax
    call runtime_buffer_new
    mov [rbp + 32], rax
    lea r10, [rax + 8]
    mov r11, [rbp + 24]
    mov r8, [rbp + 16]
    add r8, 8
    mov r9, [rbp + 8]
    mov ecx, 65001
    mov edx, 0x80
    xor esi, esi
    xor edi, edi
    API WideCharToMultiByte
    test eax, eax
    jz runtime_gui_text_invalid
    mov rax, [rbp + 32]
    mov QWORD PTR [r15 + 8], 0
    jmp runtime_gui_text_done
runtime_gui_text_empty:
    xor eax, eax
    call runtime_buffer_new
    mov QWORD PTR [r15 + 8], 0
    jmp runtime_gui_text_done
runtime_gui_text_bad:
    mov rax, -9
    jmp runtime_gui_text_error
runtime_gui_text_too_big:
    mov rax, -27
    jmp runtime_gui_text_error
runtime_gui_text_invalid:
    mov rax, -22
runtime_gui_text_error:
    mov [r15 + 8], rax
    xor eax, eax
    call runtime_buffer_new
runtime_gui_text_done:
    add rsp, 40
    pop rbx
    pop rbp
    ret
# Queue RAX=kind RCX=id RDX=value1 R8=value2. No allocation or OS calls.
runtime_gui_enqueue:
    cmp QWORD PTR [rbx + 48], 0
    jne runtime_gui_enqueue_done
    cmp QWORD PTR [rbx + 32], 64
    jae runtime_gui_enqueue_overflow
    mov r9, [rbx + 24]
    add r9, [rbx + 32]
    and r9d, 63
    shl r9, 5
    lea r9, [rbx + r9 + 2560]
    mov [r9], rax
    mov [r9 + 8], rcx
    mov [r9 + 16], rdx
    mov [r9 + 24], r8
    inc QWORD PTR [rbx + 32]
runtime_gui_enqueue_done:
    ret
runtime_gui_enqueue_overflow:
    mov QWORD PTR [rbx + 40], 1
    ret
# Win64 callback, preserving every nonvolatile register. Application-defined
# events are queued; DefWindowProc owns painting/focus/native control behavior.
runtime_gui_callback:
    push rbp
    push rbx
    push rsi
    push rdi
    push r12
    push r13
    push r14
    push r15
    sub rsp, 32
    mov rbp, rsp
    mov [rbp], rcx
    mov [rbp + 8], rdx
    mov [rbp + 16], r8
    mov [rbp + 24], r9
    mov r15, [rip + gui_process_state]
    mov rbx, [r15 + 128]
    add rbx, 8
    cmp edx, 0x10                     # WM_CLOSE: application closes explicitly
    je runtime_gui_callback_close
    cmp edx, 5                        # WM_SIZE
    je runtime_gui_callback_resize
    cmp edx, 0x111                    # WM_COMMAND
    je runtime_gui_callback_command
    cmp edx, 0x2b                     # WM_DRAWITEM for colored panels
    je runtime_gui_callback_panel
    cmp edx, 0x100                    # WM_KEYDOWN on parent
    je runtime_gui_callback_key
runtime_gui_callback_default:
    mov rcx, [rbp]
    mov rdx, [rbp + 8]
    mov r8, [rbp + 16]
    mov r9, [rbp + 24]
    GUI DefWindowProcW
    jmp runtime_gui_callback_done
runtime_gui_callback_close:
    mov eax, 1
    xor ecx, ecx
    xor edx, edx
    xor r8d, r8d
    call runtime_gui_enqueue
    xor eax, eax
    jmp runtime_gui_callback_done
runtime_gui_callback_resize:
    movzx edx, r9w
    shr r9, 16
    movzx r8d, r9w
    mov [rbx + 96], rdx
    mov [rbx + 104], r8
    mov eax, 3
    xor ecx, ecx
    call runtime_gui_enqueue
    jmp runtime_gui_callback_default
runtime_gui_callback_key:
    mov rcx, r8
    mov eax, 4
    xor edx, edx
    xor r8d, r8d
    call runtime_gui_enqueue
    jmp runtime_gui_callback_default
runtime_gui_callback_command:
    test r9, r9                      # Ignore menus/forged parent commands.
    jz runtime_gui_callback_default
    movzx eax, r8w
    mov r12, rax
    call runtime_gui_lookup
    test rax, rax
    js runtime_gui_callback_default
    cmp [rax], r9
    jne runtime_gui_callback_default
    mov edx, DWORD PTR [rbp + 16]
    shr edx, 16
    cmp QWORD PTR [rax + 8], 2
    jne runtime_gui_callback_edit
    test edx, edx                    # BN_CLICKED
    jne runtime_gui_callback_default
    mov eax, 2
    jmp runtime_gui_callback_notify
runtime_gui_callback_edit:
    cmp QWORD PTR [rax + 8], 3
    jb runtime_gui_callback_default
    cmp QWORD PTR [rax + 8], 4
    ja runtime_gui_callback_default
    cmp edx, 0x300                   # EN_CHANGE
    jne runtime_gui_callback_default
    mov eax, 5
runtime_gui_callback_notify:
    mov rcx, r12
    xor edx, edx
    xor r8d, r8d
    call runtime_gui_enqueue
    xor eax, eax
    jmp runtime_gui_callback_done
runtime_gui_callback_panel:
    mov r12, r9
    cmp DWORD PTR [r12], 5           # ODT_STATIC
    jne runtime_gui_callback_default
    mov eax, [r12 + 4]
    call runtime_gui_lookup
    test rax, rax
    js runtime_gui_callback_default
    mov rcx, [r12 + 24]
    cmp [rax], rcx
    jne runtime_gui_callback_default
    cmp QWORD PTR [rax + 8], 8
    je runtime_gui_callback_canvas
    cmp QWORD PTR [rax + 8], 5
    jne runtime_gui_callback_default
    mov r8, [rax + 16]
    test r8, r8
    jz runtime_gui_callback_default
    mov rcx, [r12 + 32]
    lea rdx, [r12 + 40]
    GUI FillRect
    mov eax, 1
runtime_gui_callback_canvas:
    call runtime_gui_canvas_paint
    mov eax, 1
runtime_gui_callback_done:
    add rsp, 32
    pop r15
    pop r14
    pop r13
    pop r12
    pop rdi
    pop rsi
    pop rbx
    pop rbp
    ret
# Return four int64 words: event kind, control ID/key, value1, value2.
# kind0=timeout, 1=close, 2=button, 3=resize, 4=key, 5=text changed.
runtime_gui_poll:
    push rbp
    push rbx
    sub rsp, 88
    mov rbp, rsp
    mov [rbp], rax
    cmp rax, -1
    jl runtime_gui_poll_invalid
    cmp rax, 2147483647
    jg runtime_gui_poll_invalid
    mov rbx, [r15 + 128]
    test rbx, rbx
    jz runtime_gui_poll_bad
    add rbx, 8
    cmp QWORD PTR [rbx], 0
    je runtime_gui_poll_bad
    mov eax, 32
    call runtime_buffer_new
    mov [rbp + 8], rax
    API GetTickCount64
    mov [rbp + 16], rax
runtime_gui_poll_more:
    cmp QWORD PTR [rbx + 40], 0
    jne runtime_gui_poll_overflow
    cmp QWORD PTR [rbx + 32], 0
    jne runtime_gui_poll_event
    lea rcx, [rbp + 32]
    xor edx, edx
    xor r8d, r8d
    xor r9d, r9d
    mov r10d, 1                     # PM_REMOVE
    GUI PeekMessageW
    test eax, eax
    jz runtime_gui_poll_wait
    cmp DWORD PTR [rbp + 40], 0x12   # external WM_QUIT becomes close request
    je runtime_gui_poll_quit
    mov rcx, [rbx]
    lea rdx, [rbp + 32]
    GUI IsDialogMessageW
    test eax, eax
    jnz runtime_gui_poll_more
    lea rcx, [rbp + 32]
    GUI TranslateMessage
    lea rcx, [rbp + 32]
    GUI DispatchMessageW
    jmp runtime_gui_poll_more
runtime_gui_poll_wait:
    # PeekMessage dispatches sent messages even when it returns FALSE. A
    # callback may just have filled our ring: drain it before any OS wait.
    cmp QWORD PTR [rbx + 40], 0
    jne runtime_gui_poll_more
    cmp QWORD PTR [rbx + 32], 0
    jne runtime_gui_poll_more
    mov r8, [rbp]
    cmp r8, -1
    je runtime_gui_poll_wait_ready
    API GetTickCount64
    sub rax, [rbp + 16]
    mov r8, [rbp]
    sub r8, rax
    jle runtime_gui_poll_success
runtime_gui_poll_wait_ready:
    xor ecx, ecx
    xor edx, edx
    mov r9d, 0x4ff                  # QS_ALLINPUT
    mov r10d, 4                     # MWMO_INPUTAVAILABLE
    GUI MsgWaitForMultipleObjectsEx
    cmp eax, -1
    je runtime_gui_poll_os_error
    cmp eax, 258                    # WAIT_TIMEOUT
    je runtime_gui_poll_success
    jmp runtime_gui_poll_more
runtime_gui_poll_quit:
    mov rax, [rbp + 8]
    mov QWORD PTR [rax + 8], 1
    jmp runtime_gui_poll_success
runtime_gui_poll_event:
    mov rax, [rbp + 8]
    lea rdi, [rax + 8]
    mov rax, [rbx + 24]
    mov rcx, rax
    inc rax
    and eax, 63
    mov [rbx + 24], rax
    dec QWORD PTR [rbx + 32]
    shl rcx, 5
    lea rsi, [rbx + rcx + 2560]
    mov ecx, 4
    rep movsq
runtime_gui_poll_success:
    mov QWORD PTR [r15 + 8], 0
    mov rax, [rbp + 8]
    jmp runtime_gui_poll_done
runtime_gui_poll_overflow:
    mov QWORD PTR [rbx + 40], 0
    mov rax, -75
    jmp runtime_gui_poll_error
runtime_gui_poll_os_error:
    call runtime_errno
    test rax, rax
    js runtime_gui_poll_error
    mov rax, -5
    jmp runtime_gui_poll_error
runtime_gui_poll_invalid:
    mov rax, -22
    jmp runtime_gui_poll_error
runtime_gui_poll_bad:
    mov rax, -9
runtime_gui_poll_error:
    mov [r15 + 8], rax
    xor eax, eax
    call runtime_buffer_new
runtime_gui_poll_done:
    add rsp, 88
    pop rbx
    pop rbp
    ret
runtime_gui_close:
    push rbp
    push rbx
    push rsi
    sub rsp, 16
    mov rbp, rsp
    mov QWORD PTR [rbp], 0
    mov rbx, [r15 + 128]
    test rbx, rbx
    jz runtime_gui_close_done
    add rbx, 8
    cmp QWORD PTR [rbx], 0
    je runtime_gui_close_done
    mov QWORD PTR [rbx + 48], 1
    mov rcx, [rbx]
    GUI DestroyWindow
    test eax, eax
    jnz runtime_gui_close_brushes
    call runtime_errno
    mov [rbp], rax
    mov QWORD PTR [rbx + 48], 0
    jmp runtime_gui_close_done
runtime_gui_close_brushes:
    mov QWORD PTR [rbx], 0
    lea rsi, [rbx + 512]
runtime_gui_close_each:
    cmp QWORD PTR [rsi + 8], 5
    jne runtime_gui_close_clear
    mov rcx, [rsi + 16]
    test rcx, rcx
    jz runtime_gui_close_clear
    GUI DeleteObject
runtime_gui_close_clear:
    mov QWORD PTR [rsi], 0
    mov QWORD PTR [rsi + 8], 0
    mov QWORD PTR [rsi + 16], 0
    add rsi, 32
    lea rax, [rbx + 2560]
    cmp rsi, rax
    jb runtime_gui_close_each
    mov QWORD PTR [rbx + 24], 0
    mov QWORD PTR [rbx + 32], 0
    mov QWORD PTR [rbx + 40], 0
runtime_gui_close_done:
    mov rax, [rbp]
    mov [r15 + 8], rax
    add rsp, 16
    pop rsi
    pop rbx
    pop rbp
    ret
runtime_gui_cleanup:
    push rax
    push rcx
    push rdx
    push rsi
    push rdi
    push QWORD PTR [r15 + 8]
    call runtime_gui_close
    pop QWORD PTR [r15 + 8]
    pop rdi
    pop rsi
    pop rdx
    pop rcx
    pop rax
    ret
.balign 2
runtime_gui_user_dll: .short 'u','s','e','r','3','2','.','d','l','l',0
.balign 2
runtime_gui_gdi_dll: .short 'g','d','i','3','2','.','d','l','l',0
.balign 2
runtime_gui_class: .short 'R','a','m','o','s','W','i','n','d','o','w',0
.balign 2
runtime_gui_static: .short 'S','T','A','T','I','C',0
.balign 2
runtime_gui_button: .short 'B','U','T','T','O','N',0
.balign 2
runtime_gui_edit: .short 'E','D','I','T',0
runtime_gui_names:
    .asciz "RegisterClassExW"
    .asciz "CreateWindowExW"
    .asciz "DefWindowProcW"
    .asciz "DestroyWindow"
    .asciz "ShowWindow"
    .asciz "AdjustWindowRectEx"
    .asciz "GetClientRect"
    .asciz "PeekMessageW"
    .asciz "TranslateMessage"
    .asciz "DispatchMessageW"
    .asciz "MsgWaitForMultipleObjectsEx"
    .asciz "IsDialogMessageW"
    .asciz "SendMessageW"
    .asciz "SetWindowTextW"
    .asciz "GetWindowTextLengthW"
    .asciz "GetWindowTextW"
    .asciz "MoveWindow"
    .asciz "LoadCursorW"
    .asciz "FillRect"
    .asciz "GetStockObject"
    .asciz "CreateSolidBrush"
    .asciz "DeleteObject"
    .asciz "SelectObject"
    .asciz "SetDCPenColor"
    .asciz "SetDCBrushColor"
    .asciz "Rectangle"
    .asciz "MoveToEx"
    .asciz "LineTo"
    .asciz "Ellipse"
    .asciz "SaveDC"
    .asciz "IntersectClipRect"
    .asciz "RestoreDC"
    .asciz "InvalidateRect"

# COMDLG32 is lazy-loaded from System32; no CRT/toolkit or application callback.
# OPENFILENAMEW is 152 bytes on Win64, initialized completely on our stack.
# File pickers select paths only; Save uses NOTESTFILECREATE and no overwrite
# prompt. The caller independently decides whether/how to publish a file.
.equ GUI_GetOpenFileNameW, 392
.equ GUI_GetSaveFileNameW, 400
.equ GUI_CommDlgExtendedError, 408
runtime_gui_choose:
    push rbp
    push rbx
    sub rsp, 240
    mov rbp, rsp
    mov [rbp], rax
    mov [rbp + 8], rcx
    mov [rbp + 16], rdx
    cmp rdx, 1
    ja runtime_gui_choose_invalid
    cmp QWORD PTR [rax], 4095
    ja runtime_gui_choose_invalid
    cmp QWORD PTR [rcx], 4095
    ja runtime_gui_choose_invalid
    mov rbx, [r15 + 128]
    test rbx, rbx
    jz runtime_gui_choose_bad
    add rbx, 8
    cmp QWORD PTR [rbx], 0
    je runtime_gui_choose_bad
    call runtime_gui_utf16
    test rax, rax
    js runtime_gui_choose_error
    mov [rbp + 24], rax
    mov rax, [rbp + 8]
    call runtime_gui_utf16
    test rax, rax
    js runtime_gui_choose_error
    mov [rbp + 32], rax
    cmp QWORD PTR [rbx + 112], 0
    jne runtime_gui_choose_loaded
    lea rcx, [rip + runtime_gui_comdlg_dll]
    xor edx, edx
    mov r8d, 0x800
    API LoadLibraryExW
    test rax, rax
    jz runtime_gui_choose_os_error
    mov [rbx + 112], rax
    mov rcx, rax
    lea rdx, [rip + runtime_gui_open_file_name]
    API GetProcAddress
    test rax, rax
    jz runtime_gui_choose_os_error
    mov [rbx + GUI_GetOpenFileNameW], rax
    mov rcx, [rbx + 112]
    lea rdx, [rip + runtime_gui_save_file_name]
    API GetProcAddress
    test rax, rax
    jz runtime_gui_choose_os_error
    mov [rbx + GUI_GetSaveFileNameW], rax
    mov rcx, [rbx + 112]
    lea rdx, [rip + runtime_gui_dialog_error_name]
    API GetProcAddress
    test rax, rax
    jz runtime_gui_choose_os_error
    mov [rbx + GUI_CommDlgExtendedError], rax
runtime_gui_choose_loaded:
    mov eax, 65536                    # 32768 UTF-16 units, including terminator.
    call runtime_buffer_new
    mov [rbp + 40], rax
    lea rdi, [rax + 8]
    mov rsi, [rbp + 32]
    mov rcx, [rsi]
    add rsi, 8
    rep movsb
    lea rdi, [rbp + 80]
    mov ecx, 20
    xor eax, eax
    rep stosq
    mov DWORD PTR [rbp + 80], 152
    mov rax, [rbx]
    mov [rbp + 88], rax
    lea rax, [rip + runtime_gui_all_files]
    mov [rbp + 104], rax
    mov DWORD PTR [rbp + 124], 1       # nFilterIndex
    mov rax, [rbp + 40]
    add rax, 8
    mov [rbp + 128], rax              # lpstrFile
    mov DWORD PTR [rbp + 136], 32768
    mov rax, [rbp + 24]
    add rax, 8
    mov [rbp + 168], rax              # lpstrTitle
    mov DWORD PTR [rbp + 176], 0x208180c # EXPLORER, NOCHANGEDIR, FILE/PATHMUSTEXIST, no recent list
    lea rcx, [rbp + 80]
    cmp QWORD PTR [rbp + 16], 0
    jne runtime_gui_choose_save
    GUI GetOpenFileNameW
    jmp runtime_gui_choose_returned
runtime_gui_choose_save:
    mov DWORD PTR [rbp + 176], 0x209080c # PATHMUSTEXIST, NOTESTFILECREATE; no overwrite prompt
    GUI GetSaveFileNameW
runtime_gui_choose_returned:
    test eax, eax
    jnz runtime_gui_choose_selected
    GUI CommDlgExtendedError
    test eax, eax
    jz runtime_gui_choose_cancel
    cmp eax, 0x3003                    # FNERR_BUFFERTOOSMALL
    je runtime_gui_choose_big
    mov rax, -5
    jmp runtime_gui_choose_error
runtime_gui_choose_selected:
    mov r8, [rbp + 40]
    add r8, 8
    xor r9d, r9d
runtime_gui_choose_wide_length:
    cmp WORD PTR [r8 + r9*2], 0
    je runtime_gui_choose_wide_ready
    inc r9d
    cmp r9d, 32768
    jae runtime_gui_choose_big
    jmp runtime_gui_choose_wide_length
runtime_gui_choose_wide_ready:
    mov [rbp + 48], r9
    mov ecx, 65001
    mov edx, 0x80                      # WC_ERR_INVALID_CHARS
    xor r10d, r10d
    xor r11d, r11d
    xor esi, esi
    xor edi, edi
    API WideCharToMultiByte
    test eax, eax
    jz runtime_gui_choose_invalid
    cmp eax, 32767
    ja runtime_gui_choose_big
    mov [rbp + 56], rax
    call runtime_buffer_new
    mov [rbp + 64], rax
    lea r10, [rax + 8]
    mov r11, [rbp + 56]
    mov r8, [rbp + 40]
    add r8, 8
    mov r9, [rbp + 48]
    mov ecx, 65001
    mov edx, 0x80
    xor esi, esi
    xor edi, edi
    API WideCharToMultiByte
    test eax, eax
    jz runtime_gui_choose_invalid
    mov QWORD PTR [r15 + 8], 0
    mov rax, [rbp + 64]
    jmp runtime_gui_choose_done
runtime_gui_choose_cancel:
    mov eax, 1
    jmp runtime_gui_choose_error
runtime_gui_choose_big:
    mov rax, -27
    jmp runtime_gui_choose_error
runtime_gui_choose_invalid:
    mov rax, -22
    jmp runtime_gui_choose_error
runtime_gui_choose_bad:
    mov rax, -9
    jmp runtime_gui_choose_error
runtime_gui_choose_os_error:
    mov QWORD PTR [rbx + 112], 0
    call runtime_errno
    test rax, rax
    js runtime_gui_choose_error
    mov rax, -5
runtime_gui_choose_error:
    mov [r15 + 8], rax
    xor eax, eax
    call runtime_buffer_new
runtime_gui_choose_done:
    add rsp, 240
    pop rbx
    pop rbp
    ret
.balign 2
runtime_gui_comdlg_dll: .short 'c','o','m','d','l','g','3','2','.','d','l','l',0
runtime_gui_open_file_name: .asciz "GetOpenFileNameW"
runtime_gui_save_file_name: .asciz "GetSaveFileNameW"
runtime_gui_dialog_error_name: .asciz "CommDlgExtendedError"
.balign 2
runtime_gui_all_files: .short 'A','l','l',' ','f','i','l','e','s',0,'*','.','*',0,0

.include "bootstrap/src/canvas_common.inc"
.include "bootstrap/windows/canvas.s.inc"
