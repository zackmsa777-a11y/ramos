#!/usr/bin/env python3
"""Native Windows DPI/resource acceptance; runs only test tooling in Python.

The single-display checks do not certify an actual Windows DPI transition.
Use examples/scaling.ramos on an adjustable display for that final acceptance.
"""
import ctypes as C
from ctypes import wintypes as W
import json
from pathlib import Path
import subprocess
import sys
import time
from scaling_output import Output


def main():
    binary, report = sys.argv[1:]
    user = C.WinDLL('user32', use_last_error=True)
    gdi = C.WinDLL('gdi32', use_last_error=True)
    kernel = C.WinDLL('kernel32', use_last_error=True)
    for dll, name, result, args in [
        (user,'EnumWindows',W.BOOL,[C.c_void_p,W.LPARAM]),
        (user,'GetWindowThreadProcessId',W.DWORD,[W.HWND,C.POINTER(W.DWORD)]),
        (user,'GetWindowTextW',C.c_int,[W.HWND,W.LPWSTR,C.c_int]),
        (user,'GetDlgItem',W.HWND,[W.HWND,C.c_int]),
        (user,'IsWindowVisible',W.BOOL,[W.HWND]),
        (user,'IsWindow',W.BOOL,[W.HWND]),
        (user,'PostMessageW',W.BOOL,[W.HWND,W.UINT,W.WPARAM,W.LPARAM]),
        (user,'SendMessageW',W.LPARAM,[W.HWND,W.UINT,W.WPARAM,W.LPARAM]),
        (user,'GetWindowRect',W.BOOL,[W.HWND,C.POINTER(W.RECT)]),
        (user,'GetClientRect',W.BOOL,[W.HWND,C.POINTER(W.RECT)]),
        (user,'ClientToScreen',W.BOOL,[W.HWND,C.POINTER(W.POINT)]),
        (user,'GetDpiForWindow',W.UINT,[W.HWND]),
        (user,'GetWindowDpiAwarenessContext',W.HANDLE,[W.HWND]),
        (user,'GetAwarenessFromDpiAwarenessContext',C.c_int,[W.HANDLE]),
        (user,'AreDpiAwarenessContextsEqual',W.BOOL,[W.HANDLE,W.HANDLE]),
        (user,'SetThreadDpiAwarenessContext',W.HANDLE,[W.HANDLE]),
        (user,'GetThreadDpiAwarenessContext',W.HANDLE,[]),
        (user,'GetDC',W.HDC,[W.HWND]),
        (user,'ReleaseDC',C.c_int,[W.HWND,W.HDC]),
        (user,'GetGuiResources',W.DWORD,[W.HANDLE,W.DWORD]),
        (gdi,'GetPixel',W.DWORD,[W.HDC,C.c_int,C.c_int]),
        (gdi,'GetObjectW',C.c_int,[W.HANDLE,C.c_int,C.c_void_p]),
        (kernel,'OpenProcess',W.HANDLE,[W.DWORD,W.BOOL,W.DWORD]),
        (kernel,'GetProcessHandleCount',W.BOOL,[W.HANDLE,C.POINTER(W.DWORD)]),
        (kernel,'CloseHandle',W.BOOL,[W.HANDLE]),
    ]:
        fn=getattr(dll,name); fn.restype=result; fn.argtypes=args
    old=user.SetThreadDpiAwarenessContext(W.HANDLE(-4))
    assert old, 'Harness needs native per-monitor-v2 support'
    proc=None; handle=None
    result={'genuine_windows_transition':False,
            'transition_status':'pending adjustable-display manual test'}
    def wait(check,label):
        deadline=time.monotonic()+20
        while time.monotonic()<deadline:
            value=check()
            if value:return value
            if proc.poll() is not None:
                raise AssertionError((label,proc.returncode,proc.stderr.read()))
            time.sleep(.01)
        raise AssertionError('Timed out: '+label)
    def find():
        found=[]
        @C.WINFUNCTYPE(W.BOOL,W.HWND,W.LPARAM)
        def cb(window,unused):
            pid=W.DWORD();user.GetWindowThreadProcessId(window,C.byref(pid))
            if pid.value==proc.pid and user.IsWindowVisible(window):
                caption=C.create_unicode_buffer(128);user.GetWindowTextW(window,caption,128)
                if caption.value=='Ramos Scaling test':found.append(window)
            return True
        user.EnumWindows(cb,0)
        return found[0] if found else None
    def text(control):
        raw=C.create_unicode_buffer(256)
        user.SendMessageW(control,0xd,len(raw),C.addressof(raw))
        return raw.value
    def geometry(window,number,dpi,x,y,w,h):
        child=user.GetDlgItem(window,number);assert child
        bounds=W.RECT();origin=W.POINT()
        assert user.GetWindowRect(child,C.byref(bounds))
        assert user.ClientToScreen(window,C.byref(origin))
        px=lambda n:(n*dpi+48)//96
        actual=[bounds.left-origin.x,bounds.top-origin.y,bounds.right-origin.x,bounds.bottom-origin.y]
        expected=[px(x),px(y),px(x+w),px(y+h)]
        assert actual==expected,(number,actual,expected)
    def check_scene(window,round):
        scaled=round%2==0
        context=user.GetWindowDpiAwarenessContext(window)
        assert user.GetAwarenessFromDpiAwarenessContext(context)==(2 if scaled else 0)
        if scaled:assert user.AreDpiAwarenessContextsEqual(context,W.HANDLE(-4))
        dpi=user.GetDpiForWindow(window)
        assert 96<=dpi<=768
        assert text(user.GetDlgItem(window,1))==f'round={round} dpi={dpi if scaled else 96}'
        if not scaled:return dpi
        geometry(window,3,dpi,10,80,100,40)
        geometry(window,4,dpi,120,80,100,40)
        bounds=W.RECT();assert user.GetClientRect(window,C.byref(bounds))
        assert (bounds.right,bounds.bottom)==((320*dpi+48)//96,(240*dpi+48)//96), [bounds.right,bounds.bottom]
        font=user.SendMessageW(user.GetDlgItem(window,1),0x31,0,0)
        assert font
        raw=C.create_string_buffer(92)
        assert gdi.GetObjectW(W.HANDLE(font),92,raw)==92
        height=C.c_int32.from_buffer(raw).value
        assert height==-((12*dpi+48)//96),(height,dpi)
        for number,color in [(3,0xdc5028),(4,0x283cdc)]:
            child=user.GetDlgItem(window,number)
            def pixel():
                dc=user.GetDC(child);assert dc
                try:return gdi.GetPixel(dc,(20*dpi+48)//96,(15*dpi+48)//96)
                finally:assert user.ReleaseDC(child,dc)
            wait(lambda:pixel()==color,f'native pixel {number}')
        return dpi
    def resources():
        count=W.DWORD();assert kernel.GetProcessHandleCount(handle,C.byref(count))
        return {'handles':count.value,'gdi':user.GetGuiResources(handle,0),'user':user.GetGuiResources(handle,1)}
    def bounded(before,after):
        # Native libraries can lazily cache a few process-owned objects, but
        # 200 frames/20 complete windows must not cause proportional growth.
        assert before['gdi']>0 and before['user']>0,before
        for key in before:assert after[key]<=before[key]+4,(key,before,after)
    try:
        proc=subprocess.Popen([binary],stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        output=Output(proc)
        assert [output.line() for _ in range(3)]==['-9','-22','-16']
        hwnd=wait(find,'scaled window')
        wait(lambda:text(user.GetDlgItem(hwnd,1)).startswith('round=0'),'complete scene')
        wait(lambda:user.GetDlgItem(hwnd,6),'last control')
        dpi=check_scene(hwnd,0)
        result.update(initial_dpi=dpi,initial_awareness='per-monitor-v2',geometry=True,font=True,pixels=True)
        # This is only rejection of a bogus notification, never transition proof.
        bogus=192 if dpi!=192 else 96
        user.SendMessageW(hwnd,0x2e0,bogus|(bogus<<16),0)
        assert text(user.GetDlgItem(hwnd,1))==f'round=0 dpi={dpi}'
        result['synthetic_notification_ignored']=True
        handle=kernel.OpenProcess(0x400,False,proc.pid);assert handle
        baseline=None
        for i in range(200):
            assert user.PostMessageW(user.GetDlgItem(hwnd,5),0xf5,0,0)
            parts=output.line().split()
            assert parts[:2]==['step',str(i)],parts
            assert int(parts[2])<262144,parts
            if i==9:baseline=resources()
        after=resources();bounded(baseline,after)
        result.update(churn_steps=200,churn_bytes=200*1048576,resources_warm=baseline,resources_after_churn=after)
        cycle_baseline=None
        for round in range(1,21):
            assert user.PostMessageW(user.GetDlgItem(hwnd,6),0xf5,0,0)
            assert output.line()=='-9'
            def scene():
                window=find()
                return window if window and text(user.GetDlgItem(window,1)).startswith(f'round={round} ') else None
            hwnd=wait(scene,'reopened scene')
            check_scene(hwnd,round)
            if round==4:cycle_baseline=resources()
        after=resources();bounded(cycle_baseline,after)
        result.update(reopen_cycles=20,thread_context_restored=True,resources_after_reopen=after)
        assert user.PostMessageW(hwnd,0x10,0,0)
        assert [output.line(),output.line()]==['-9','true']
        assert proc.wait(timeout=10)==0
        assert proc.stderr.read()==b''
        assert not user.IsWindow(hwnd)
        result['closed']=True
    except Exception as exc:
        result['error']=repr(exc)
        raise
    finally:
        if handle:kernel.CloseHandle(handle)
        if proc is not None:
            if proc.poll() is None:proc.kill()
            proc.wait(timeout=5);proc.stdout.close();proc.stderr.close()
        assert user.SetThreadDpiAwarenessContext(old)
        assert user.AreDpiAwarenessContextsEqual(user.GetThreadDpiAwarenessContext(),old)
        Path(report).write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')

if __name__=='__main__':main()
