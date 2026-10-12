#!/usr/bin/env python3
"""Test-only X11 interaction with a real Ramos GTK window. No app implementation."""
import ctypes as C
import os
from pathlib import Path
import subprocess
import time

class Client(C.Structure):
    _fields_ = [('type', C.c_int), ('serial', C.c_ulong), ('send_event', C.c_int),
                ('display', C.c_void_p), ('window', C.c_ulong), ('message_type', C.c_ulong),
                ('format', C.c_int), ('data', C.c_long * 5)]

class Event(C.Union):
    _fields_ = [('client', Client), ('pad', C.c_long * 24)]

class Desktop:
    def __init__(self, env):
        self.env = env
        self.x = C.CDLL('libX11.so.6')
        for name, result, args in [
            ('XOpenDisplay', C.c_void_p, [C.c_char_p]),
            ('XInternAtom', C.c_ulong, [C.c_void_p, C.c_char_p, C.c_int]),
            ('XSendEvent', C.c_int, [C.c_void_p, C.c_ulong, C.c_int, C.c_long, C.POINTER(Event)]),
            ('XFlush', C.c_int, [C.c_void_p]),
            ('XCloseDisplay', C.c_int, [C.c_void_p]),
            ('XGetImage', C.c_void_p, [C.c_void_p, C.c_ulong, C.c_int, C.c_int, C.c_uint, C.c_uint, C.c_ulong, C.c_int]),
            ('XGetPixel', C.c_ulong, [C.c_void_p, C.c_int, C.c_int]),
            ('XDestroyImage', C.c_int, [C.c_void_p]),
        ]:
            fn = getattr(self.x, name); fn.restype = result; fn.argtypes = args
        self.display = wait(lambda: self.x.XOpenDisplay(env['DISPLAY'].encode()), 'X display ready')

    def close(self):
        self.x.XCloseDisplay(self.display)

    def command(self, *args):
        return subprocess.check_output(['xdotool', *map(str, args)], env=self.env, stderr=subprocess.DEVNULL, timeout=5)

    def window(self, title, process=None):
        def find():
            if process is not None and process.poll() is not None:
                out, err = process.communicate(timeout=5)
                raise AssertionError(f'Window {title!r} never appeared: app exit '
                                     f'{process.returncode}, stdout={out!r}, stderr={err!r}')
            try: return int(self.command('search', '--onlyvisible', '--name', '^'+title+'$').splitlines()[0])
            except (subprocess.CalledProcessError, IndexError): return None
        return wait(find, 'window '+title)

    def click(self, window, x, y):
        self.command('windowfocus', window, 'mousemove', '--window', window, x, y, 'click', '1')
        time.sleep(.12)

    def paste(self, window, x, y, text):
        self.click(window, x, y)
        self.command('key', 'ctrl+a')
        subprocess.run(['xclip', '-selection', 'clipboard'], input=text.encode(), env=self.env, check=True, timeout=5, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        self.command('key', 'ctrl+v')
        time.sleep(.15)

    def resize(self, window, width, height):
        self.command('windowsize', window, width, height)
        time.sleep(.2)

    def pixel(self, window, x, y):
        image = self.x.XGetImage(self.display, window, x, y, 1, 1, C.c_ulong(-1).value, 2)
        if not image: raise RuntimeError('Window image unavailable')
        try: return self.x.XGetPixel(image, 0, 0) & 0xffffff
        finally: self.x.XDestroyImage(image)

    def request_close(self, window):
        e = Event(); e.client.type = 33; e.client.display = self.display
        e.client.window = window; e.client.message_type = self.x.XInternAtom(self.display, b'WM_PROTOCOLS', 0)
        e.client.format = 32; e.client.data[0] = self.x.XInternAtom(self.display, b'WM_DELETE_WINDOW', 0)
        self.x.XSendEvent(self.display, window, 0, 0, C.byref(e)); self.x.XFlush(self.display)


def wait(predicate, description, seconds=5):
    deadline = time.monotonic()+seconds
    while time.monotonic() < deadline:
        result = predicate()
        if result: return result
        time.sleep(.04)
    raise AssertionError('Timed out waiting for '+description)
