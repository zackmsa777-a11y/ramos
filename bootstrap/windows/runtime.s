# Windows x64 native OS boundary. Compiled Ramos uses its existing private ABI;
# runtime_api supplies Microsoft's alignment, shadow space, and stack arguments.
.intel_syntax noprefix
.global runtime_writer, runtime_end, runtime_entry, entry_end, runtime_main_return
.equ BUFFER_LIMIT, 1048576
.equ BUFFER_ARENA_LIMIT, 16777216
.macro API name
    mov rax, QWORD PTR [rip + iat_\name]
    call runtime_api
.endm
.section .text
runtime_writer:
    mov edi, 1
runtime_write_fd:
    push rbp
    push rbx
    sub rsp, 24
    mov rbp, rsp
    mov rbx, rdx
    mov ecx, -11
    cmp edi, 2
    jne runtime_get_stream
    mov ecx, -12
runtime_get_stream:
    API GetStdHandle
    mov rdi, rax
runtime_write_more:
    test rbx, rbx
    jz runtime_write_done
    mov rcx, rdi
    mov rdx, rsi
    mov r8, rbx
    lea r9, [rbp]
    xor r10d, r10d
    API WriteFile
    test eax, eax
    jz runtime_write_failed
    mov eax, [rbp]
    test eax, eax
    jz runtime_write_failed
    add rsi, rax
    sub rbx, rax
    jmp runtime_write_more
runtime_write_done:
    add rsp, 24
    pop rbx
    pop rbp
    ret
runtime_write_failed:
    call runtime_gui_cleanup
    call runtime_terminal_cleanup
    mov ecx, 1
    API ExitProcess
    ud2
runtime_api:
    push rbp
    mov rbp, rsp
    and rsp, -16
    sub rsp, 96
    mov [rsp + 32], r10
    mov [rsp + 40], r11
    mov [rsp + 48], rsi
    mov [rsp + 56], rdi
    call rax
    mov rsp, rbp
    pop rbp
    ret
runtime_integer:
    sub rsp, 32
    lea rsi, [rsp + 31]
    mov BYTE PTR [rsi], 10
    call runtime_decimal_digits
    inc rdx
    call runtime_writer
    add rsp, 32
    ret
runtime_boolean:
    test rax, rax
    jz runtime_boolean_false
    lea rsi, [rip + runtime_true]
    mov edx, 5
    jmp runtime_writer
runtime_boolean_false:
    lea rsi, [rip + runtime_false]
    mov edx, 6
    jmp runtime_writer
runtime_true: .ascii "true\n"
runtime_false: .ascii "false\n"
runtime_arithmetic_error:
    lea rsi, [rip + math_message]
    mov edx, math_message_end - math_message
    jmp runtime_error
runtime_stack_budget_error:
    lea rsi, [rip + stack_message]
    mov edx, stack_message_end - stack_message
    jmp runtime_error
runtime_call_depth_error:
    lea rsi, [rip + depth_message]
    mov edx, depth_message_end - depth_message
    jmp runtime_error
runtime_buffer_size_error:
    lea rsi, [rip + size_message]
    mov edx, size_message_end - size_message
    jmp runtime_error
runtime_buffer_allocation_error:
    lea rsi, [rip + allocation_message]
    mov edx, allocation_message_end - allocation_message
    jmp runtime_error
runtime_buffer_index_error:
    lea rsi, [rip + index_message]
    mov edx, index_message_end - index_message
    jmp runtime_error
runtime_buffer_value_error:
    lea rsi, [rip + value_message]
    mov edx, value_message_end - value_message
runtime_error:
    mov edi, 2
    call runtime_write_fd
    call runtime_gui_cleanup
    call runtime_terminal_cleanup
    mov ecx, 1
    API ExitProcess
    ud2
math_message: .ascii "Ramos runtime error: arithmetic overflow or division by zero\n"
math_message_end:
stack_message: .ascii "Ramos runtime error: stack budget exceeded\n"
stack_message_end:
depth_message: .ascii "Ramos runtime error: call depth limit exceeded\n"
depth_message_end:
size_message: .ascii "Ramos runtime error: buffer size must be between 0 and 1048576\n"
size_message_end:
allocation_message: .ascii "Ramos runtime error: buffer allocation failed or arena limit exceeded\n"
allocation_message_end:
index_message: .ascii "Ramos runtime error: buffer index out of bounds\n"
index_message_end:
value_message: .ascii "Ramos runtime error: byte value must be between 0 and 255\n"
value_message_end:
runtime_heap_prepare:
    test r13, r13
    jnz runtime_heap_ready
    xor ecx, ecx
    mov edx, OFFSET FLAT:HEAP_MAPPING_SIZE
    mov r8d, 0x3000
    mov r9d, 4
    API VirtualAlloc
    test rax, rax
    jz runtime_buffer_allocation_error
    mov r13, rax
    mov QWORD PTR [r13], BUFFER_ARENA_LIMIT
runtime_heap_ready:
    ret
.include "bootstrap/src/heap_runtime.inc"
runtime_buffer_literal:
    push rsi
    call runtime_buffer_new
    pop rsi
    mov rcx, [rax]
    lea rdi, [rax + 8]
    rep movsb
    ret
runtime_buffer_len:
    mov rax, [rax]
    ret
runtime_buffer_get:
    cmp rcx, [rax]
    jae runtime_buffer_index_error
    movzx eax, BYTE PTR [rax + rcx + 8]
    ret
runtime_buffer_set:
    cmp rcx, [rax]
    jae runtime_buffer_index_error
    cmp rdx, 255
    ja runtime_buffer_value_error
    mov [rax + rcx + 8], dl
    xor eax, eax
    ret
runtime_buffer_print:
    mov rdx, [rax]
    lea rsi, [rax + 8]
    call runtime_writer
    lea rsi, [rip + newline]
    mov edx, 1
    jmp runtime_writer
newline: .byte 10
runtime_arg_count:
    mov rax, [r15 + 40]
    ret
runtime_arg:
    cmp rax, [r15 + 40]
    jae runtime_buffer_index_error
    push rbp
    push rbx
    sub rsp, 16
    mov rbp, rsp
    mov rcx, [r15]
    mov rbx, [rcx + rax*8]
    mov ecx, 65001
    mov edx, 0x80
    mov r8, rbx
    mov r9d, -1
    xor r10d, r10d
    xor r11d, r11d
    xor esi, esi
    xor edi, edi
    API WideCharToMultiByte
    test eax, eax
    jz runtime_buffer_value_error
    call runtime_buffer_new
    mov [rbp], rax
    mov ecx, 65001
    mov edx, 0x80
    mov r8, rbx
    mov r9d, -1
    lea r10, [rax + 8]
    mov r11, [rax]
    xor esi, esi
    xor edi, edi
    API WideCharToMultiByte
    test eax, eax
    jz runtime_buffer_value_error
    mov rax, [rbp]
    dec QWORD PTR [rax]
    add rsp, 16
    pop rbx
    pop rbp
    ret
runtime_io_error:
    mov rax, [r15 + 8]
    ret
runtime_stderr:
    mov rdx, [rax]
    lea rsi, [rax + 8]
    mov edi, 2
    call runtime_write_fd
    xor eax, eax
    ret
runtime_process_exit:
    cmp rax, 255
    ja runtime_buffer_value_error
    call runtime_gui_cleanup
    call runtime_terminal_cleanup
    mov rcx, rax
    API ExitProcess
    ud2
runtime_platform:
    mov eax, 1
    ret
# UTF-8 bytes -> allocated UTF-16 path or a negative common errno.
runtime_path:
    push rbp
    push rbx
    sub rsp, 16
    mov rbp, rsp
    mov rbx, rax
    mov rcx, [rax]
    test rcx, rcx
    jz runtime_path_invalid
    cmp rcx, 4096
    jae runtime_path_long
    xor edx, edx
runtime_path_scan:
    cmp BYTE PTR [rax + rdx + 8], 0
    je runtime_path_invalid
    inc rdx
    cmp rdx, rcx
    jb runtime_path_scan
    lea rax, [rcx*2 + 2]
    call runtime_buffer_new
    mov [rbp], rax
    mov ecx, 65001
    mov edx, 8
    lea r8, [rbx + 8]
    mov r9, [rbx]
    lea r10, [rax + 8]
    mov r11, [rax]
    shr r11, 1
    API MultiByteToWideChar
    test eax, eax
    jz runtime_path_invalid
    mov rax, [rbp]
    add rax, 8
    jmp runtime_path_return
runtime_path_invalid:
    mov rax, -22
    jmp runtime_path_return
runtime_path_long:
    mov rax, -36
runtime_path_return:
    add rsp, 16
    pop rbx
    pop rbp
    ret
runtime_errno:
    API GetLastError
    cmp eax, 2
    je runtime_errno_missing
    cmp eax, 3
    je runtime_errno_missing
    cmp eax, 5
    je runtime_errno_denied
    cmp eax, 80
    je runtime_errno_exists
    cmp eax, 183
    je runtime_errno_exists
    mov rax, -5
    ret
runtime_errno_missing: mov rax, -2
    ret
runtime_errno_denied: mov rax, -13
    ret
runtime_errno_exists: mov rax, -17
    ret
runtime_read_file:
    push rbp
    push rbx
    sub rsp, 128
    mov rbp, rsp
    mov QWORD PTR [rbp + 64], -1
    mov QWORD PTR [r15 + 8], 0
    call runtime_path
    test rax, rax
    js runtime_read_error
    mov rcx, rax
    mov edx, 0x80000000
    mov r8d, 7
    xor r9d, r9d
    mov r10d, 3
    mov r11d, 0x80
    xor esi, esi
    API CreateFileW
    cmp rax, -1
    je runtime_read_os_error
    mov [rbp + 64], rax
    mov rcx, rax
    API GetFileType
    cmp eax, 1
    jne runtime_read_invalid
    mov rcx, [rbp + 64]
    mov rdx, rbp
    API GetFileInformationByHandle
    test eax, eax
    jz runtime_read_os_error
    test DWORD PTR [rbp], 0x10
    jnz runtime_read_invalid
    cmp DWORD PTR [rbp + 32], 0
    jne runtime_read_large
    mov eax, [rbp + 36]
    cmp eax, BUFFER_LIMIT
    ja runtime_read_large
    call runtime_buffer_new
    mov [rbp + 72], rax
    xor ebx, ebx
runtime_read_more:
    mov rax, [rbp + 72]
    mov r8, [rax]
    sub r8, rbx
    jz runtime_read_probe
    mov rcx, [rbp + 64]
    lea rdx, [rax + rbx + 8]
    lea r9, [rbp + 80]
    xor r10d, r10d
    API ReadFile
    test eax, eax
    jz runtime_read_os_error
    mov eax, [rbp + 80]
    test eax, eax
    jz runtime_read_done
    add rbx, rax
    jmp runtime_read_more
runtime_read_probe:
    mov rcx, [rbp + 64]
    lea rdx, [rbp + 88]
    mov r8d, 1
    lea r9, [rbp + 80]
    xor r10d, r10d
    API ReadFile
    test eax, eax
    jz runtime_read_os_error
    cmp DWORD PTR [rbp + 80], 0
    jne runtime_read_large
runtime_read_done:
    mov rcx, [rbp + 64]
    mov QWORD PTR [rbp + 64], -1
    API CloseHandle
    test eax, eax
    jz runtime_read_os_error
    mov eax, [rbp + 28]
    mov [r15 + 16], rax
    mov eax, [rbp + 44]
    shl rax, 32
    mov edx, [rbp + 48]
    or rax, rdx
    mov [r15 + 24], rax
    mov QWORD PTR [r15 + 32], 1
    mov rax, [rbp + 72]
    mov [rax], rbx
    jmp runtime_read_return
runtime_read_large:
    mov rax, -27
    jmp runtime_read_error
runtime_read_invalid:
    mov rax, -22
    jmp runtime_read_error
runtime_read_os_error:
    call runtime_errno
runtime_read_error:
    mov [r15 + 8], rax
    mov rcx, [rbp + 64]
    cmp rcx, -1
    je runtime_read_empty
    API CloseHandle
runtime_read_empty:
    xor eax, eax
    call runtime_buffer_new
runtime_read_return:
    add rsp, 128
    pop rbx
    pop rbp
    ret
# Publisher state in rbp: content, flags, destination, temporary, handle,
# temporary-active, status; file info starts at +64, parent prefix at +120.
runtime_check_destination:
    mov rcx, [rbp + 16]
    xor edx, edx
    mov r8d, 7
    xor r9d, r9d
    mov r10d, 3
    mov r11d, 0x80
    xor esi, esi
    API CreateFileW
    cmp rax, -1
    je runtime_destination_missing_or_error
    push rax
    mov rcx, rax
    lea rdx, [rbp + 64]
    API GetFileInformationByHandle
    test eax, eax
    jz runtime_destination_info_failed
    pop rcx
    API CloseHandle
    mov eax, [rbp + 92]
    mov edx, [rbp + 108]
    shl rdx, 32
    mov ecx, [rbp + 112]
    or rdx, rcx
    call runtime_stream_alias
    test rax, rax
    jnz runtime_destination_alias
    mov eax, [rbp + 92]
    mov edx, [rbp + 108]
    shl rdx, 32
    mov ecx, [rbp + 112]
    or rdx, rcx
    call runtime_guard_alias
    test rax, rax
    jnz runtime_destination_alias
    cmp QWORD PTR [r15 + 32], 0
    je runtime_destination_exists
    mov eax, [rbp + 92]
    cmp rax, [r15 + 16]
    jne runtime_destination_exists
    mov eax, [rbp + 108]
    shl rax, 32
    mov edx, [rbp + 112]
    or rax, rdx
    cmp rax, [r15 + 24]
    je runtime_destination_alias
runtime_destination_exists:
    test QWORD PTR [rbp + 8], 2
    jz runtime_destination_conflict
runtime_destination_ok:
    xor eax, eax
    ret
runtime_destination_info_failed:
    pop rcx
    API CloseHandle
    mov rax, -5
    ret
runtime_destination_missing_or_error:
    call runtime_errno
    cmp rax, -2
    je runtime_destination_ok
    ret
runtime_destination_alias: mov rax, -22
    ret
runtime_destination_conflict: mov rax, -17
    ret
runtime_write_file:
    push rbp
    push rbx
    sub rsp, 160
    mov rbp, rsp
    mov [rbp], rcx
    mov [rbp + 8], rdx
    mov QWORD PTR [rbp + 32], -1
    mov QWORD PTR [rbp + 40], 0
    mov QWORD PTR [r15 + 8], 0
    cmp rdx, 3
    ja runtime_write_invalid
    call runtime_path
    test rax, rax
    js runtime_write_error
    mov [rbp + 56], rax
    # Canonicalize once; destination paths are not reinterpreted via cwd later.
    mov rax, 8192
    call runtime_buffer_new
    lea r8, [rax + 8]
    mov [rbp + 16], r8
    jmp runtime_write_fullpath
runtime_write_invalid:
    mov rax, -22
    jmp runtime_write_error
runtime_write_fullpath:
    mov rcx, [rbp + 56]
    mov edx, 4096
    mov r8, [rbp + 16]
    xor r9d, r9d
    API GetFullPathNameW
    test eax, eax
    jz runtime_write_os_error
    cmp eax, 4096
    jae runtime_write_invalid
    mov rax, [rbp + 16]
    xor ecx, ecx
    xor ebx, ebx
runtime_parent_scan:
    cmp WORD PTR [rax + rcx*2], 0
    je runtime_parent_found
    cmp WORD PTR [rax + rcx*2], 92
    jne runtime_parent_next
    lea rbx, [rcx + 1]
runtime_parent_next:
    inc rcx
    jmp runtime_parent_scan
runtime_parent_found:
    cmp rbx, 4067
    ja runtime_write_invalid
    cmp rcx, rbx
    je runtime_write_invalid
    mov [rbp + 120], rbx
    call runtime_check_destination
    test rax, rax
    js runtime_write_error
    mov rax, 8192
    call runtime_buffer_new
    lea rdi, [rax + 8]
    mov [rbp + 24], rdi
    mov rsi, [rbp + 16]
    mov rcx, [rbp + 120]
    shl rcx, 1
    rep movsb
    mov [rbp + 128], rdi
    xor ebx, ebx
runtime_temporary_retry:
    inc ebx
    cmp ebx, 16
    ja runtime_write_conflict
    API GetTickCount64
    mov [rbp + 136], rax
    API GetCurrentProcessId
    shl rax, 32
    xor [rbp + 136], rax
    inc QWORD PTR [r15 + 72]
    mov rax, [r15 + 72]
    xor [rbp + 136], rax
    mov rdi, [rbp + 128]
    lea rsi, [rip + temporary_prefix]
    mov ecx, 22
    rep movsb
    mov rax, [rbp + 136]
    mov ecx, 16
runtime_temporary_hex:
    mov edx, eax
    and edx, 15
    add edx, 97
    mov WORD PTR [rdi], dx
    add rdi, 2
    shr rax, 4
    loop runtime_temporary_hex
    mov WORD PTR [rdi], 0
    mov rsi, [rbp + 16]
    mov rdi, [rbp + 24]
runtime_temporary_compare:
    mov ax, [rsi]
    cmp ax, [rdi]
    jne runtime_temporary_open
    test ax, ax
    jz runtime_temporary_retry
    add rsi, 2
    add rdi, 2
    jmp runtime_temporary_compare
runtime_temporary_open:
    mov rcx, [rbp + 24]
    mov edx, 0x40000000
    xor r8d, r8d
    xor r9d, r9d
    mov r10d, 1
    mov r11d, 0x80
    xor esi, esi
    API CreateFileW
    cmp rax, -1
    je runtime_temporary_create_error
    mov [rbp + 32], rax
    mov QWORD PTR [rbp + 40], 1
    xor ebx, ebx
runtime_file_write_more:
    mov rax, [rbp]
    mov r8, [rax]
    sub r8, rbx
    jz runtime_file_write_done
    mov rcx, [rbp + 32]
    lea rdx, [rax + rbx + 8]
    lea r9, [rbp + 144]
    xor r10d, r10d
    API WriteFile
    test eax, eax
    jz runtime_write_os_error
    mov eax, [rbp + 144]
    test eax, eax
    jz runtime_write_zero
    add rbx, rax
    jmp runtime_file_write_more
runtime_file_write_done:
    mov rcx, [rbp + 32]
    mov QWORD PTR [rbp + 32], -1
    API CloseHandle
    test eax, eax
    jz runtime_write_os_error
    call runtime_check_destination
    test rax, rax
    js runtime_write_error
    mov rcx, [rbp + 24]
    mov rdx, [rbp + 16]
    xor r8d, r8d
    test QWORD PTR [rbp + 8], 2
    jz runtime_file_move
    mov r8d, 1
runtime_file_move:
    API MoveFileExW
    test eax, eax
    jz runtime_write_os_error
    mov QWORD PTR [rbp + 40], 0
    xor eax, eax
    jmp runtime_write_error
runtime_temporary_create_error:
    call runtime_errno
    cmp rax, -17
    je runtime_temporary_retry
    jmp runtime_write_error
runtime_write_conflict:
    mov rax, -17
    jmp runtime_write_error
runtime_write_zero:
    mov rax, -5
    jmp runtime_write_error
runtime_write_os_error:
    call runtime_errno
runtime_write_error:
    mov [rbp + 48], rax
    mov [r15 + 8], rax
    mov rcx, [rbp + 32]
    cmp rcx, -1
    je runtime_write_cleanup
    API CloseHandle
runtime_write_cleanup:
    cmp QWORD PTR [rbp + 40], 0
    je runtime_write_return
    mov rcx, [rbp + 24]
    API DeleteFileW
runtime_write_return:
    mov rax, [rbp + 48]
    add rsp, 160
    pop rbx
    pop rbp
    ret
temporary_prefix: .short '.', 'r', 'a', 'm', 'o', 's', '-', 't', 'm', 'p', '-'
.include "bootstrap/src/text_runtime.inc"
.include "bootstrap/windows/stdin.s.inc"
.set runtime_value_error, runtime_error
.include "bootstrap/src/values_runtime.inc"
.include "bootstrap/src/float_runtime.inc"
.include "bootstrap/src/source_guard.inc"
.include "bootstrap/src/stream_runtime.inc"
.include "bootstrap/windows/stream.s.inc"
.include "bootstrap/windows/terminal.s.inc"
.include "bootstrap/windows/gui.s.inc"
runtime_initialize:
    API GetCommandLineW
    mov rcx, rax
    lea rdx, [r15 + 40]
    API CommandLineToArgvW
    test rax, rax
    jz runtime_buffer_allocation_error
    mov [r15], rax
    mov ecx, 65001
    API SetConsoleOutputCP
    ret
runtime_main_return:
    call runtime_gui_cleanup
    call runtime_terminal_cleanup
    xor ecx, ecx
    API ExitProcess
    ud2
.include "bootstrap/src/system_runtime.inc"
.include "bootstrap/windows/system.s.inc"
# High-resolution QPC converted by quotient/remainder; no counter*1000 overflow.
# The clock is independent of console setup and does not allocate.
.global runtime_monotonic_ms
runtime_monotonic_ms:
    push rbp
    sub rsp, 32
    mov rbp, rsp
    mov rcx, rbp
    API QueryPerformanceFrequency
    test eax, eax
    jz runtime_monotonic_ms_os_error
    lea rcx, [rbp + 8]
    API QueryPerformanceCounter
    test eax, eax
    jz runtime_monotonic_ms_os_error
    mov rcx, [rbp]
    test rcx, rcx
    jle runtime_monotonic_ms_os_error
    mov rax, [rbp + 8]
    test rax, rax
    js runtime_monotonic_ms_range
    xor edx, edx
    div rcx
    imul rax, rax, 1000
    jo runtime_monotonic_ms_range
    mov [rbp + 16], rax
    mov rax, rdx
    imul rax, rax, 1000
    jo runtime_monotonic_ms_range
    xor edx, edx
    div rcx
    add rax, [rbp + 16]
    jo runtime_monotonic_ms_range
    mov QWORD PTR [r15 + 8], 0
    jmp runtime_monotonic_ms_done
runtime_monotonic_ms_os_error:
    mov rax, -5
    jmp runtime_monotonic_ms_fail
runtime_monotonic_ms_range:
    mov rax, -75
runtime_monotonic_ms_fail:
    mov [r15 + 8], rax
    mov rax, -1
runtime_monotonic_ms_done:
    add rsp, 32
    pop rbp
    ret
runtime_end:
runtime_entry:
    cld
    xor r12d, r12d
    xor r13d, r13d
    xor r14d, r14d
    sub rsp, 144
    mov r15, rsp
    mov rdi, rsp
    xor eax, eax
    mov ecx, 18
    rep stosq
    call runtime_initialize
    push 8064
    ldmxcsr [rsp]
    add rsp, 8
entry_end:
# Probe each Windows stack page before reserving a potentially large frame.
.global stack_probe, stack_probe_end
stack_probe:
    cmp rax, 4096
    jb stack_probe_tail
    sub rsp, 4096
    or QWORD PTR [rsp], 0
    sub rax, 4096
    jmp stack_probe
stack_probe_tail:
    sub rsp, rax
stack_probe_end:
