#!/usr/bin/env python3
"""Windows-only isolated console test worker. Not part of the Ramos runtime."""
import ctypes as C
from ctypes import wintypes as W
import json
from pathlib import Path
import struct
import subprocess
import sys
import time


def main():
    binary, mode, marker, report = sys.argv[1:]
    kernel = C.WinDLL('kernel32', use_last_error=True)
    signatures = {
        'GetStdHandle': (W.HANDLE, [W.DWORD]),
        'GetConsoleMode': (W.BOOL, [W.HANDLE, C.POINTER(W.DWORD)]),
        'SetConsoleMode': (W.BOOL, [W.HANDLE, W.DWORD]),
        'WriteConsoleInputW': (W.BOOL, [W.HANDLE, C.c_void_p, W.DWORD, C.POINTER(W.DWORD)]),
        'ReadConsoleOutputCharacterW': (W.BOOL, [W.HANDLE, C.c_void_p, W.DWORD, W.DWORD, C.POINTER(W.DWORD)]),
        'GenerateConsoleCtrlEvent': (W.BOOL, [W.DWORD, W.DWORD]),
    }
    for name, (result, arguments) in signatures.items():
        function = getattr(kernel, name); function.restype = result; function.argtypes = arguments
    input_handle, output_handle = kernel.GetStdHandle(-10), kernel.GetStdHandle(-11)
    def console_mode(handle):
        value = W.DWORD()
        if not kernel.GetConsoleMode(handle, C.byref(value)): raise C.WinError(C.get_last_error())
        return value.value
    kernel.SetConsoleMode(input_handle, console_mode(input_handle) | 7)
    before = [console_mode(input_handle), console_mode(output_handle)]
    process = subprocess.Popen([binary, marker], creationflags=subprocess.CREATE_NEW_PROCESS_GROUP)
    result = {}
    try:
        deadline = time.monotonic() + 8
        painted = False
        changed = False
        while process.poll() is None and time.monotonic() < deadline:
            changed = console_mode(input_handle) != before[0]
            value = C.create_unicode_buffer(10); count = W.DWORD()
            if kernel.ReadConsoleOutputCharacterW(output_handle, value, 9, 0x10002, C.byref(count)):
                painted = value.value == 'Ramos TUI'
            if changed and painted: break
            time.sleep(.01)
        result.update(changed=changed, painted=painted)
        if mode == 'control':
            if not kernel.GenerateConsoleCtrlEvent(1, process.pid): raise C.WinError(C.get_last_error())
        else:
            # INPUT_RECORD / KEY_EVENT_RECORD: down, repeat=1, VK_UP, no text.
            record = C.create_string_buffer(struct.pack('<HHIHHHHI', 1, 0, 1, 1, 0x26, 0, 0, 0))
            written = W.DWORD()
            if not kernel.WriteConsoleInputW(input_handle, record, 1, C.byref(written)): raise C.WinError(C.get_last_error())
        result['status'] = process.wait(timeout=8)
        result['restored'] = [console_mode(input_handle), console_mode(output_handle)] == before
        result['key'] = Path(marker).read_text() if Path(marker).exists() else None
    finally:
        if process.poll() is None: process.kill(); process.wait()
        Path(report).write_text(json.dumps(result))


if __name__ == '__main__':
    main()
