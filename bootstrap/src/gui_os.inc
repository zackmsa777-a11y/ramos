# Desktop GUI has a native Windows backend in 0.13. Linux stays static and
# reports ENOSYS explicitly; adding a display-server backend is separate work.
runtime_gui_open:
runtime_gui_control:
    mov rax, -38
    mov [r15 + 8], rax
    ret
runtime_gui_text:
runtime_gui_poll:
    mov QWORD PTR [r15 + 8], -38
    xor eax, eax
    jmp runtime_buffer_new
runtime_gui_close:
    xor eax, eax
    mov [r15 + 8], rax
    ret
