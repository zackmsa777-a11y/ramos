#!/usr/bin/env python3
"""Drive real Win32 windows and controls. Test harness, never a GUI runtime."""
import ctypes as C
from ctypes import wintypes as W
import json
from pathlib import Path
import subprocess
import sys
import time


def main():
    binary, mode, directory, report = sys.argv[1:]
    root = Path(directory)
    user = C.WinDLL('user32', use_last_error=True)
    gdi = C.WinDLL('gdi32', use_last_error=True)
    signatures = {
        'EnumWindows': (W.BOOL, [C.c_void_p, W.LPARAM]),
        'EnumChildWindows': (W.BOOL, [W.HWND, C.c_void_p, W.LPARAM]),
        'GetClassNameW': (C.c_int, [W.HWND, W.LPWSTR, C.c_int]),
        'GetDlgCtrlID': (C.c_int, [W.HWND]),
        'GetWindowThreadProcessId': (W.DWORD, [W.HWND, C.POINTER(W.DWORD)]),
        'GetDlgItem': (W.HWND, [W.HWND, C.c_int]),
        'IsWindowVisible': (W.BOOL, [W.HWND]),
        'IsWindow': (W.BOOL, [W.HWND]),
        'GetWindowTextW': (C.c_int, [W.HWND, W.LPWSTR, C.c_int]),
        'SendMessageW': (W.LPARAM, [W.HWND, W.UINT, W.WPARAM, W.LPARAM]),
        'PostMessageW': (W.BOOL, [W.HWND, W.UINT, W.WPARAM, W.LPARAM]),
        'SetWindowPos': (W.BOOL, [W.HWND, W.HWND, C.c_int, C.c_int, C.c_int, C.c_int, W.UINT]),
        'GetClientRect': (W.BOOL, [W.HWND, C.POINTER(W.RECT)]),
        'GetWindowRect': (W.BOOL, [W.HWND, C.POINTER(W.RECT)]),
        'GetDC': (W.HDC, [W.HWND]),
        'ReleaseDC': (C.c_int, [W.HWND, W.HDC]),
        'RedrawWindow': (W.BOOL, [W.HWND, C.c_void_p, C.c_void_p, W.UINT]),
    }
    for name, (result, args) in signatures.items():
        fn = getattr(user, name); fn.restype = result; fn.argtypes = args
    gdi.GetPixel.restype = W.DWORD
    gdi.GetPixel.argtypes = [W.HDC, C.c_int, C.c_int]
    process = subprocess.Popen([binary], cwd=root, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    result = {}
    hwnd = None

    def wait(condition, label):
        deadline = time.monotonic() + 45
        while time.monotonic() < deadline:
            value = condition()
            if value: return value
            if process.poll() is not None:
                out, err = process.communicate()
                raise AssertionError((label, process.returncode, out, err))
            time.sleep(.02)
        raise AssertionError('Timed out: ' + label)

    def find_window(title=None):
        found = []
        @C.WINFUNCTYPE(W.BOOL, W.HWND, W.LPARAM)
        def callback(window, unused):
            pid = W.DWORD()
            user.GetWindowThreadProcessId(window, C.byref(pid))
            if pid.value == process.pid and user.IsWindowVisible(window):
                caption = C.create_unicode_buffer(256)
                user.GetWindowTextW(window, caption, len(caption))
                if caption.value == (title or ('Ramos Notes' if mode in ('notes','dialogs') else 'Ramos GUI test')): found.append(window)
            return True
        user.EnumWindows(callback, 0)
        return found[0] if found else None

    def text(control):
        value = C.create_unicode_buffer(32768)
        # GetWindowTextW cannot read another process's EDIT text. WM_GETTEXT
        # is a system message whose buffer Windows marshals across processes.
        user.SendMessageW(control, 0xd, len(value), C.addressof(value))
        return value.value

    def set_text(control, value):
        # WM_SETTEXT, like WM_GETTEXT, is marshalled across process boundaries.
        raw = C.create_unicode_buffer(value)
        return user.SendMessageW(control, 0xc, 0, C.addressof(raw))

    def control(number):
        return wait(lambda: user.GetDlgItem(hwnd, number), 'control ' + str(number))

    def choose(button, title, path=None):
        assert user.PostMessageW(control(button), 0xf5, 0, 0)
        dialog = wait(lambda: find_window(title), 'file dialog ' + title)
        if path is not None:
            # Explorer-style common dialogs expose the filename edit as edt1,
            # or as the edit child of cmb13 (ComboBoxEx32 on newer Windows).
            def filename_edit():
                edit = user.GetDlgItem(dialog, 1152)
                if edit: return edit
                combo = user.GetDlgItem(dialog, 1148)
                children = []
                @C.WINFUNCTYPE(W.BOOL, W.HWND, W.LPARAM)
                def child(window, unused):
                    name = C.create_unicode_buffer(64)
                    user.GetClassNameW(window, name, len(name))
                    if name.value == 'Edit': children.append(window)
                    return True
                if combo: user.EnumChildWindows(combo, child, 0)
                return children[0] if children else None
            edit = wait(filename_edit, 'filename edit ready')
            assert set_text(edit, str(path))
        assert user.PostMessageW(dialog, 0x111, 2 if path is None else 1, 0)
        wait(lambda: not user.IsWindow(dialog), 'dismissed file dialog')

    try:
        hwnd = wait(find_window, 'visible native window')
        result['visible'] = True
        result['title'] = text(hwnd)
        if mode == 'dialogs':
            source = root / 'source-مرحبا 🌍.txt'
            destination = root / 'saved-مرحبا 🌍.txt'
            invalid = root / 'invalid.txt'
            source.write_bytes('First\r\nمرحبا 🌍'.encode())
            invalid.write_bytes(b'bad\xff')
            destination.unlink(missing_ok=True)
            entry, editor, status = [control(i) for i in (3, 4, 7)]
            choose(8, 'Open a note', source)
            wait(lambda: text(editor) == 'First\r\nمرحبا 🌍', 'opened Unicode file')
            assert text(entry) == str(source)
            result['unicode_open'] = True
            choose(9, 'Save a new note')
            wait(lambda: text(status) == 'Save As cancelled', 'cancelled Save As')
            assert text(entry) == str(source) and text(editor) == 'First\r\nمرحبا 🌍'
            result['cancel_preserves_note'] = True
            choose(8, 'Open a note', invalid)
            wait(lambda: text(status).startswith('Not opened'), 'invalid text rejected')
            assert text(entry) == str(source) and text(editor) == 'First\r\nمرحبا 🌍'
            result['invalid_open_preserves_note'] = True
            choose(9, 'Save a new note', destination)
            wait(lambda: destination.exists() and text(status) == 'Saved', 'Save As Unicode path')
            assert destination.read_bytes() == source.read_bytes()
            result['unicode_save_as'] = True
            choose(9, 'Save a new note', source)
            wait(lambda: text(status).startswith('Not saved'), 'Save As refuses existing path')
            assert source.read_bytes() == 'First\r\nمرحبا 🌍'.encode()
            result['existing_file_preserved'] = True
            pane, resize_control = control(1), editor
        elif mode == 'notes':
            path = root / 'saved-مرحبا.txt'
            path.unlink(missing_ok=True)
            entry, editor, save, clear, status = [control(i) for i in (3, 4, 5, 6, 7)]
            assert set_text(entry, str(path))
            assert set_text(editor, 'first\r\nمرحبا 🌍')
            user.SendMessageW(hwnd, 0x28, editor, 1)  # WM_NEXTDLGCTL establishes real edit focus
            user.SendMessageW(editor, 0xb1, 2147483647, 2147483647)
            assert user.PostMessageW(editor, 0x102, ord('!'), 0)
            wait(lambda: text(editor).endswith('!'), 'keyboard text editing')
            user.PostMessageW(save, 0xf5, 0, 0)
            wait(lambda: path.exists() and text(status) == 'Saved', 'save button')
            assert path.read_bytes() == 'first\r\nمرحبا 🌍!'.encode()
            result['unicode_keyboard_and_save'] = True
            assert set_text(editor, 'must not replace saved note')
            user.PostMessageW(save, 0xf5, 0, 0)
            wait(lambda: text(status).startswith('Not saved'), 'refuse overwrite')
            assert path.read_bytes() == 'first\r\nمرحبا 🌍!'.encode()
            result['existing_file_preserved'] = True
            user.PostMessageW(clear, 0xf5, 0, 0)
            wait(lambda: text(editor) == '', 'clear button')
            result['clear'] = True
            pane, resize_control = control(1), editor
        else:
            wait(lambda: text(control(1)) == 'Ready after GC', 'fixture ready after GC and lifecycle checks')
            pane, entry, button = [control(i) for i in (4, 3, 2)]
            assert set_text(entry, 'مرحبا 🌍')
            user.SendMessageW(hwnd, 0x28, entry, 1)
            user.SendMessageW(entry, 0xb1, 2147483647, 2147483647)
            assert user.PostMessageW(entry, 0x102, ord('!'), 0)
            wait(lambda: text(entry).endswith('!'), 'native keyboard input')
            user.PostMessageW(button, 0xf5, 0, 0)
            wait(lambda: text(control(1)) == 'Clicked', 'Ramos receives button event')
            result['button_and_keyboard'] = True
            resize_control = entry
        user.RedrawWindow(hwnd, None, None, 0x181)
        dc = user.GetDC(pane)
        try: result['panel_color'] = gdi.GetPixel(dc, 2, 2)
        finally: user.ReleaseDC(pane, dc)
        assert result['panel_color'] == 55 + 120 * 256 + 220 * 65536, result
        original = W.RECT(); user.GetClientRect(hwnd, C.byref(original))
        assert user.SetWindowPos(hwnd, None, 0, 0, 520, 350, 6)
        client = W.RECT(); assert user.GetClientRect(hwnd, C.byref(client))
        result['resize_expected'] = [client.right, client.bottom]
        def resized():
            # Cross-thread positioning can complete asynchronously (notably Wine).
            user.GetClientRect(hwnd, C.byref(client))
            result['resize_expected'] = [client.right, client.bottom]
            after = W.RECT(); user.GetWindowRect(resize_control, C.byref(after))
            result['resize_observed'] = [after.right - after.left, after.bottom - after.top]
            return client.right != original.right and after.right - after.left == max(360 if mode in ('notes','dialogs') else 0, client.right) - 40
        wait(resized, 'resize event relayout')
        result['resize'] = [client.right, client.bottom]
        if mode == 'dialogs':
            choose(8, 'Open a note')
            wait(lambda: text(status) == 'Open cancelled', 'cancel after resize')
            result['resized_dialog'] = True
        assert user.PostMessageW(hwnd, 0x10, 0, 0)
        out, err = process.communicate(timeout=12)
        result.update(status=process.returncode, stdout=out.decode('utf-8'), stderr=err.decode('utf-8'), closed=not user.IsWindow(hwnd))
        if mode in ('notes','dialogs'): assert process.returncode == 0 and not err, result
        else:
            assert 'مرحبا 🌍!\n' in result['stdout'], result
            assert process.returncode == (7 if mode == 'exit' else 1 if mode == 'trap' else 0), result
            if mode != 'trap': assert not err, result
        assert result['closed'], result
    finally:
        if process.poll() is None:
            result['alive_on_failure'] = True
            if hwnd:
                result['controls_on_failure'] = {str(i): text(user.GetDlgItem(hwnd,i)) for i in range(1,8)}
            process.kill()
            out, err = process.communicate()
            result['failure_stdout'] = out.decode('utf-8',errors='replace')
            result['failure_stderr'] = err.decode('utf-8',errors='replace')
        Path(report).write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')


if __name__ == '__main__':
    main()
