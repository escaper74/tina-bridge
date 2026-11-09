"""Keep the explicitly operated TINA process on the secondary monitor."""
import ctypes as C
from ctypes import wintypes as W
import os
from win32_probe import U, window, windows
import settings


class MonitorInfo(C.Structure):
    _fields_=[('size',W.DWORD),('monitor',W.RECT),('work',W.RECT),('flags',W.DWORD),('device',W.WCHAR*32)]


MONITOR_CB=C.WINFUNCTYPE(W.BOOL,W.HANDLE,W.HDC,C.POINTER(W.RECT),W.LPARAM)
U.GetMonitorInfoW.argtypes=[W.HANDLE,C.POINTER(MonitorInfo)]
U.EnumDisplayMonitors.argtypes=[W.HDC,C.POINTER(W.RECT),MONITOR_CB,W.LPARAM]
U.SetWindowPos.argtypes=[W.HWND,W.HWND,C.c_int,C.c_int,C.c_int,C.c_int,W.UINT]
U.SetWindowPos.restype=W.BOOL
U.ShowWindow.argtypes=[W.HWND,C.c_int]


def monitors():
    result=[]
    @MONITOR_CB
    def callback(handle,dc,rect,param):
        info=MonitorInfo()
        info.size=C.sizeof(info)
        if U.GetMonitorInfoW(handle,C.byref(info)):
            convert=lambda r:[r.left,r.top,r.right,r.bottom]
            result.append({'device':info.device,'primary':bool(info.flags&1),
                           'monitor':convert(info.monitor),'work':convert(info.work)})
        return True
    U.EnumDisplayMonitors(None,None,callback,0)
    return result


def place_windows(pid, preference=None, restore=False):
    preference=preference or settings.monitor()
    choices=monitors()
    targets=[m for m in choices if (not m['primary'] if preference=='secondary'
                                  else m['device'].casefold()==preference.casefold())]
    if preference=='unchanged' or not targets:
        return {'moved':[],'target':None,'note':'Placement unchanged: no requested monitor'}
    target=targets[0]
    if restore:
        for w in windows(pid):
            if w['cls']=='TApplication' and w['minimized']:
                U.ShowWindow(w['hwnd'],4)  # restore owner/owned windows, no activation request
    left,top,right,bottom=target['work']
    moved=[]
    for w in windows(pid):
        if not w['visible'] or w['cls']=='TApplication' or w['minimized']:
            continue
        x,y,xr,yb=w['rect']
        if xr-x<=0 or yb-y<=0:
            continue
        if left<=(x+xr)/2<right and top<=(y+yb)/2<bottom:
            continue
        if int(w['style'],16)&0x01000000:
            U.ShowWindow(w['hwnd'],4)  # SW_SHOWNOACTIVATE
        width=min(max(xr-x,100),right-left-24)
        height=min(max(yb-y,60),bottom-top-24)
        nx=left+(right-left-width)//2
        ny=top+(bottom-top-height)//2
        if not U.SetWindowPos(w['hwnd'],None,nx,ny,width,height,0x4|0x10):
            raise OSError(C.get_last_error(),'Could not position TINA window on requested monitor')
        moved.append({'class':w['cls'],'title':w['title'],'before':w['rect'],
                      'after':window(w['hwnd'])['rect']})
    return {'target':target,'moved':moved}
