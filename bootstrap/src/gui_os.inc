# Optional Linux GTK3 boundary. --gui maps an audited import table at 0x600000.
# Static ELF programs have three headers and never touch that table. GTK owns
# its widgets; a rooted Ramos buffer owns stable callback data and the ring.
# No callback calls Ramos or allocates a managed value. Native calls use SysV.
.equ LG_BASE, 0x600000
# Slot order is audited against tools/runtime_data.py by its symbol check.
.equ LG_gtk_init_check, LG_BASE + 0
.equ LG_gtk_window_new, LG_BASE + 8
.equ LG_gtk_window_set_title, LG_BASE + 16
.equ LG_gtk_window_set_default_size, LG_BASE + 24
.equ LG_gtk_layout_new, LG_BASE + 32
.equ LG_gtk_container_add, LG_BASE + 40
.equ LG_gtk_widget_show_all, LG_BASE + 48
.equ LG_gtk_widget_destroy, LG_BASE + 56
.equ LG_g_signal_connect_data, LG_BASE + 64
.equ LG_gtk_label_new, LG_BASE + 72
.equ LG_gtk_label_set_xalign, LG_BASE + 80
.equ LG_gtk_button_new_with_label, LG_BASE + 88
.equ LG_gtk_entry_new, LG_BASE + 96
.equ LG_gtk_entry_set_max_length, LG_BASE + 104
.equ LG_gtk_entry_set_text, LG_BASE + 112
.equ LG_gtk_text_view_new, LG_BASE + 120
.equ LG_gtk_text_view_get_buffer, LG_BASE + 128
.equ LG_gtk_text_buffer_set_text, LG_BASE + 136
.equ LG_gtk_scrolled_window_new, LG_BASE + 144
.equ LG_gtk_scrolled_window_set_policy, LG_BASE + 152
.equ LG_gtk_drawing_area_new, LG_BASE + 160
.equ LG_gtk_widget_set_size_request, LG_BASE + 168
.equ LG_gtk_layout_put, LG_BASE + 176
.equ LG_gtk_layout_move, LG_BASE + 184
.equ LG_gtk_label_set_text, LG_BASE + 192
.equ LG_gtk_button_set_label, LG_BASE + 200
.equ LG_gtk_entry_get_text, LG_BASE + 208
.equ LG_gtk_label_get_text, LG_BASE + 216
.equ LG_gtk_button_get_label, LG_BASE + 224
.equ LG_gtk_text_buffer_get_bounds, LG_BASE + 232
.equ LG_gtk_text_buffer_get_text, LG_BASE + 240
.equ LG_g_free, LG_BASE + 248
.equ LG_gtk_main_iteration_do, LG_BASE + 256
.equ LG_g_timeout_add, LG_BASE + 264
.equ LG_g_source_remove, LG_BASE + 272
.equ LG_gtk_widget_grab_focus, LG_BASE + 280
.equ LG_gtk_text_buffer_get_char_count, LG_BASE + 288
.equ LG_g_utf8_strlen, LG_BASE + 296
.equ LG_g_signal_stop_emission_by_name, LG_BASE + 304
.equ LG_cairo_set_source_rgb, LG_BASE + 312
.equ LG_cairo_paint, LG_BASE + 320
.equ LG_gtk_text_view_set_wrap_mode, LG_BASE + 328
.equ LG_g_get_monotonic_time, LG_BASE + 336
.equ LG_gtk_file_chooser_dialog_new, LG_BASE + 344
.equ LG_gtk_dialog_add_button, LG_BASE + 352
.equ LG_gtk_dialog_set_default_response, LG_BASE + 360
.equ LG_gtk_dialog_run, LG_BASE + 368
.equ LG_gtk_file_chooser_set_local_only, LG_BASE + 376
.equ LG_gtk_file_chooser_get_filename, LG_BASE + 384
.equ LG_gtk_file_chooser_set_current_name, LG_BASE + 392
.equ LG_gtk_file_chooser_set_filename, LG_BASE + 400
.equ LG_g_utf8_validate, LG_BASE + 408
.equ LG_gtk_widget_queue_draw, LG_BASE + 416
.equ LG_cairo_rectangle, LG_BASE + 424
.equ LG_cairo_move_to, LG_BASE + 432
.equ LG_cairo_line_to, LG_BASE + 440
.equ LG_cairo_arc, LG_BASE + 448
.equ LG_cairo_stroke, LG_BASE + 456
.equ LG_cairo_fill, LG_BASE + 464
.equ LG_cairo_set_line_width, LG_BASE + 472
.equ LG_cairo_clip, LG_BASE + 480
.equ LG_gtk_widget_get_allocated_width, LG_BASE + 488
.equ LG_gtk_widget_get_allocated_height, LG_BASE + 496
.equ LG_cairo_status, LG_BASE + 504
.equ LG_gtk_widget_get_scale_factor, LG_BASE + 512
.macro LG name
    mov r11d, LG_\name
    call runtime_lg_call
.endm
runtime_lg_call:
    push rbp
    mov rbp, rsp
    and rsp, -16
    call QWORD PTR [r11]
    mov rsp, rbp
    pop rbp
    ret
runtime_lg_enabled:
    mov r11d, 0x400000
    cmp WORD PTR [r11 + 56], 7
    ret
runtime_lg_table:
    mov rbx, [r15 + 128]
    test rbx, rbx
    jnz runtime_lg_table_ready
    mov eax, 8192
    call runtime_buffer_new
    mov [r15 + 128], rax
    mov rbx, rax
runtime_lg_table_ready:
    add rbx, 8
    ret
# Fallible strict UTF-8/NUL validation needs no GTK initialization.
# The managed terminated copy remains rooted on the caller's stack.
runtime_lg_string:
    push rbp
    mov rbp, rsp
    sub rsp, 32
    mov [rbp - 8], rax
    cmp QWORD PTR [rax], 32767
    ja runtime_lg_string_bad
    xor ecx, ecx
runtime_lg_string_scan:
    cmp rcx, [rax]
    jae runtime_lg_string_valid
    cmp BYTE PTR [rax + rcx + 8], 0
    je runtime_lg_string_bad
    inc rcx
    jmp runtime_lg_string_scan
runtime_lg_string_valid:
    # Validate by a local fallible version of the shared strict decoder.
    lea rsi, [rax + 8]
    mov rdi, [rax]
    add rdi, rsi
runtime_lg_utf8_next:
    cmp rsi, rdi
    jae runtime_lg_string_copy
    movzx edx, BYTE PTR [rsi]
    inc rsi
    cmp edx, 128
    jb runtime_lg_utf8_next
    cmp edx, 194
    jb runtime_lg_string_bad
    cmp edx, 244
    ja runtime_lg_string_bad
    mov r8d, 1
    mov r9d, 128
    mov r10d, 191
    cmp edx, 224
    jb runtime_lg_utf8_cont
    mov r8d, 2
    cmp edx, 224
    jne runtime_lg_utf8_ed
    mov r9d, 160
runtime_lg_utf8_ed:
    cmp edx, 237
    jne runtime_lg_utf8_four
    mov r10d, 159
runtime_lg_utf8_four:
    cmp edx, 240
    jb runtime_lg_utf8_cont
    mov r8d, 3
    mov r9d, 128
    mov r10d, 191
    cmp edx, 240
    jne runtime_lg_utf8_f4
    mov r9d, 144
runtime_lg_utf8_f4:
    cmp edx, 244
    jne runtime_lg_utf8_cont
    mov r10d, 143
runtime_lg_utf8_cont:
    cmp rsi, rdi
    jae runtime_lg_string_bad
    movzx edx, BYTE PTR [rsi]
    inc rsi
    cmp edx, r9d
    jb runtime_lg_string_bad
    cmp edx, r10d
    ja runtime_lg_string_bad
    mov r9d, 128
    mov r10d, 191
    dec r8d
    jnz runtime_lg_utf8_cont
    jmp runtime_lg_utf8_next
runtime_lg_string_copy:
    mov rax, [rbp - 8]
    mov rax, [rax]
    inc rax
    call runtime_buffer_new
    mov [rbp - 16], rax
    lea rdi, [rax + 8]
    mov rsi, [rbp - 8]
    mov rcx, [rsi]
    add rsi, 8
    rep movsb
    mov rax, [rbp - 16]
    jmp runtime_lg_string_done
runtime_lg_string_bad:
    mov rax, -22
runtime_lg_string_done:
    leave
    ret
runtime_gui_open:
    xor r8d, r8d
    jmp runtime_lg_open_common
runtime_gui_open_scaled:
    mov r8d, 1
runtime_lg_open_common:
    call runtime_lg_enabled
    jne runtime_lg_unsupported
    push rbp
    push rbx
    sub rsp, 48
    mov rbp, rsp
    mov [rbp], rax
    mov [rbp + 8], rcx
    mov [rbp + 16], rdx
    mov [rbp + 32], r8
    cmp rcx, 160
    jl runtime_lg_open_invalid
    cmp rcx, 4096
    jg runtime_lg_open_invalid
    cmp rdx, 80
    jl runtime_lg_open_invalid
    cmp rdx, 4096
    jg runtime_lg_open_invalid
    cmp QWORD PTR [rax], 4095
    ja runtime_lg_open_invalid
    call runtime_lg_string
    test rax, rax
    js runtime_lg_open_done
    mov [rbp + 24], rax
    call runtime_lg_table
    cmp QWORD PTR [rbx], 0
    jne runtime_lg_open_busy
    xor edi, edi
    xor esi, esi
    LG gtk_init_check
    test eax, eax
    jz runtime_lg_open_no_display
    xor edi, edi
    LG gtk_window_new
    mov [rbx], rax
    mov rdi, rax
    mov rsi, [rbp + 24]
    add rsi, 8
    LG gtk_window_set_title
    mov rdi, [rbx]
    mov rsi, [rbp + 8]
    mov rdx, [rbp + 16]
    LG gtk_window_set_default_size
    xor edi, edi
    xor esi, esi
    LG gtk_layout_new
    mov [rbx + 8], rax
    mov rdi, [rbx]
    mov rsi, rax
    LG gtk_container_add
    mov [rbx + 56], r15
    mov rax, [rbp + 32]
    mov [rbx + 104], rax
    mov QWORD PTR [rbx + 96], 0
    test rax, rax
    jz runtime_lg_open_signals
    mov rdi, [rbx]
    lea rsi, [rip + runtime_lg_scale_name]
    lea rdx, [rip + runtime_lg_scale_cb]
    mov rcx, rbx
    call runtime_lg_connect
runtime_lg_open_signals:
    mov rdi, [rbx]
    lea rsi, [rip + runtime_lg_delete_name]
    lea rdx, [rip + runtime_lg_delete_cb]
    mov rcx, rbx
    call runtime_lg_connect
    mov rdi, [rbx]
    lea rsi, [rip + runtime_lg_size_name]
    lea rdx, [rip + runtime_lg_size_cb]
    mov rcx, rbx
    call runtime_lg_connect
    mov rdi, [rbx]
    lea rsi, [rip + runtime_lg_key_name]
    lea rdx, [rip + runtime_lg_key_cb]
    mov rcx, rbx
    call runtime_lg_connect
    mov rdi, [rbx]
    LG gtk_widget_show_all
    mov rdi, [rbx]
    LG gtk_widget_get_scale_factor
    imul eax, eax, 96
    mov [rbx + 96], rax
    xor eax, eax
    jmp runtime_lg_open_done
runtime_lg_open_busy:
    mov rax, -16
    jmp runtime_lg_open_done
runtime_lg_open_invalid:
    mov rax, -22
    jmp runtime_lg_open_done
runtime_lg_open_no_display:
    mov rax, -19
runtime_lg_open_done:
    mov [r15 + 8], rax
    add rsp, 48
    pop rbx
    pop rbp
    ret
runtime_lg_unsupported:
    mov rax, -38
    mov [r15 + 8], rax
    ret
runtime_lg_connect:
    xor r8d, r8d
    xor r9d, r9d
    LG g_signal_connect_data
    ret
# RAX=id -> RCX=control slot. No handles escape the boundary.
runtime_lg_lookup:
    cmp rax, 1
    jl runtime_lg_lookup_bad
    cmp rax, 64
    jg runtime_lg_lookup_bad
    imul rax, rax, 48
    lea rcx, [rbx + rax + 128]
    xor eax, eax
    ret
runtime_lg_lookup_bad:
    mov rax, -9
    ret
runtime_gui_control:
    call runtime_lg_enabled
    jne runtime_lg_unsupported
    push rbp
    push rbx
    sub rsp, 64
    mov rbp, rsp
    mov [rbp], rax
    mov [rbp + 8], rcx
    cmp QWORD PTR [rax], 56
    jne runtime_lg_control_invalid
    mov rdx, [rax + 8]
    cmp rdx, 1
    jl runtime_lg_control_invalid
    cmp rdx, 9
    jg runtime_lg_control_invalid
    mov [rbp + 16], rdx
    mov rbx, [r15 + 128]
    test rbx, rbx
    jz runtime_lg_control_bad
    add rbx, 8
    cmp QWORD PTR [rbx], 0
    je runtime_lg_control_bad
    mov rax, [rax + 16]
    call runtime_lg_lookup
    test rax, rax
    js runtime_lg_control_done
    mov [rbp + 24], rcx
    cmp QWORD PTR [rbp + 16], 6
    je runtime_lg_control_update
    cmp QWORD PTR [rbp + 16], 9
    je runtime_lg_control_present
    mov rax, [rbp]
    mov ecx, 24
runtime_lg_geometry:
    mov rdx, [rax + rcx]
    cmp rdx, 8192
    ja runtime_lg_control_invalid
    cmp ecx, 40
    jb runtime_lg_geometry_next
    test rdx, rdx
    jz runtime_lg_control_invalid
runtime_lg_geometry_next:
    add ecx, 8
    cmp ecx, 56
    jb runtime_lg_geometry
    cmp QWORD PTR [rax + 56], 16777215
    ja runtime_lg_control_invalid
    cmp QWORD PTR [rbp + 16], 7
    je runtime_lg_control_move
    mov rcx, [rbp + 24]
    cmp QWORD PTR [rcx], 0
    jne runtime_lg_control_exists
    mov rax, [rbp + 8]
    call runtime_lg_string
    test rax, rax
    js runtime_lg_control_done
    mov [rbp + 32], rax
    mov rax, [rbp + 16]
    cmp eax, 1
    je runtime_lg_create_label
    cmp eax, 2
    je runtime_lg_create_button
    cmp eax, 3
    je runtime_lg_create_input
    cmp eax, 4
    je runtime_lg_create_editor
    LG gtk_drawing_area_new
    jmp runtime_lg_created
runtime_lg_create_label:
    mov rdi, [rbp + 32]
    add rdi, 8
    LG gtk_label_new
    mov [rbp + 40], rax
    mov rdi, rax
    xorps xmm0, xmm0
    LG gtk_label_set_xalign
    mov rax, [rbp + 40]
    jmp runtime_lg_created
runtime_lg_create_button:
    mov rdi, [rbp + 32]
    add rdi, 8
    LG gtk_button_new_with_label
    jmp runtime_lg_created
runtime_lg_create_input:
    LG gtk_entry_new
    mov [rbp + 40], rax
    mov rdi, rax
    mov esi, 32767
    LG gtk_entry_set_max_length
    mov rdi, [rbp + 40]
    mov rsi, [rbp + 32]
    add rsi, 8
    LG gtk_entry_set_text
    mov rax, [rbp + 40]
    jmp runtime_lg_created
runtime_lg_create_editor:
    LG gtk_text_view_new
    mov [rbp + 40], rax
    mov rdi, rax
    mov esi, 2
    LG gtk_text_view_set_wrap_mode
    mov rdi, [rbp + 40]
    LG gtk_text_view_get_buffer
    mov rdi, rax
    mov rsi, [rbp + 32]
    add rsi, 8
    mov edx, -1
    LG gtk_text_buffer_set_text
    mov rax, [rbp + 40]
runtime_lg_created:
    mov rcx, [rbp + 24]
    mov [rcx], rax
    mov [rcx + 16], rax
    mov rdx, [rbp + 16]
    mov [rcx + 8], rdx
    mov rdx, [rbp]
    mov rax, [rdx + 16]
    mov [rcx + 24], rax
    mov [rcx + 32], rbx
    mov rax, [rdx + 56]
    mov [rcx + 40], rax
    cmp QWORD PTR [rcx + 8], 8
    jne runtime_lg_created_color
    mov QWORD PTR [rcx + 40], 0
runtime_lg_created_color:
    cmp QWORD PTR [rcx + 8], 4
    jne runtime_lg_add_child
    xor edi, edi
    xor esi, esi
    LG gtk_scrolled_window_new
    mov rcx, [rbp + 24]
    mov [rcx + 16], rax
    mov rdi, rax
    mov esi, 1
    mov edx, 1
    LG gtk_scrolled_window_set_policy
    mov rcx, [rbp + 24]
    mov rdi, [rcx + 16]
    mov rsi, [rcx]
    LG gtk_container_add
runtime_lg_add_child:
    mov rcx, [rbp + 24]
    mov rdi, [rbx + 8]
    mov rsi, [rcx + 16]
    mov rax, [rbp]
    mov rdx, [rax + 24]
    mov rcx, [rax + 32]
    LG gtk_layout_put
    mov rcx, [rbp + 24]
    mov rdi, [rcx + 16]
    mov rax, [rbp]
    mov rsi, [rax + 40]
    mov rdx, [rax + 48]
    LG gtk_widget_set_size_request
    mov rcx, [rbp + 24]
    mov rdi, [rcx]
    mov rax, [rcx + 8]
    cmp eax, 1
    je runtime_lg_show
    cmp eax, 2
    je runtime_lg_button_signal
    cmp eax, 3
    je runtime_lg_changed_signal
    cmp eax, 5
    je runtime_lg_draw_signal
    cmp eax, 8
    je runtime_lg_draw_signal
    LG gtk_text_view_get_buffer
    mov rdi, rax
    mov [rbp + 48], rax
    lea rsi, [rip + runtime_lg_insert_name]
    lea rdx, [rip + runtime_lg_insert_cb]
    mov rcx, [rbp + 24]
    call runtime_lg_connect
    mov rdi, [rbp + 48]
runtime_lg_changed_signal:
    lea rsi, [rip + runtime_lg_changed_name]
    lea rdx, [rip + runtime_lg_changed_cb]
    jmp runtime_lg_signal
runtime_lg_button_signal:
    lea rsi, [rip + runtime_lg_clicked_name]
    lea rdx, [rip + runtime_lg_clicked_cb]
    jmp runtime_lg_signal
runtime_lg_draw_signal:
    lea rsi, [rip + runtime_lg_draw_name]
    lea rdx, [rip + runtime_lg_draw_cb]
runtime_lg_signal:
    mov rcx, [rbp + 24]
    call runtime_lg_connect
runtime_lg_show:
    mov rcx, [rbp + 24]
    mov rdi, [rcx + 16]
    LG gtk_widget_show_all
    jmp runtime_lg_control_success
runtime_lg_control_update:
    mov rcx, [rbp + 24]
    cmp QWORD PTR [rcx], 0
    je runtime_lg_control_bad
    cmp QWORD PTR [rcx + 8], 5
    jae runtime_lg_control_invalid
    mov rax, [rbp + 8]
    call runtime_lg_string
    test rax, rax
    js runtime_lg_control_done
    mov [rbp + 32], rax
    mov rcx, [rbp + 24]
    mov rdi, [rcx]
    mov rsi, rax
    add rsi, 8
    mov rax, [rcx + 8]
    cmp eax, 1
    je runtime_lg_update_label
    cmp eax, 2
    je runtime_lg_update_button
    cmp eax, 3
    je runtime_lg_update_input
    LG gtk_text_view_get_buffer
    mov rdi, rax
    mov rsi, [rbp + 32]
    add rsi, 8
    mov edx, -1
    LG gtk_text_buffer_set_text
    jmp runtime_lg_control_success
runtime_lg_update_label:
    LG gtk_label_set_text
    jmp runtime_lg_control_success
runtime_lg_update_button:
    LG gtk_button_set_label
    jmp runtime_lg_control_success
runtime_lg_update_input:
    LG gtk_entry_set_text
    jmp runtime_lg_control_success
runtime_lg_control_present:
    mov rcx, [rbp + 24]
    cmp QWORD PTR [rcx], 0
    je runtime_lg_control_bad
    cmp QWORD PTR [rcx + 8], 8
    jne runtime_lg_control_bad
    mov rax, [rbp + 8]
    call runtime_canvas_copy
    test rax, rax
    js runtime_lg_control_done
    mov rcx, [rbp + 24]
    mov [rcx + 40], rax
    mov rdi, [rcx]
    LG gtk_widget_queue_draw
    jmp runtime_lg_control_success
runtime_lg_control_move:
    mov rcx, [rbp + 24]
    cmp QWORD PTR [rcx], 0
    je runtime_lg_control_bad
    mov rdi, [rcx + 16]
    mov rax, [rbp]
    mov rsi, [rax + 40]
    mov rdx, [rax + 48]
    LG gtk_widget_set_size_request
    mov rdi, [rbx + 8]
    mov rcx, [rbp + 24]
    mov rsi, [rcx + 16]
    mov rax, [rbp]
    mov rdx, [rax + 24]
    mov rcx, [rax + 32]
    LG gtk_layout_move
runtime_lg_control_success:
    xor eax, eax
    jmp runtime_lg_control_done
runtime_lg_control_bad:
    mov rax, -9
    jmp runtime_lg_control_done
runtime_lg_control_exists:
    mov rax, -17
    jmp runtime_lg_control_done
runtime_lg_control_invalid:
    mov rax, -22
runtime_lg_control_done:
    mov [r15 + 8], rax
    add rsp, 64
    pop rbx
    pop rbp
    ret
runtime_gui_text:
    call runtime_lg_enabled
    jne runtime_lg_bytes_unsupported
    push rbp
    push rbx
    sub rsp, 192
    mov rbp, rsp
    mov [rbp], rax
    mov QWORD PTR [rbp + 8], 0
    mov rbx, [r15 + 128]
    test rbx, rbx
    jz runtime_lg_text_bad
    add rbx, 8
    cmp QWORD PTR [rbx], 0
    je runtime_lg_text_bad
    mov rax, [rbp]
    call runtime_lg_lookup
    test rax, rax
    js runtime_lg_text_error
    cmp QWORD PTR [rcx], 0
    je runtime_lg_text_bad
    mov rdi, [rcx]
    mov rax, [rcx + 8]
    cmp eax, 1
    je runtime_lg_text_label
    cmp eax, 2
    je runtime_lg_text_button
    cmp eax, 3
    je runtime_lg_text_input
    cmp eax, 4
    jne runtime_lg_text_bad
    LG gtk_text_view_get_buffer
    mov [rbp + 16], rax
    mov rdi, rax
    lea rsi, [rbp + 32]
    lea rdx, [rbp + 112]
    LG gtk_text_buffer_get_bounds
    mov rdi, [rbp + 16]
    lea rsi, [rbp + 32]
    lea rdx, [rbp + 112]
    xor ecx, ecx
    LG gtk_text_buffer_get_text
    mov [rbp + 8], rax
    jmp runtime_lg_text_copy
runtime_lg_text_label:
    LG gtk_label_get_text
    jmp runtime_lg_text_copy
runtime_lg_text_button:
    LG gtk_button_get_label
    jmp runtime_lg_text_copy
runtime_lg_text_input:
    LG gtk_entry_get_text
runtime_lg_text_copy:
    mov [rbp + 16], rax
    xor edx, edx
runtime_lg_text_length:
    cmp BYTE PTR [rax + rdx], 0
    je runtime_lg_text_allocate
    inc rdx
    cmp rdx, 1048576
    ja runtime_lg_text_big
    jmp runtime_lg_text_length
runtime_lg_text_allocate:
    mov [rbp + 24], rdx
    mov rax, rdx
    call runtime_buffer_new
    mov [rbp], rax
    lea rdi, [rax + 8]
    mov rsi, [rbp + 16]
    mov rcx, [rbp + 24]
    rep movsb
    xor eax, eax
    mov [r15 + 8], rax
    jmp runtime_lg_text_free
runtime_lg_text_big:
    mov rax, -27
    jmp runtime_lg_text_error
runtime_lg_text_bad:
    mov rax, -9
runtime_lg_text_error:
    mov [r15 + 8], rax
    xor eax, eax
    call runtime_buffer_new
    mov [rbp], rax
runtime_lg_text_free:
    mov rdi, [rbp + 8]
    test rdi, rdi
    jz runtime_lg_text_done
    LG g_free
runtime_lg_text_done:
    mov rax, [rbp]
    add rsp, 192
    pop rbx
    pop rbp
    ret
runtime_lg_bytes_unsupported:
    mov QWORD PTR [r15 + 8], -38
    xor eax, eax
    jmp runtime_buffer_new
# Callback queue arguments: RDI=state, RSI=kind, RDX=id, RCX=w, R8=h.
runtime_lg_enqueue:
    cmp QWORD PTR [rdi], 0
    je runtime_lg_enqueue_done
    cmp QWORD PTR [rdi + 24], 64
    jae runtime_lg_enqueue_full
    mov rax, [rdi + 16]
    add rax, [rdi + 24]
    and eax, 63
    shl eax, 5
    lea rax, [rdi + rax + 4096]
    mov [rax], rsi
    mov [rax + 8], rdx
    mov [rax + 16], rcx
    mov [rax + 24], r8
    inc QWORD PTR [rdi + 24]
runtime_lg_enqueue_done:
    ret
runtime_lg_enqueue_full:
    mov QWORD PTR [rdi + 32], -75
    ret
runtime_lg_delete_cb:
    mov rdi, rdx
    mov esi, 1
    xor edx, edx
    xor ecx, ecx
    xor r8d, r8d
    call runtime_lg_enqueue
    mov eax, 1                          # Keep window alive until gui_close.
    ret
runtime_lg_size_cb:
    mov ecx, [rsi + 8]
    mov r8d, [rsi + 12]
    cmp rcx, [rdx + 40]
    jne runtime_lg_size_changed
    cmp r8, [rdx + 48]
    je runtime_lg_callback_false
runtime_lg_size_changed:
    mov [rdx + 40], rcx
    mov [rdx + 48], r8
    mov rdi, rdx
    mov esi, 3
    xor edx, edx
    jmp runtime_lg_enqueue
runtime_lg_key_cb:
    # GdkEventKey.keyval at +28. Normalize common keys to Windows virtual codes.
    mov eax, [rsi + 28]
    cmp eax, 97
    jb runtime_lg_key_special
    cmp eax, 122
    ja runtime_lg_key_special
    sub eax, 32
runtime_lg_key_special:
    cmp eax, 0xff08
    jne runtime_lg_key_tab
    mov eax, 8
runtime_lg_key_tab:
    cmp eax, 0xff09
    jne runtime_lg_key_return
    mov eax, 9
runtime_lg_key_return:
    cmp eax, 0xff0d
    jne runtime_lg_key_escape
    mov eax, 13
runtime_lg_key_escape:
    cmp eax, 0xff1b
    jne runtime_lg_key_arrows
    mov eax, 27
runtime_lg_key_arrows:
    cmp eax, 0xff51
    jb runtime_lg_key_queue
    cmp eax, 0xff54
    ja runtime_lg_key_queue
    sub eax, 0xff51 - 37
runtime_lg_key_queue:
    mov rdi, rdx
    mov edx, eax
    mov esi, 4
    xor ecx, ecx
    xor r8d, r8d
    call runtime_lg_enqueue
runtime_lg_callback_false:
    xor eax, eax
    ret
runtime_lg_clicked_cb:
    mov edx, 2
    jmp runtime_lg_control_cb
runtime_lg_changed_cb:
    mov edx, 5
runtime_lg_control_cb:
    mov rdi, [rsi + 32]
    mov eax, edx
    mov rdx, [rsi + 24]
    mov esi, eax
    xor ecx, ecx
    xor r8d, r8d
    jmp runtime_lg_enqueue
runtime_lg_insert_cb:
    # (buffer, iter, text, byte length, user data). Native editing cap is 32767
    # Unicode scalars on GTK, UTF-16 units on Windows; supplied text is UTF-8.
    push rbp
    mov rbp, rsp
    sub rsp, 32
    mov [rbp - 8], rdi
    mov [rbp - 16], rdx
    mov [rbp - 24], rcx
    LG gtk_text_buffer_get_char_count
    mov [rbp - 32], rax
    mov rdi, [rbp - 16]
    mov rsi, [rbp - 24]
    LG g_utf8_strlen
    add rax, [rbp - 32]
    cmp rax, 32767
    jbe runtime_lg_insert_done
    mov rdi, [rbp - 8]
    lea rsi, [rip + runtime_lg_insert_name]
    LG g_signal_stop_emission_by_name
runtime_lg_insert_done:
    leave
    ret
runtime_lg_draw_cb:
    cmp QWORD PTR [rdx + 8], 8
    je runtime_lg_canvas_cb
    push rbp
    mov rbp, rsp
    sub rsp, 16
    mov [rbp - 8], rsi
    mov eax, [rdx + 40]
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
    mov rdi, rsi
    LG cairo_set_source_rgb
    mov rdi, [rbp - 8]
    LG cairo_paint
    xor eax, eax
    leave
    ret
runtime_lg_timeout_cb:
    mov QWORD PTR [rdi + 72], 1
    xor eax, eax
    ret
runtime_gui_poll:
    call runtime_lg_enabled
    jne runtime_lg_bytes_unsupported
    push rbp
    push rbx
    sub rsp, 48
    mov rbp, rsp
    mov [rbp], rax
    cmp rax, -1
    jl runtime_lg_poll_invalid
    cmp rax, 2147483647
    jg runtime_lg_poll_invalid
    mov rbx, [r15 + 128]
    test rbx, rbx
    jz runtime_lg_poll_bad
    add rbx, 8
    cmp QWORD PTR [rbx], 0
    je runtime_lg_poll_bad
    mov eax, 32
    call runtime_buffer_new
    mov [rbp + 8], rax
    mov QWORD PTR [rbp + 16], 0
    mov QWORD PTR [rbx + 72], 0
    cmp QWORD PTR [rbp], 0
    jle runtime_lg_poll_more
    mov rdi, [rbp]
    lea rsi, [rip + runtime_lg_timeout_cb]
    mov rdx, rbx
    LG g_timeout_add
    mov [rbp + 16], rax
runtime_lg_poll_more:
    cmp QWORD PTR [rbx + 32], 0
    jne runtime_lg_poll_overflow
    cmp QWORD PTR [rbx + 24], 0
    jne runtime_lg_poll_event
    cmp QWORD PTR [rbx + 72], 0
    jne runtime_lg_poll_success
    cmp QWORD PTR [rbp], 0
    je runtime_lg_poll_nowait
    mov edi, 1
    LG gtk_main_iteration_do
    jmp runtime_lg_poll_more
runtime_lg_poll_nowait:
    xor edi, edi
    LG gtk_main_iteration_do
    # Nonblocking poll processes one iteration, then returns an event or timeout.
    cmp QWORD PTR [rbx + 32], 0
    jne runtime_lg_poll_overflow
    cmp QWORD PTR [rbx + 24], 0
    je runtime_lg_poll_success
runtime_lg_poll_event:
    mov rax, [rbx + 16]
    shl eax, 5
    lea rsi, [rbx + rax + 4096]
    mov rdi, [rbp + 8]
    add rdi, 8
    mov ecx, 4
    rep movsq
    inc QWORD PTR [rbx + 16]
    and QWORD PTR [rbx + 16], 63
    dec QWORD PTR [rbx + 24]
runtime_lg_poll_success:
    xor eax, eax
    mov [r15 + 8], rax
    jmp runtime_lg_poll_remove
runtime_lg_poll_overflow:
    mov rax, [rbx + 32]
    mov QWORD PTR [rbx + 32], 0
    jmp runtime_lg_poll_error
runtime_lg_poll_invalid:
    mov rax, -22
    jmp runtime_lg_poll_error_empty
runtime_lg_poll_bad:
    mov rax, -9
runtime_lg_poll_error_empty:
    mov [r15 + 8], rax
    xor eax, eax
    call runtime_buffer_new
    mov [rbp + 8], rax
    jmp runtime_lg_poll_done
runtime_lg_poll_error:
    mov [r15 + 8], rax
    xor eax, eax
    call runtime_buffer_new
    mov [rbp + 8], rax
runtime_lg_poll_remove:
    cmp QWORD PTR [rbx + 72], 0
    jne runtime_lg_poll_done
    mov rdi, [rbp + 16]
    test rdi, rdi
    jz runtime_lg_poll_done
    LG g_source_remove
runtime_lg_poll_done:
    mov rax, [rbp + 8]
    add rsp, 48
    pop rbx
    pop rbp
    ret
runtime_gui_close:
    push rbp
    push rbx
    sub rsp, 8
    mov rbx, [r15 + 128]
    test rbx, rbx
    jz runtime_lg_close_done
    add rbx, 8
    mov rdi, [rbx]
    test rdi, rdi
    jz runtime_lg_close_done
    mov [rsp], rdi
    mov QWORD PTR [rbx], 0           # Suppress callbacks during destruction.
    mov rdi, [rbx + 80]
    test rdi, rdi
    jz runtime_lg_close_parent
    mov QWORD PTR [rbx + 80], 0
    LG gtk_widget_destroy
runtime_lg_close_parent:
    mov rdi, [rsp]
    LG gtk_widget_destroy
    mov rdi, rbx
    mov ecx, 1024
    xor eax, eax
    rep stosq
runtime_lg_close_done:
    xor eax, eax
    mov [r15 + 8], rax
    add rsp, 8
    pop rbx
    pop rbp
    ret
runtime_gui_cleanup:
    push QWORD PTR [r15 + 8]
    call runtime_gui_close
    pop QWORD PTR [r15 + 8]
    ret
runtime_lg_delete_name: .asciz "delete-event"
runtime_lg_size_name: .asciz "size-allocate"
runtime_lg_key_name: .asciz "key-press-event"
runtime_lg_clicked_name: .asciz "clicked"
runtime_lg_changed_name: .asciz "changed"
runtime_lg_draw_name: .asciz "draw"
runtime_lg_insert_name: .asciz "insert-text"

# Single local-file picker. Only the GUI toolkit pumps during this modal call;
# callback data remains rooted and no Ramos callback or managed allocation runs.
runtime_gui_choose:
    call runtime_lg_enabled
    jne runtime_lg_bytes_unsupported
    push rbp
    push rbx
    sub rsp, 80
    mov rbp, rsp
    mov [rbp], rax
    mov [rbp + 8], rcx
    mov [rbp + 16], rdx
    mov QWORD PTR [rbp + 32], 0
    mov rbx, [r15 + 128]
    cmp rdx, 1
    ja runtime_lg_choose_invalid
    cmp QWORD PTR [rax], 4095
    ja runtime_lg_choose_invalid
    cmp QWORD PTR [rcx], 4095
    ja runtime_lg_choose_invalid
    test rbx, rbx
    jz runtime_lg_choose_bad
    add rbx, 8
    cmp QWORD PTR [rbx], 0
    je runtime_lg_choose_bad
    call runtime_lg_string
    test rax, rax
    js runtime_lg_choose_error
    mov [rbp + 24], rax
    mov rax, [rbp + 8]
    call runtime_lg_string
    test rax, rax
    js runtime_lg_choose_error
    mov [rbp + 8], rax
    mov rdi, [rbp + 24]
    add rdi, 8
    mov rsi, [rbx]
    mov rdx, [rbp + 16]
    xor ecx, ecx                      # End the varargs button list immediately.
    xor eax, eax                      # SysV variadic vector argument count.
    LG gtk_file_chooser_dialog_new
    test rax, rax
    jz runtime_lg_choose_os_error
    mov [rbx + 80], rax
    mov rdi, rax
    mov esi, 1
    LG gtk_file_chooser_set_local_only
    mov rdi, [rbx + 80]
    lea rsi, [rip + runtime_lg_cancel_button]
    mov edx, -6                       # GTK_RESPONSE_CANCEL
    LG gtk_dialog_add_button
    mov rdi, [rbx + 80]
    lea rsi, [rip + runtime_lg_open_button]
    cmp QWORD PTR [rbp + 16], 0
    je runtime_lg_choose_accept
    lea rsi, [rip + runtime_lg_save_button]
runtime_lg_choose_accept:
    mov edx, -3                       # GTK_RESPONSE_ACCEPT
    LG gtk_dialog_add_button
    mov rdi, [rbx + 80]
    mov esi, -3
    LG gtk_dialog_set_default_response
    mov rax, [rbp + 8]
    cmp QWORD PTR [rax], 1             # Terminated copy includes the NUL byte.
    je runtime_lg_choose_show
    lea rsi, [rax + 8]
    mov rdi, [rbx + 80]
    cmp QWORD PTR [rbp + 16], 0
    je runtime_lg_choose_filename
    # Save initial is a suggested filename; slash finds its leaf.
    mov rcx, rsi
runtime_lg_choose_leaf:
    cmp BYTE PTR [rcx], 0
    je runtime_lg_choose_leaf_ready
    cmp BYTE PTR [rcx], '/'
    jne runtime_lg_choose_leaf_next
    lea rsi, [rcx + 1]
runtime_lg_choose_leaf_next:
    inc rcx
    jmp runtime_lg_choose_leaf
runtime_lg_choose_leaf_ready:
    LG gtk_file_chooser_set_current_name
    jmp runtime_lg_choose_show
runtime_lg_choose_filename:
    LG gtk_file_chooser_set_filename
runtime_lg_choose_show:
    mov rdi, [rbx + 80]
    LG gtk_dialog_run
    cmp eax, -3
    jne runtime_lg_choose_cancelled
    mov rdi, [rbx + 80]
    LG gtk_file_chooser_get_filename
    test rax, rax
    jz runtime_lg_choose_invalid
    mov [rbp + 32], rax
    mov rdi, rax
    mov rsi, -1
    xor edx, edx
    LG g_utf8_validate
    test eax, eax
    jz runtime_lg_choose_invalid
    mov rax, [rbp + 32]
    xor edx, edx
runtime_lg_choose_length:
    cmp BYTE PTR [rax + rdx], 0
    je runtime_lg_choose_copy
    inc rdx
    cmp rdx, 32767
    ja runtime_lg_choose_big
    jmp runtime_lg_choose_length
runtime_lg_choose_copy:
    mov rsi, rax
    mov rax, rdx
    call runtime_buffer_literal
    mov [rbp + 48], rax
    mov QWORD PTR [rbp + 56], 0
    jmp runtime_lg_choose_cleanup
runtime_lg_choose_cancelled:
    mov eax, 1
    jmp runtime_lg_choose_error
runtime_lg_choose_big:
    mov rax, -27
    jmp runtime_lg_choose_error
runtime_lg_choose_os_error:
    mov rax, -5
    jmp runtime_lg_choose_error
runtime_lg_choose_bad:
    mov rax, -9
    jmp runtime_lg_choose_error
runtime_lg_choose_invalid:
    mov rax, -22
runtime_lg_choose_error:
    mov [rbp + 56], rax
    xor eax, eax
    call runtime_buffer_new
    mov [rbp + 48], rax
runtime_lg_choose_cleanup:
    mov rdi, [rbp + 32]
    test rdi, rdi
    jz runtime_lg_choose_destroy
    LG g_free
runtime_lg_choose_destroy:
    mov rbx, [r15 + 128]
    test rbx, rbx
    jz runtime_lg_choose_done
    add rbx, 8
    mov rdi, [rbx + 80]
    test rdi, rdi
    jz runtime_lg_choose_done
    mov QWORD PTR [rbx + 80], 0
    LG gtk_widget_destroy
runtime_lg_choose_done:
    mov rax, [rbp + 56]
    mov [r15 + 8], rax
    mov rax, [rbp + 48]
    add rsp, 80
    pop rbx
    pop rbp
    ret
runtime_lg_cancel_button: .asciz "Cancel"
runtime_lg_open_button: .asciz "Open"
runtime_lg_save_button: .asciz "Save"

.include "bootstrap/src/canvas_common.inc"
.include "bootstrap/src/canvas_linux.inc"

# Query does not pump events or allocate managed data.
runtime_gui_dpi:
    call runtime_lg_enabled
    jne runtime_lg_unsupported
    push rbx
    mov rbx, [r15 + 128]
    test rbx, rbx
    jz runtime_lg_dpi_bad
    add rbx, 8
    mov rdi, [rbx]
    test rdi, rdi
    jz runtime_lg_dpi_bad
    LG gtk_widget_get_scale_factor
    test eax, eax
    jle runtime_lg_dpi_error
    imul rax, rax, 96
    mov QWORD PTR [r15 + 8], 0
    pop rbx
    ret
runtime_lg_dpi_bad:
    mov rax, -9
    jmp runtime_lg_dpi_done
runtime_lg_dpi_error:
    mov rax, -5
runtime_lg_dpi_done:
    mov [r15 + 8], rax
    pop rbx
    ret
runtime_lg_scale_cb:
    push rbx
    mov rbx, rdx
    cmp QWORD PTR [rbx], 0
    je runtime_lg_scale_done
    LG gtk_widget_get_scale_factor
    test eax, eax
    jle runtime_lg_scale_error
    imul rax, rax, 96
    cmp rax, [rbx + 96]
    je runtime_lg_scale_done
    mov rdx, [rbx + 96]
    mov [rbx + 96], rax
    test rdx, rdx
    jz runtime_lg_scale_done             # No initial-creation notification.
    mov rdi, rbx
    mov edx, eax
    mov esi, 6
    mov rcx, [rbx + 40]
    mov r8, [rbx + 48]
    call runtime_lg_enqueue
    jmp runtime_lg_scale_done
runtime_lg_scale_error:
    mov QWORD PTR [rbx + 32], -5
runtime_lg_scale_done:
    pop rbx
    ret
runtime_lg_scale_name: .asciz "notify::scale-factor"
