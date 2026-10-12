#!/usr/bin/env python3
"""Native Windows canvas acceptance. Python drives/test pixels; app is Ramos."""
import ctypes as C
from ctypes import wintypes as W
import json
from pathlib import Path
import subprocess
import sys
import time


def main():
    binary, report = sys.argv[1:3]
    plot = len(sys.argv)>3 and sys.argv[3]=="plot"
    user=C.WinDLL('user32',use_last_error=True)
    gdi=C.WinDLL('gdi32',use_last_error=True)
    kernel=C.WinDLL('kernel32',use_last_error=True)
    for name,result,args in [
        ('EnumWindows',W.BOOL,[C.c_void_p,W.LPARAM]),
        ('GetWindowThreadProcessId',W.DWORD,[W.HWND,C.POINTER(W.DWORD)]),
        ('GetWindowTextW',C.c_int,[W.HWND,W.LPWSTR,C.c_int]),
        ('IsWindowVisible',W.BOOL,[W.HWND]),
        ('IsWindow',W.BOOL,[W.HWND]),
        ('GetDlgItem',W.HWND,[W.HWND,C.c_int]),
        ('PostMessageW',W.BOOL,[W.HWND,W.UINT,W.WPARAM,W.LPARAM]),
        ('GetDC',W.HDC,[W.HWND]),
        ('GetClientRect',W.BOOL,[W.HWND,C.POINTER(W.RECT)]),
        ('ReleaseDC',C.c_int,[W.HWND,W.HDC]),
        ('SetWindowPos',W.BOOL,[W.HWND,W.HWND,C.c_int,C.c_int,C.c_int,C.c_int,W.UINT]),
        ('GetGuiResources',W.DWORD,[W.HANDLE,W.DWORD]),
        ('RedrawWindow',W.BOOL,[W.HWND,C.c_void_p,C.c_void_p,W.UINT]),
    ]:
        fn=getattr(user,name);fn.restype=result;fn.argtypes=args
    gdi.GetPixel.restype=W.DWORD;gdi.GetPixel.argtypes=[W.HDC,C.c_int,C.c_int]
    kernel.OpenProcess.restype=W.HANDLE;kernel.OpenProcess.argtypes=[W.DWORD,W.BOOL,W.DWORD]
    kernel.CloseHandle.restype=W.BOOL;kernel.CloseHandle.argtypes=[W.HANDLE]
    proc=subprocess.Popen([binary],stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    result={};handle=None
    def wait(check,label):
        end=time.monotonic()+30
        while time.monotonic()<end:
            value=check()
            if value:return value
            if proc.poll() is not None:
                out,err=proc.communicate()
                raise AssertionError((label,proc.returncode,out,err))
            time.sleep(.02)
        raise AssertionError('Timeout: '+label)
    def find():
        found=[]
        @C.WINFUNCTYPE(W.BOOL,W.HWND,W.LPARAM)
        def cb(hwnd,unused):
            pid=W.DWORD();user.GetWindowThreadProcessId(hwnd,C.byref(pid))
            caption=C.create_unicode_buffer(256);user.GetWindowTextW(hwnd,caption,256)
            if pid.value==proc.pid and user.IsWindowVisible(hwnd) and caption.value==('Ramos Plot' if plot else 'Ramos Canvas test'):found.append(hwnd)
            return True
        user.EnumWindows(cb,0)
        return found[0] if found else None
    def text(hwnd):
        buf=C.create_unicode_buffer(256);user.GetWindowTextW(hwnd,buf,256);return buf.value
    def pixel(hwnd,x,y):
        dc=user.GetDC(hwnd)
        assert dc
        try:return gdi.GetPixel(dc,x,y)
        finally:assert user.ReleaseDC(hwnd,dc)
    def click(number):assert user.PostMessageW(user.GetDlgItem(hwnd,number),0xf5,0,0)
    try:
        hwnd=wait(find,'canvas window')
        status=wait(lambda:user.GetDlgItem(hwnd,3),'status label')
        canvas=wait(lambda:user.GetDlgItem(hwnd,1),'canvas control')
        if plot:
            def blue(x,y):
                color=pixel(canvas,x,y)
                return (color>>16)-(color&255)>50
            wait(lambda:any(blue(320,y) for y in range(280,286)),'initial parabola')
            click(2)
            wait(lambda:any(blue(320,y) for y in range(193,198)),'button changes curve')
            assert user.SetWindowPos(hwnd,None,0,0,830,640,0x16)
            bounds=W.RECT()
            assert user.GetClientRect(hwnd,C.byref(bounds))
            x=bounds.right//2; y=20+(bounds.bottom-90)//2
            wait(lambda:any(blue(x,row) for row in range(y-2,y+3)),'resize reflows plot')
            assert user.PostMessageW(hwnd,0x10,0,0)
            out,err=proc.communicate(timeout=5)
            assert proc.returncode==0 and out==b'',(proc.returncode,out,err)
            assert not user.IsWindow(hwnd)
            result.update(closed=True,curve_button=True,resize=True)
            return
        wait(lambda:text(status)=='Ready','validation and GC before paint')
        wait(lambda:pixel(canvas,15,20)==0x0000ff,'red snapshot')
        assert pixel(canvas,90,30)==0xff0000,'blue disk'
        assert pixel(canvas,155,30)==0xffffff,'outlined box interior'
        assert pixel(canvas,200,20)==0,'single pixel'
        assert pixel(canvas,20,80)!=0xffffff,'line stroke'
        assert any(pixel(canvas,x,15)!=0xffffff for x in (139,140,141)),'box stroke'
        assert any(pixel(canvas,x,75)!=0xffffff for x in range(99,104)),'circle stroke'
        neighbor=user.GetDlgItem(hwnd,6)
        wait(lambda:pixel(neighbor,5,15)==0xff0000,'neighbor panel painted')
        assert user.RedrawWindow(canvas,None,None,0x105)
        assert pixel(neighbor,5,15)==0xff0000,'forced canvas repaint clips negative shape'
        result['snapshot_gc']=True
        assert user.SetWindowPos(hwnd,None,0,0,530,280,0x16)
        wait(lambda:pixel(canvas,260,20)==0x0000ff,'resize reveals retained frame')
        result['resize']=True
        assert user.RedrawWindow(canvas,None,None,0x105) # invalidate, erase, update now
        wait(lambda:pixel(canvas,15,20)==0x0000ff,'OS repaint after source mutation')
        click(2)
        wait(lambda:text(status)=='Replaced','replacement')
        wait(lambda:pixel(canvas,15,20)==0x00ff00,'green private snapshot')
        assert user.RedrawWindow(canvas,None,None,0x105)
        wait(lambda:pixel(canvas,260,20)==0x00ff00,'replacement repaint')
        click(4)
        wait(lambda:text(status)=='Empty','empty frame')
        wait(lambda:pixel(canvas,15,20)==0xffffff,'default white empty scene')
        handle=kernel.OpenProcess(0x400,False,proc.pid)
        assert handle
        before=user.GetGuiResources(handle,0)
        click(5)
        wait(lambda:text(status)=='Stress passed','400 maximum-size managed snapshots')
        wait(lambda:pixel(canvas,15,2)==0,'stress scene')
        after=user.GetGuiResources(handle,0)
        assert before>0 and after<=before+2,(before,after)
        result.update(gc_stress=True,gdi_before=before,gdi_after=after)
        assert user.PostMessageW(hwnd,0x10,0,0)
        out,err=proc.communicate(timeout=10)
        assert proc.returncode==0,(proc.returncode,out,err)
        assert not user.IsWindow(hwnd)
        result.update(closed=True,stdout=out.decode(),stderr=err.decode())
    except Exception as exc:
        result['error']=str(exc)
        raise
    finally:
        if handle:kernel.CloseHandle(handle)
        if proc.poll() is None:proc.kill();proc.communicate()
        Path(report).write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')

if __name__=='__main__':main()
