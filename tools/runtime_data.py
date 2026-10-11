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
          'GetConsoleScreenBufferInfo', 'ReadConsoleInputW', 'WaitForSingleObject', 'SetConsoleCtrlHandler', 'SetFilePointerEx', 'LoadLibraryExW', 'GetProcAddress', 'GetModuleHandleW']
BUILTINS = ['buffer_new', 'buffer_len', 'buffer_get', 'buffer_set', 'arg_count',
            'arg', 'read_file', 'write_file', 'io_error', 'stderr', 'process_exit', 'platform',
            'read_line', 'stdin_eof', 'int_to_text', 'text_to_int', 'parse_error', 'collect', 'memory_used', 'string_from_bytes', 'string_to_bytes', 'string_len', 'string_slice',
            'array_new', 'array_len', 'array_get', 'array_set', 'array_resize',
            'string_concat', 'string_equal', 'record_new', 'record_get', 'record_set', 'array_empty', 'protect_input', 'stdout', 'file_open', 'file_read', 'file_write', 'file_eof', 'file_close', 'terminal_start', 'terminal_stop', 'terminal_width', 'terminal_height', 'terminal_key', 'file_seek', 'gui_open', 'gui_control', 'gui_text', 'gui_poll', 'gui_close',
            'cwd', 'env_get', 'dir_open', 'dir_next', 'dir_kind', 'dir_close', 'process_run', 'dir_create', 'run_file']
ADDRESSES = ['arithmetic_error', 'call_depth_error', 'buffer_literal', 'integer', 'boolean', 'buffer_print']


def run(*args):
    return subprocess.check_output(args, cwd=ROOT)


def symbols(path):
    return {v[2]: int(v[0], 16) for line in run('nm', '-n', path).decode().splitlines()
            if len(v := line.split()) == 3}


def imports():
    data = bytearray(4096)
    cursor = 768
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
    assert 512 + (count + 2) * 8 <= 768, "Import lookup table overlaps names"
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


def generated():
    run('make', 'build/stage0')
    sample = ROOT / 'build/runtime-data.ramos'
    sample.write_text('fn main() {}\n')
    run('./build/stage0', 'build', str(sample), '-o', 'build/runtime-data', '--force')
    sym = symbols('build/stage0')
    binary = (ROOT / 'build/runtime-data').read_bytes()
    end = 4096 + sym['RUNTIME_SIZE']
    result = {
        'runtime_text': binary[4096:end],
        'entry_text': binary[end:end + sym['ENTRY_INITIALIZE_SIZE']],
        'runtime_end': end,
    }
    for fn, label in zip(['math_address', 'depth_address', 'literal_address', 'integer_address',
                          'boolean_address', 'print_buffer_address'], ADDRESSES):
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
