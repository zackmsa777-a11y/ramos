#!/usr/bin/env python3
"""Compare the scaling demo's actual Win32 canvas with independent GDI drawing.

Observe before forcing repaint. No DPI changes, fake messages, private memory
writes or application implementation. The same process/window stays open.
Run: python tools/canvas_capture.py --pid PID --output DIRECTORY
Keep the whole demo unobscured. Python is diagnostic tooling only.
"""
import argparse
import ctypes as C
from ctypes import wintypes as W
import hashlib
import json
from pathlib import Path
import struct


def capture(pid, output):
    user=C.WinDLL('user32',use_last_error=True)
    gdi=C.WinDLL('gdi32',use_last_error=True)
    signatures=[
        (user,'EnumWindows',W.BOOL,[C.c_void_p,W.LPARAM]),
        (user,'GetWindowThreadProcessId',W.DWORD,[W.HWND,C.POINTER(W.DWORD)]),
        (user,'GetWindowTextW',C.c_int,[W.HWND,W.LPWSTR,C.c_int]),
        (user,'IsWindowVisible',W.BOOL,[W.HWND]),
        (user,'IsIconic',W.BOOL,[W.HWND]),
        (user,'GetDlgItem',W.HWND,[W.HWND,C.c_int]),
        (user,'GetClientRect',W.BOOL,[W.HWND,C.POINTER(W.RECT)]),
        (user,'GetDpiForWindow',W.UINT,[W.HWND]),
        (user,'SetThreadDpiAwarenessContext',W.HANDLE,[W.HANDLE]),
        (user,'GetDC',W.HDC,[W.HWND]),
        (user,'ReleaseDC',C.c_int,[W.HWND,W.HDC]),
        (user,'RedrawWindow',W.BOOL,[W.HWND,C.c_void_p,C.c_void_p,W.UINT]),
        (user,'FillRect',C.c_int,[W.HDC,C.POINTER(W.RECT),W.HBRUSH]),
        (gdi,'CreateCompatibleDC',W.HDC,[W.HDC]),
        (gdi,'DeleteDC',W.BOOL,[W.HDC]),
        (gdi,'CreateCompatibleBitmap',W.HBITMAP,[W.HDC,C.c_int,C.c_int]),
        (gdi,'SelectObject',W.HANDLE,[W.HDC,W.HANDLE]),
        (gdi,'DeleteObject',W.BOOL,[W.HANDLE]),
        (gdi,'GetStockObject',W.HANDLE,[C.c_int]),
        (gdi,'SetDCPenColor',W.DWORD,[W.HDC,W.DWORD]),
        (gdi,'SetDCBrushColor',W.DWORD,[W.HDC,W.DWORD]),
        (gdi,'SetMapMode',C.c_int,[W.HDC,C.c_int]),
        (gdi,'SetWindowExtEx',W.BOOL,[W.HDC,C.c_int,C.c_int,C.c_void_p]),
        (gdi,'SetViewportExtEx',W.BOOL,[W.HDC,C.c_int,C.c_int,C.c_void_p]),
        (gdi,'Rectangle',W.BOOL,[W.HDC,C.c_int,C.c_int,C.c_int,C.c_int]),
        (gdi,'Ellipse',W.BOOL,[W.HDC,C.c_int,C.c_int,C.c_int,C.c_int]),
        (gdi,'MoveToEx',W.BOOL,[W.HDC,C.c_int,C.c_int,C.c_void_p]),
        (gdi,'LineTo',W.BOOL,[W.HDC,C.c_int,C.c_int]),
        (gdi,'BitBlt',W.BOOL,[W.HDC,C.c_int,C.c_int,C.c_int,C.c_int,W.HDC,C.c_int,C.c_int,W.DWORD]),
        (gdi,'GetDIBits',C.c_int,[W.HDC,W.HBITMAP,W.UINT,W.UINT,C.c_void_p,C.c_void_p,W.UINT]),
    ]
    for dll,name,result,args in signatures:
        fn=getattr(dll,name);fn.restype=result;fn.argtypes=args
    previous=user.SetThreadDpiAwarenessContext(W.HANDLE(-4))
    assert previous, 'Per-monitor-v2 diagnostic context unavailable'
    output=Path(output);output.mkdir(parents=True,exist_ok=True)
    report={'pid':pid,'scope':'Native GDI pixels before/after full redraw. No DPI transition is generated.'}
    def find():
        found=[]
        @C.WINFUNCTYPE(W.BOOL,W.HWND,W.LPARAM)
        def callback(window,unused):
            owner=W.DWORD();user.GetWindowThreadProcessId(window,C.byref(owner))
            title=C.create_unicode_buffer(128);user.GetWindowTextW(window,title,128)
            if owner.value==pid and title.value=='Ramos DPI demo' and user.IsWindowVisible(window):found.append(window)
            return True
        user.EnumWindows(callback,0)
        assert len(found)==1,('Expected one visible Ramos DPI demo for PID',pid,found)
        assert not user.IsIconic(found[0]),'Demo is minimized'
        return found[0]
    def bitmap(canvas,width,height,reference=False,dpi=96):
        screen=user.GetDC(canvas);assert screen
        dc=None;image=None;old=None
        try:
            dc=gdi.CreateCompatibleDC(screen);assert dc
            image=gdi.CreateCompatibleBitmap(screen,width,height);assert image
            old=gdi.SelectObject(dc,image);assert old
            if reference:
                brush=gdi.GetStockObject(18);pen=gdi.GetStockObject(19)
                assert brush and pen
                assert gdi.SelectObject(dc,brush) and gdi.SelectObject(dc,pen)
                assert gdi.SetDCBrushColor(dc,0xfaf0eb)!=0xffffffff
                bounds=W.RECT(0,0,width,height)
                assert user.FillRect(dc,C.byref(bounds),brush)
                assert gdi.SetMapMode(dc,8)
                assert gdi.SetWindowExtEx(dc,96,96,None)
                assert gdi.SetViewportExtEx(dc,dpi,dpi,None)
                assert gdi.SelectObject(dc,gdi.GetStockObject(5))
                assert gdi.SetDCPenColor(dc,0xdc5028)!=0xffffffff
                assert gdi.Rectangle(dc,16,16,128,96)
                assert gdi.SelectObject(dc,brush)
                assert gdi.SetDCBrushColor(dc,0x283cdc)!=0xffffffff
                assert gdi.SetDCPenColor(dc,0x283cdc)!=0xffffffff
                assert gdi.Ellipse(dc,188,20,261,93)
                assert gdi.SetDCPenColor(dc,0x326414)!=0xffffffff
                assert gdi.MoveToEx(dc,304,20,None)
                assert gdi.LineTo(dc,448,92)
                assert gdi.SetMapMode(dc,1)
            else:
                assert gdi.BitBlt(dc,0,0,width,height,screen,0,0,0xcc0020)
            # GetDIBits requires the bitmap deselected from its DC.
            assert gdi.SelectObject(dc,old);old=None
            header=struct.pack('<IiiHHIIiiII',40,width,-height,1,32,0,width*height*4,0,0,0,0)
            info=C.create_string_buffer(header+b'\0'*12)
            raw=C.create_string_buffer(width*height*4)
            assert gdi.GetDIBits(dc,image,0,height,raw,info,0)==height
            return raw.raw
        finally:
            if old:gdi.SelectObject(dc,old)
            if image:assert gdi.DeleteObject(image)
            if dc:assert gdi.DeleteDC(dc)
            assert user.ReleaseDC(canvas,screen)
    try:
        hwnd=find();canvas=user.GetDlgItem(hwnd,4);assert canvas
        dpi=user.GetDpiForWindow(hwnd);assert 96<=dpi<=768,dpi
        bounds=W.RECT();assert user.GetClientRect(canvas,C.byref(bounds))
        width,height=bounds.right,bounds.bottom
        assert (width,height)==((480*dpi+48)//96,(112*dpi+48)//96),(width,height,dpi)
        report.update(window_handle=int(hwnd),dpi=dpi,width=width,height=height)
        before=bitmap(canvas,width,height)
        reference=bitmap(canvas,width,height,reference=True,dpi=dpi)
        assert user.RedrawWindow(canvas,None,None,0x105)
        after=bitmap(canvas,width,height)
        for name,data in [('before',before),('reference',reference),('after-redraw',after)]:
            header=struct.pack('<IiiHHIIiiII',40,width,-height,1,32,0,len(data),0,0,0,0)
            bmp=b'BM'+struct.pack('<IHHI',54+len(data),0,0,54)+header+data
            (output/(name+'.bmp')).write_bytes(bmp)
        def difference(a,b):
            # The fourth byte is undefined for a 32-bit BI_RGB bitmap.
            return sum(a[i:i+3]!=b[i:i+3] for i in range(0,len(a),4))
        report.update(before_different_pixels=difference(before,reference),
                      after_redraw_different_pixels=difference(after,reference),
                      changed_by_redraw_pixels=difference(before,after),
                      before_sha256=hashlib.sha256(before).hexdigest(),
                      after_sha256=hashlib.sha256(after).hexdigest())
    except Exception as exc:
        report['error']=repr(exc)
        raise
    finally:
        assert user.SetThreadDpiAwarenessContext(previous)
        (output/'capture.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    return report

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--pid',required=True,type=int)
    parser.add_argument('--output',required=True,type=Path)
    args=parser.parse_args()
    print(json.dumps(capture(args.pid,args.output),indent=2))
