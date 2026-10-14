"""Independent WinHTTP timing diagnosis against the owned loopback fixture."""
import ctypes as C
from ctypes import wintypes as W
import time
from urllib.parse import urlsplit

def probe(url,timeout):
    w=C.WinDLL('winhttp',use_last_error=True)
    specs=[('WinHttpOpen',W.HANDLE,[W.LPCWSTR,W.DWORD,W.LPCWSTR,W.LPCWSTR,W.DWORD]),
           ('WinHttpConnect',W.HANDLE,[W.HANDLE,W.LPCWSTR,W.WORD,W.DWORD]),
           ('WinHttpOpenRequest',W.HANDLE,[W.HANDLE,W.LPCWSTR,W.LPCWSTR,W.LPCWSTR,W.LPCWSTR,C.c_void_p,W.DWORD]),
           ('WinHttpSetTimeouts',W.BOOL,[W.HANDLE,C.c_int,C.c_int,C.c_int,C.c_int]),
           ('WinHttpSetOption',W.BOOL,[W.HANDLE,W.DWORD,C.c_void_p,W.DWORD]),
           ('WinHttpQueryOption',W.BOOL,[W.HANDLE,W.DWORD,C.c_void_p,C.POINTER(W.DWORD)]),
           ('WinHttpSendRequest',W.BOOL,[W.HANDLE,W.LPCWSTR,W.DWORD,C.c_void_p,W.DWORD,W.DWORD,C.c_size_t]),
           ('WinHttpReceiveResponse',W.BOOL,[W.HANDLE,C.c_void_p]),
           ('WinHttpCloseHandle',W.BOOL,[W.HANDLE])]
    for name,result,args in specs:
        f=getattr(w,name);f.restype=result;f.argtypes=args
    handles=[];parts=urlsplit(url)
    try:
        session=w.WinHttpOpen('Ramos test diagnostic',1,None,None,0);assert session;handles.append(session)
        assert w.WinHttpSetTimeouts(session,timeout,timeout,timeout,timeout)
        connection=w.WinHttpConnect(session,parts.hostname,parts.port,0);assert connection;handles.append(connection)
        request=w.WinHttpOpenRequest(connection,'GET',parts.path,None,None,None,0);assert request;handles.append(request)
        assert w.WinHttpSetTimeouts(request,timeout,timeout,timeout,timeout)
        val=W.DWORD(timeout);assert w.WinHttpSetOption(request,7,C.byref(val),4)
        options={}
        for option in [2,3,5,6,7]:
            val=W.DWORD();size=W.DWORD(4)
            assert w.WinHttpQueryOption(request,option,C.byref(val),C.byref(size))
            options[option]=val.value
        start=time.monotonic();assert w.WinHttpSendRequest(request,None,0,None,0,0,0)
        ok=w.WinHttpReceiveResponse(request,None);error=C.get_last_error()
        return {'requested_ms':timeout,'options':options,'received':bool(ok),'error':error,'elapsed_ms':round((time.monotonic()-start)*1000)}
    finally:
        for handle in reversed(handles):assert w.WinHttpCloseHandle(handle)
