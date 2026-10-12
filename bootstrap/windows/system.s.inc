.equ SYS_CWD, 4096
.equ SYS_ENV, 4104
.equ SYS_SETERROR, 4112
.equ SYS_FINDFIRST, 4120
.equ SYS_FINDNEXT, 4128
.equ SYS_FINDCLOSE, 4136
.equ SYS_CREATEPROCESS, 4144
.equ SYS_EXITCODE, 4152
.equ SYS_ATTRIBUTES, 4160
.equ SYS_MKDIR, 4168
.equ SYS_TEMP, 4176
.equ SYS_RMDIR, 4184
.macro SYSTEM_API offset
    mov rax, [r15 + 136]
    mov rax, [rax + 8 + \offset]
    call runtime_api
.endm
# Fixed, lazy KERNEL32 table avoids growing the PE import lookup area.
runtime_system_initialize:
    push rbp
    push rbx
    push rsi
    push rdi
    sub rsp, 16
    mov rbp, rsp
    call runtime_system_table
    lea rdi, [rax + 4104]
    cmp QWORD PTR [rdi + 88], 0
    jne runtime_system_initialized
    lea rcx, [rip + runtime_system_kernel]
    API GetModuleHandleW
    mov rbx, rax
    lea rsi, [rip + runtime_system_names]
runtime_system_load:
    mov rcx, rbx
    mov rdx, rsi
    API GetProcAddress
    test rax, rax
    jz runtime_system_unavailable
    mov [rdi], rax
    add rdi, 8
runtime_system_load_next:
    cmp BYTE PTR [rsi], 0
    lea rsi, [rsi + 1]
    jne runtime_system_load_next
    cmp BYTE PTR [rsi], 0
    jne runtime_system_load
runtime_system_initialized:
    xor eax, eax
    jmp runtime_system_initialize_return
runtime_system_unavailable:
    mov rax, -38
runtime_system_initialize_return:
    add rsp, 16
    pop rdi
    pop rsi
    pop rbx
    pop rbp
    ret
# General UTF-8 text -> NUL-terminated UTF-16. Empty text is allowed.
runtime_system_wide:
    push rbp
    push rbx
    sub rsp, 16
    mov rbp, rsp
    mov rbx, rax
    mov rcx, [rax]
    cmp rcx, 32767
    ja runtime_system_wide_large
    xor edx, edx
runtime_system_wide_scan:
    cmp rdx, rcx
    jae runtime_system_wide_allocate
    cmp BYTE PTR [rax + rdx + 8], 0
    je runtime_system_wide_invalid
    inc rdx
    jmp runtime_system_wide_scan
runtime_system_wide_allocate:
    lea rax, [rcx*2 + 2]
    call runtime_buffer_new
    mov [rbp], rax
    cmp QWORD PTR [rbx], 0
    je runtime_system_wide_ready
    mov ecx, 65001
    mov edx, 8
    lea r8, [rbx + 8]
    mov r9, [rbx]
    lea r10, [rax + 8]
    mov r11, [rax]
    shr r11, 1
    API MultiByteToWideChar
    test eax, eax
    jz runtime_system_wide_invalid
runtime_system_wide_ready:
    mov rax, [rbp]
    add rax, 8
    jmp runtime_system_wide_return
runtime_system_wide_large:
    mov rax, -27
    jmp runtime_system_wide_return
runtime_system_wide_invalid:
    mov rax, -22
runtime_system_wide_return:
    add rsp, 16
    pop rbx
    pop rbp
    ret
# Explicit UTF-16 pointer RAX and code-unit count RCX -> UTF-8 bytes.
runtime_system_utf8:
    test rcx, rcx
    jnz runtime_system_utf8_nonempty
    xor eax, eax
    jmp runtime_buffer_new
runtime_system_utf8_nonempty:
    push rbp
    sub rsp, 32
    mov rbp, rsp
    mov [rbp], rax
    mov [rbp + 8], rcx
    mov r8, rax
    mov r9, rcx
    mov ecx, 65001
    mov edx, 0x80
    xor r10d, r10d
    xor r11d, r11d
    xor esi, esi
    xor edi, edi
    API WideCharToMultiByte
    test eax, eax
    jz runtime_system_utf8_invalid
    cmp eax, 32767
    ja runtime_system_utf8_large
    call runtime_buffer_new
    mov [rbp + 16], rax
    mov ecx, 65001
    mov edx, 0x80
    mov r8, [rbp]
    mov r9, [rbp + 8]
    lea r10, [rax + 8]
    mov r11, [rax]
    xor esi, esi
    xor edi, edi
    API WideCharToMultiByte
    test eax, eax
    jz runtime_system_utf8_invalid
    mov rax, [rbp + 16]
    jmp runtime_system_utf8_return
runtime_system_utf8_large:
    mov rax, -27
    jmp runtime_system_utf8_return
runtime_system_utf8_invalid:
    mov rax, -22
runtime_system_utf8_return:
    add rsp, 32
    pop rbp
    ret
runtime_cwd:
    push rbp
    sub rsp, 16
    mov rbp, rsp
    call runtime_system_initialize
    test rax, rax
    js runtime_system_cwd_error
    mov eax, 65536
    call runtime_buffer_new
    mov [rbp], rax
    lea rdx, [rax + 8]
    mov ecx, 32768
    SYSTEM_API SYS_CWD
    test eax, eax
    jz runtime_system_cwd_os_error
    cmp eax, 32768
    jae runtime_system_cwd_long
    mov rcx, rax
    mov rax, [rbp]
    add rax, 8
    call runtime_system_utf8
    test rax, rax
    js runtime_system_cwd_error
    mov QWORD PTR [r15 + 8], 0
    jmp runtime_system_cwd_return
runtime_system_cwd_long:
    mov rax, -36
    jmp runtime_system_cwd_error
runtime_system_cwd_os_error:
    call runtime_errno
runtime_system_cwd_error:
    mov [r15 + 8], rax
    xor eax, eax
    call runtime_buffer_new
runtime_system_cwd_return:
    add rsp, 16
    pop rbp
    ret
runtime_env_get:
    push rbp
    sub rsp, 32
    mov rbp, rsp
    mov [rbp], rax
    mov rcx, [rax]
    test rcx, rcx
    jz runtime_system_env_invalid
    xor edx, edx
runtime_system_env_scan:
    cmp BYTE PTR [rax + rdx + 8], '='
    je runtime_system_env_invalid
    inc rdx
    cmp rdx, rcx
    jb runtime_system_env_scan
    call runtime_system_wide
    test rax, rax
    js runtime_system_env_error
    mov [rbp + 8], rax
    call runtime_system_initialize
    test rax, rax
    js runtime_system_env_error
    mov eax, 65536
    call runtime_buffer_new
    mov [rbp + 16], rax
    xor ecx, ecx
    SYSTEM_API SYS_SETERROR
    mov rcx, [rbp + 8]
    mov rdx, [rbp + 16]
    add rdx, 8
    mov r8d, 32768
    SYSTEM_API SYS_ENV
    cmp eax, 32768
    jae runtime_system_env_large
    test eax, eax
    jnz runtime_system_env_found
    API GetLastError
    cmp eax, 203
    je runtime_system_env_missing
    test eax, eax
    jnz runtime_system_env_os_error
    xor eax, eax
runtime_system_env_found:
    mov rcx, rax
    mov rax, [rbp + 16]
    add rax, 8
    call runtime_system_utf8
    test rax, rax
    js runtime_system_env_error
    mov QWORD PTR [r15 + 8], 0
    jmp runtime_system_env_return
runtime_system_env_os_error:
    mov rax, -5
    jmp runtime_system_env_error
runtime_system_env_missing:
    mov rax, -2
    jmp runtime_system_env_error
runtime_system_env_large:
    mov rax, -27
    jmp runtime_system_env_error
runtime_system_env_invalid:
    mov rax, -22
runtime_system_env_error:
    mov [r15 + 8], rax
    xor eax, eax
    call runtime_buffer_new
runtime_system_env_return:
    add rsp, 32
    pop rbp
    ret
runtime_os_dir_open:
    push rbp
    sub rsp, 24
    mov rbp, rsp
    mov [rbp], rax
    call runtime_system_initialize
    test rax, rax
    js runtime_system_dir_open_return
    mov rcx, [rbp]
    SYSTEM_API SYS_ATTRIBUTES
    cmp eax, -1
    je runtime_system_dir_open_error
    test eax, 16
    jz runtime_system_not_directory
    mov eax, 65536
    call runtime_buffer_new
    mov [rbp + 16], rax
    mov rcx, [rbp]
    mov edx, 32768
    lea r8, [rax + 8]
    xor r9d, r9d
    API GetFullPathNameW
    test eax, eax
    jz runtime_system_dir_open_error
    cmp eax, 32766
    jae runtime_system_dir_path_long
    mov rsi, [rbp + 16]
    add rsi, 8
    mov [rbp], rsi
    xor ecx, ecx
runtime_system_dir_path_length:
    cmp WORD PTR [rsi + rcx*2], 0
    je runtime_system_dir_pattern
    inc rcx
    jmp runtime_system_dir_path_length
runtime_system_dir_pattern:
    mov [rbp + 8], rcx
    lea rax, [rcx*2 + 6]
    call runtime_buffer_new
    mov [rbp + 16], rax
    lea rdi, [rax + 8]
    mov rsi, [rbp]
    mov rcx, [rbp + 8]
    rep movsw
    cmp rdi, QWORD PTR [rbp + 16]
    je runtime_system_dir_append_separator
    cmp WORD PTR [rdi - 2], '\\'
    je runtime_system_dir_append_star
    cmp WORD PTR [rdi - 2], '/'
    je runtime_system_dir_append_star
runtime_system_dir_append_separator:
    mov WORD PTR [rdi], '\\'
    add rdi, 2
runtime_system_dir_append_star:
    mov WORD PTR [rdi], '*'
    mov rcx, [rbp + 16]
    add rcx, 8
    mov rdx, [rbx + 16]
    add rdx, 8
    SYSTEM_API SYS_FINDFIRST
    cmp rax, -1
    je runtime_system_dir_first_error
    mov QWORD PTR [rbx + 56], 1
    jmp runtime_system_dir_open_return
runtime_system_dir_first_error:
    API GetLastError
    cmp eax, 2
    jne runtime_system_dir_open_error
    mov QWORD PTR [rbx + 48], 1
    xor eax, eax                   # Empty valid directory; no native handle.
    jmp runtime_system_dir_open_return
runtime_system_dir_path_long:
    mov rax, -36
    jmp runtime_system_dir_open_return
runtime_system_not_directory:
    mov rax, -20
    jmp runtime_system_dir_open_return
runtime_system_dir_open_error:
    call runtime_errno
runtime_system_dir_open_return:
    add rsp, 24
    pop rbp
    ret
runtime_os_dir_next:
    push rbp
    sub rsp, 16
    mov rbp, rsp
runtime_system_dir_more:
    cmp QWORD PTR [rbx + 48], 0
    jne runtime_system_dir_empty
    cmp QWORD PTR [rbx + 56], 0
    jne runtime_system_dir_pending
    mov rcx, [rbx]
    mov rdx, [rbx + 16]
    add rdx, 8
    SYSTEM_API SYS_FINDNEXT
    test eax, eax
    jnz runtime_system_dir_pending
    API GetLastError
    cmp eax, 18
    jne runtime_system_dir_next_error
    mov QWORD PTR [rbx + 48], 1
    jmp runtime_system_dir_empty
runtime_system_dir_pending:
    mov QWORD PTR [rbx + 56], 0
    mov rdx, [rbx + 16]
    add rdx, 8
    lea rax, [rdx + 44]            # WIN32_FIND_DATAW.cFileName
    xor ecx, ecx
runtime_system_dir_name_length:
    cmp rcx, 260
    jae runtime_system_dir_corrupt
    cmp WORD PTR [rax + rcx*2], 0
    je runtime_system_dir_name_ready
    inc rcx
    jmp runtime_system_dir_name_length
runtime_system_dir_name_ready:
    test rcx, rcx
    jz runtime_system_dir_corrupt
    cmp WORD PTR [rax], '.'
    jne runtime_system_dir_kind
    cmp rcx, 1
    je runtime_system_dir_more
    cmp rcx, 2
    jne runtime_system_dir_kind
    cmp WORD PTR [rax + 2], '.'
    je runtime_system_dir_more
runtime_system_dir_kind:
    mov esi, 1
    test DWORD PTR [rdx], 16
    jz runtime_system_dir_not_directory
    mov esi, 2
runtime_system_dir_not_directory:
    test DWORD PTR [rdx], 1024     # Reparse points include links and junctions.
    jz runtime_system_dir_kind_ready
    mov esi, 3
runtime_system_dir_kind_ready:
    mov [rbx + 40], rsi
    call runtime_system_utf8
    jmp runtime_system_dir_next_return
runtime_system_dir_corrupt:
    mov rax, -5
    jmp runtime_system_dir_next_return
runtime_system_dir_next_error:
    call runtime_errno
    jmp runtime_system_dir_next_return
runtime_system_dir_empty:
    xor eax, eax
    call runtime_buffer_new
runtime_system_dir_next_return:
    add rsp, 16
    pop rbp
    ret
runtime_os_dir_close:
    mov rcx, [rbx]
    test rcx, rcx
    jz runtime_system_dir_close_ok
    SYSTEM_API SYS_FINDCLOSE
    test eax, eax
    jz runtime_errno
runtime_system_dir_close_ok:
    xor eax, eax
    ret
# RAX -> 10 argument words, RDX -> CreateProcessW function address.
runtime_system_call10:
    push rbp
    push rbx
    mov rbp, rsp
    mov rbx, rdx
    and rsp, -16
    sub rsp, 96
    mov rcx, [rax + 32]
    mov [rsp + 32], rcx
    mov rcx, [rax + 40]
    mov [rsp + 40], rcx
    mov rcx, [rax + 48]
    mov [rsp + 48], rcx
    mov rcx, [rax + 56]
    mov [rsp + 56], rcx
    mov rcx, [rax + 64]
    mov [rsp + 64], rcx
    mov rcx, [rax + 72]
    mov [rsp + 72], rcx
    mov rcx, [rax]
    mov rdx, [rax + 8]
    mov r8, [rax + 16]
    mov r9, [rax + 24]
    call rbx
    mov rsp, rbp
    pop rbx
    pop rbp
    ret
runtime_process_run:
    push rbp
    push rbx
    sub rsp, 272
    mov rbp, rsp
    mov [rbp], rax
    mov [rbp + 8], rcx
    call runtime_path
    test rax, rax
    js runtime_system_process_error
    mov [rbp + 16], rax
    mov rax, [rbp + 8]
    call runtime_system_wide
    test rax, rax
    js runtime_system_process_error
    mov [rbp + 24], rax
    call runtime_system_initialize
    test rax, rax
    js runtime_system_process_error
    lea rdi, [rbp + 48]
    xor eax, eax
    mov ecx, 28
    rep stosq
    mov DWORD PTR [rbp + 48], 104
    mov DWORD PTR [rbp + 108], 256 # STARTF_USESTDHANDLES
    mov ecx, -10
    API GetStdHandle
    mov [rbp + 128], rax
    mov ecx, -11
    API GetStdHandle
    mov [rbp + 136], rax
    mov ecx, -12
    API GetStdHandle
    mov [rbp + 144], rax
    mov rax, [rbp + 16]
    mov [rbp + 192], rax
    mov rax, [rbp + 24]
    mov [rbp + 200], rax
    mov QWORD PTR [rbp + 224], 1  # Inherit only inheritable OS handles.
    lea rax, [rbp + 48]
    mov [rbp + 256], rax
    lea rax, [rbp + 160]
    mov [rbp + 264], rax
    mov rdx, [r15 + 136]
    mov rdx, [rdx + 8 + SYS_CREATEPROCESS]
    lea rax, [rbp + 192]
    call runtime_system_call10
    test eax, eax
    jz runtime_system_process_os_error
    mov rcx, [rbp + 168]         # Thread handle closes immediately.
    API CloseHandle
    mov rcx, [rbp + 160]
    mov edx, -1
    API WaitForSingleObject
    test eax, eax
    jnz runtime_system_process_wait_error
    mov rcx, [rbp + 160]
    lea rdx, [rbp + 40]
    SYSTEM_API SYS_EXITCODE
    test eax, eax
    jz runtime_system_process_wait_error
    mov eax, [rbp + 40]
    mov [rbp + 32], rax
    jmp runtime_system_process_close
runtime_system_process_wait_error:
    call runtime_errno
    mov [rbp + 32], rax
runtime_system_process_close:
    mov rcx, [rbp + 160]
    API CloseHandle
    mov rax, [rbp + 32]
    test rax, rax
    js runtime_system_process_error
    mov QWORD PTR [r15 + 8], 0
    jmp runtime_system_process_return
runtime_system_process_os_error:
    call runtime_errno
runtime_system_process_error:
    mov [r15 + 8], rax
runtime_system_process_return:
    add rsp, 272
    pop rbx
    pop rbp
    ret
.balign 2
runtime_system_kernel: .short 'K','E','R','N','E','L','3','2','.','d','l','l',0
runtime_system_names:
    .asciz "GetCurrentDirectoryW", "GetEnvironmentVariableW", "SetLastError"
    .asciz "FindFirstFileW", "FindNextFileW", "FindClose", "CreateProcessW"
    .asciz "GetExitCodeProcess", "GetFileAttributesW", "CreateDirectoryW", "GetTempPathW", "RemoveDirectoryW", ""

runtime_dir_create:
    push rbp
    sub rsp, 16
    mov rbp, rsp
    call runtime_path
    test rax, rax
    js runtime_system_mkdir_done
    mov [rbp], rax
    call runtime_system_initialize
    test rax, rax
    js runtime_system_mkdir_done
    mov rcx, [rbp]
    xor edx, edx
    SYSTEM_API SYS_MKDIR
    test eax, eax
    jz runtime_system_mkdir_error
    xor eax, eax
    jmp runtime_system_mkdir_done
runtime_system_mkdir_error:
    call runtime_errno
runtime_system_mkdir_done:
    mov [r15 + 8], rax
    add rsp, 16
    pop rbp
    ret

runtime_os_run_base:
    push rbp
    sub rsp, 16
    mov rbp, rsp
    call runtime_system_initialize
    test rax, rax
    js runtime_windows_run_base_return
    mov eax, 8192
    call runtime_buffer_new
    mov [rbp], rax
    lea rdx, [rax + 8]
    mov ecx, 4096
    SYSTEM_API SYS_TEMP
    test eax, eax
    jz runtime_windows_run_base_error
    cmp eax, 4096
    jae runtime_windows_run_base_long
    mov rcx, rax
    mov rax, [rbp]
    add rax, 8
    call runtime_system_utf8
    jmp runtime_windows_run_base_return
runtime_windows_run_base_long:
    mov rax, -36
    jmp runtime_windows_run_base_return
runtime_windows_run_base_error:
    call runtime_errno
runtime_windows_run_base_return:
    add rsp, 16
    pop rbp
    ret
runtime_os_run_random:
    API GetTickCount64
    push rax
    API GetCurrentProcessId
    shl rax, 32
    pop rcx
    xor rax, rcx
    mov QWORD PTR [r15 + 8], 0
    ret
runtime_os_run_mkdir:
    jmp runtime_dir_create
runtime_os_run_unlink:
    call runtime_path
    test rax, rax
    js runtime_windows_run_unlink_return
    mov rcx, rax
    API DeleteFileW
    test eax, eax
    jz runtime_errno
    xor eax, eax
runtime_windows_run_unlink_return:
    ret
runtime_os_run_rmdir:
    call runtime_path
    test rax, rax
    js runtime_windows_run_rmdir_return
    mov rcx, rax
    SYSTEM_API SYS_RMDIR
    test eax, eax
    jz runtime_errno
    xor eax, eax
runtime_windows_run_rmdir_return:
    ret
