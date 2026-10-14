#!/usr/bin/env python3
"""Reproduce embedded OS-boundary bytes. Never used to compile Ramos programs."""
import argparse
from pathlib import Path
import re
import struct
import subprocess

ROOT = Path(__file__).resolve().parents[1]
KERNEL = ['GetStdHandle', 'WriteFile', 'ExitProcess', 'VirtualAlloc',
          'WideCharToMultiByte', 'MultiByteToWideChar', 'GetLastError',
          'CreateFileW', 'CloseHandle', 'GetFileType', 'GetFileInformationByHandle',
          'ReadFile', 'GetFullPathNameW', 'GetTickCount64', 'GetCurrentProcessId',
          'MoveFileExW', 'DeleteFileW', 'GetCommandLineW', 'SetConsoleOutputCP', 'GetConsoleMode', 'SetConsoleMode',
          'GetConsoleScreenBufferInfo', 'ReadConsoleInputW', 'WaitForSingleObject', 'SetConsoleCtrlHandler', 'SetFilePointerEx', 'LoadLibraryExW', 'GetProcAddress', 'GetModuleHandleW', 'QueryPerformanceCounter', 'QueryPerformanceFrequency']
BUILTINS = ['buffer_new', 'buffer_len', 'buffer_get', 'buffer_set', 'arg_count',
            'arg', 'read_file', 'write_file', 'io_error', 'stderr', 'process_exit', 'platform',
            'read_line', 'stdin_eof', 'int_to_text', 'text_to_int', 'parse_error', 'collect', 'memory_used', 'string_from_bytes', 'string_to_bytes', 'string_len', 'string_slice',
            'array_new', 'array_len', 'array_get', 'array_set', 'array_resize',
            'string_concat', 'string_equal', 'record_new', 'record_get', 'record_set', 'array_empty', 'protect_input', 'stdout', 'file_open', 'file_read', 'file_write', 'file_eof', 'file_close', 'terminal_start', 'terminal_stop', 'terminal_width', 'terminal_height', 'terminal_key', 'file_seek', 'gui_open', 'gui_control', 'gui_text', 'gui_poll', 'gui_close',
            'cwd', 'env_get', 'dir_open', 'dir_next', 'dir_kind', 'dir_close', 'process_run', 'dir_create', 'run_file', 'float_from_int', 'float_to_int', 'float_to_text', 'float_sqrt', 'float_check', 'float_error', 'float_print', 'gui_choose', 'monotonic_ms', 'gui_open_scaled', 'gui_dpi', 'http_request']
LINUX_GUI = ['gtk_init_check', 'gtk_window_new', 'gtk_window_set_title', 'gtk_window_set_default_size', 'gtk_layout_new', 'gtk_container_add', 'gtk_widget_show_all', 'gtk_widget_destroy', 'g_signal_connect_data', 'gtk_label_new', 'gtk_label_set_xalign', 'gtk_button_new_with_label', 'gtk_entry_new', 'gtk_entry_set_max_length', 'gtk_entry_set_text', 'gtk_text_view_new', 'gtk_text_view_get_buffer', 'gtk_text_buffer_set_text', 'gtk_scrolled_window_new', 'gtk_scrolled_window_set_policy', 'gtk_drawing_area_new', 'gtk_widget_set_size_request', 'gtk_layout_put', 'gtk_layout_move', 'gtk_label_set_text', 'gtk_button_set_label', 'gtk_entry_get_text', 'gtk_label_get_text', 'gtk_button_get_label', 'gtk_text_buffer_get_bounds', 'gtk_text_buffer_get_text', 'g_free', 'gtk_main_iteration_do', 'g_timeout_add', 'g_source_remove', 'gtk_widget_grab_focus', 'gtk_text_buffer_get_char_count', 'g_utf8_strlen', 'g_signal_stop_emission_by_name', 'cairo_set_source_rgb', 'cairo_paint', 'gtk_text_view_set_wrap_mode', 'g_get_monotonic_time', 'gtk_file_chooser_dialog_new', 'gtk_dialog_add_button', 'gtk_dialog_set_default_response', 'gtk_dialog_run', 'gtk_file_chooser_set_local_only', 'gtk_file_chooser_get_filename', 'gtk_file_chooser_set_current_name', 'gtk_file_chooser_set_filename', 'g_utf8_validate', 'gtk_widget_queue_draw', 'cairo_rectangle', 'cairo_move_to', 'cairo_line_to', 'cairo_arc', 'cairo_stroke', 'cairo_fill', 'cairo_set_line_width', 'cairo_clip', 'gtk_widget_get_allocated_width', 'gtk_widget_get_allocated_height', 'cairo_status', 'gtk_widget_get_scale_factor']

LINUX_NET = ['curl_global_init', 'curl_global_cleanup', 'curl_easy_init', 'curl_easy_setopt', 'curl_easy_perform', 'curl_easy_getinfo', 'curl_easy_cleanup', 'curl_slist_append', 'curl_slist_free_all', 'getenv']

ADDRESSES = ['arithmetic_error', 'call_depth_error', 'buffer_literal', 'integer', 'boolean', 'buffer_print', 'stack_budget_error']


def run(*args):
    return subprocess.check_output(args, cwd=ROOT)


def symbols(path):
    return {v[2]: int(v[0], 16) for line in run('nm', '-n', path).decode().splitlines()
            if len(v := line.split()) == 3}


def imports():
    data = bytearray(4096)
    cursor = 832
    def name(value, hint=False):
        nonlocal cursor
        if cursor % 2:
            cursor += 1
        offset = cursor
        value = (b'\0\0' if hint else b'') + value.encode() + b'\0'
        data[cursor:cursor + len(value)] = value
        cursor += len(value)
        return 0x200000 + offset
    kernel_name = name('KERNEL32.dll')
    shell_name = name('SHELL32.dll')
    offsets = {}
    count = len(KERNEL) + 1
    assert 512 + (count + 2) * 8 <= 832, "Import lookup table overlaps names"
    for i, func in enumerate(KERNEL):
        ptr = name(func, True)
        struct.pack_into('<Q', data, 128 + i * 8, ptr)
        struct.pack_into('<Q', data, 512 + i * 8, ptr)
        offsets[func] = 128 + i * 8
    ptr = name('CommandLineToArgvW', True)
    struct.pack_into('<Q', data, 128 + count * 8, ptr)
    struct.pack_into('<Q', data, 512 + count * 8, ptr)
    offsets['CommandLineToArgvW'] = 128 + count * 8
    struct.pack_into('<IIIII', data, 0, 0x200200, 0, 0, kernel_name, 0x200080)
    struct.pack_into('<IIIII', data, 20, 0x200200 + count * 8, 0, 0, shell_name, 0x200080 + count * 8)
    assert cursor < 3000, "Import names overlap reserved console state pointer"
    return bytes(data), offsets


def linux_imports(gui, net):
    base = 0x600000
    data = bytearray(8192)
    functions = ([(i,n) for i,n in enumerate(LINUX_GUI)] if gui else [])
    if net: functions += [(len(LINUX_GUI)+i,n) for i,n in enumerate(LINUX_NET)]
    assert len(LINUX_GUI)+len(LINUX_NET) <= 79
    struct.pack_into('<Q',data,632,int(gui)+2*int(net))
    cursor = 6145
    def name(value):
        nonlocal cursor
        at=cursor; raw=value.encode()+b'\0';data[at:at+len(raw)]=raw;cursor+=len(raw)
        return at-6144
    libraries=['libgtk-3.so.0','libgobject-2.0.so.0','libglib-2.0.so.0','libcairo.so.2'] if gui else []
    if net: libraries += ['libcurl.so.4']
    needed=[name(n) for n in libraries]
    for i,(slot,n) in enumerate(functions,1):
        offset=name(n)
        struct.pack_into('<IBBHQQ',data,1024+i*24,offset,0x12,0,0,0,0)
        struct.pack_into('<QQq',data,3072+(i-1)*24,base+slot*8,(i<<32)|6,0)
    count=len(functions)+1
    struct.pack_into('<III',data,5120,1,count,1)
    for i in range(1,count):struct.pack_into('<I',data,5132+i*4,i+1 if i+1<count else 0)
    tags=[(1,n) for n in needed]+[(4,base+5120),(5,base+6144),(6,base+1024),(10,cursor-6144),(11,24),(7,base+3072),(8,len(functions)*24),(9,24),(0,0)]
    for i,(tag,value) in enumerate(tags):struct.pack_into('<QQ',data,640+i*16,tag,value)
    assert 1024+count*24<=3072 and 3072+len(functions)*24<=5120
    assert 5132+count*4<=6144 and cursor<=len(data) and len(tags)*16<=256
    return bytes(data)

def generated():
    run('make', 'build/stage0')
    sample = ROOT / 'build/runtime-data.ramos'
    sample.write_text('fn main() {}\n')
    run('./build/stage0', 'build', str(sample), '-o', 'build/runtime-data', '--force')
    sym = symbols('build/stage0')
    for i, name in enumerate(LINUX_GUI):
        assert sym['LG_' + name] == 0x600000 + i*8, name
    for i, name in enumerate(LINUX_NET):
        assert sym['HC_' + name] == 0x600000 + (len(LINUX_GUI)+i)*8, name
    binary = (ROOT / 'build/runtime-data').read_bytes()
    end = 4096 + sym['RUNTIME_SIZE']
    result = {
        'runtime_text': binary[4096:end],
        'entry_text': binary[end:end + sym['ENTRY_INITIALIZE_SIZE']],
        'runtime_end': end,
        'linux_gui_imports': linux_imports(True, False),
        'linux_net_imports': linux_imports(False, True),
        'linux_gui_net_imports': linux_imports(True, True),
    }
    for fn, label in zip(['math_address', 'depth_address', 'literal_address', 'integer_address',
                          'boolean_address', 'print_buffer_address', 'stack_address'], ADDRESSES):
        result[fn] = 4096 + sym['runtime_' + label] - sym['runtime_writer']
    # The source names the Linux exit intrinsic runtime_process_exit.
    result['builtin_address'] = [4096 + sym['runtime_' + n] - sym['runtime_writer'] for n in BUILTINS]
    blob, offsets = imports()
    (ROOT / 'build/windows-imports.bin').write_bytes(blob)
    asm = '.intel_syntax noprefix\n.section .idata,"aw"\nimports:\n.incbin "build/windows-imports.bin"\n'
    for n, offset in offsets.items():
        asm += f'.global iat_{n}\n.set iat_{n}, imports + {offset}\n'
    asm += '.global terminal_process_state\n.set terminal_process_state, imports + 3000\n'
    asm += '.global gui_process_state\n.set gui_process_state, imports + 3008\n'
    (ROOT / 'build/windows-imports.s').write_text(asm)
    run('as', '--64', '-o', 'build/windows-runtime.o', 'bootstrap/windows/runtime.s')
    run('as', '--64', '-o', 'build/windows-imports.o', 'build/windows-imports.s')
    run('ld', '--build-id=none', '--section-start=.text=0x1000', '--section-start=.idata=0x200000',
        '-e', 'runtime_entry', '-o', 'build/windows-runtime.elf', 'build/windows-runtime.o', 'build/windows-imports.o')
    run('objcopy', '--dump-section', '.text=build/windows-runtime.bin', 'build/windows-runtime.elf')
    sym = symbols('build/windows-runtime.elf')
    for name in ('temporary_prefix', 'runtime_gui_user_dll', 'runtime_gui_gdi_dll',
                 'runtime_gui_class', 'runtime_gui_static', 'runtime_gui_button',
                 'runtime_gui_edit', 'runtime_gui_comdlg_dll', 'runtime_gui_all_files',
                 'runtime_system_kernel', 'runtime_gui_dpi_font'):
        assert sym[name] % 2 == 0, f'Unaligned Windows UTF-16 constant: {name}'
    code = (ROOT / 'build/windows-runtime.bin').read_bytes()
    end = sym['runtime_end'] - 4096
    result.update(windows_runtime=code[:end], windows_entry=code[end:sym['entry_end'] - 4096],
                  windows_imports=blob, windows_iat_size=(len(KERNEL) + 3) * 8, windows_end=sym['runtime_end'],
                  windows_stack_probe=code[sym['stack_probe'] - 4096:sym['stack_probe_end'] - 4096],
                  windows_return=sym['runtime_main_return'])
    result['windows_address'] = [sym['runtime_' + n] for n in ADDRESSES]
    result['windows_builtin'] = [sym['runtime_' + n] for n in BUILTINS]
    return result


def functions(data):
    result = []
    for name, value in data.items():
        if isinstance(value, bytes):
            result.append(f'fn {name}() -> bytes {{ return "{value.hex()}" }}')
        elif isinstance(value, int):
            result.append(f'fn {name}() -> int64 {{ return {value} }}')
        else:
            body = '\n'.join(f'    if n == {i} {{ return {v} }}' for i, v in enumerate(value))
            result.append(f'fn {name}(n: int64) -> int64 {{\n{body}\n    return 0\n}}')
    return '\n'.join(result) + '\n'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--write', action='store_true', help='update the checked-in boundary data')
    args = parser.parse_args()
    path = ROOT / 'compiler/ramos.ramos'
    source = path.read_text()
    suffix = functions(generated())
    start = source.index('fn runtime_text()')
    if args.write:
        path.write_text(source[:start] + suffix)
    elif source[start:] != suffix:
        raise SystemExit('Embedded runtime data differs; run python3 tools/runtime_data.py --write')
    print('Linux and Windows embedded OS-boundary bytes verified')


if __name__ == '__main__':
    main()
