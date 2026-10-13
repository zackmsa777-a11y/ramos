"""Test-only real XSETTINGS manager; GTK observes native scale-factor changes."""
import ctypes as C
import struct

class Settings:
    def __init__(self, desktop):
        self.desktop = desktop
        x = desktop.x
        for name,result,args in [
            ('XDefaultRootWindow',C.c_ulong,[C.c_void_p]),
            ('XCreateSimpleWindow',C.c_ulong,[C.c_void_p,C.c_ulong,C.c_int,C.c_int,C.c_uint,C.c_uint,C.c_uint,C.c_ulong,C.c_ulong]),
            ('XSetSelectionOwner',C.c_int,[C.c_void_p,C.c_ulong,C.c_ulong,C.c_ulong]),
            ('XChangeProperty',C.c_int,[C.c_void_p,C.c_ulong,C.c_ulong,C.c_ulong,C.c_int,C.c_int,C.c_void_p,C.c_int]),
            ('XDestroyWindow',C.c_int,[C.c_void_p,C.c_ulong]),
        ]:
            fn=getattr(x,name);fn.restype=result;fn.argtypes=args
        self.window=x.XCreateSimpleWindow(desktop.display,x.XDefaultRootWindow(desktop.display),0,0,1,1,0,0,0)
        self.selection=x.XInternAtom(desktop.display,b'_XSETTINGS_S0',0)
        self.property=x.XInternAtom(desktop.display,b'_XSETTINGS_SETTINGS',0)
        self.serial=0
        x.XSetSelectionOwner(desktop.display,self.selection,self.window,0)
        self.set_scale(1)

    def set_scale(self, scale):
        self.serial+=1
        name=b'Gdk/WindowScalingFactor'
        # GDK uses the Gdk/WindowScalingFactor setting, not a forged widget notify.
        data=struct.pack('<B3xII',0,self.serial,1)+struct.pack('<BBH',0,0,len(name))+name
        data+=b'\0'*(-len(data)%4)+struct.pack('<Ii',self.serial,scale)
        raw=C.create_string_buffer(data)
        x=self.desktop.x
        x.XChangeProperty(self.desktop.display,self.window,self.property,self.property,8,0,raw,len(data))
        x.XFlush(self.desktop.display)

    def close(self):
        self.desktop.x.XDestroyWindow(self.desktop.display,self.window)
        self.desktop.x.XFlush(self.desktop.display)
