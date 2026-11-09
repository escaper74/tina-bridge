"""Read-only inspection of a selected TINA process. No input injection."""
import argparse
import ctypes as C
from ctypes import wintypes as W
import json

U = C.WinDLL('user32', use_last_error=True)
CB = C.WINFUNCTYPE(W.BOOL, W.HWND, W.LPARAM)
U.EnumWindows.argtypes = [CB, W.LPARAM]
U.EnumChildWindows.argtypes = [W.HWND, CB, W.LPARAM]
U.GetWindowThreadProcessId.argtypes = [W.HWND, C.POINTER(W.DWORD)]
U.GetWindowTextW.argtypes = [W.HWND, W.LPWSTR, C.c_int]
U.GetClassNameW.argtypes = [W.HWND, W.LPWSTR, C.c_int]
U.GetWindowRect.argtypes = [W.HWND, C.POINTER(W.RECT)]
U.GetWindowLongW.argtypes = [W.HWND, C.c_int]
U.GetWindowLongW.restype = W.LONG
U.GetWindow.argtypes = [W.HWND, W.UINT]
U.GetWindow.restype = W.HWND
U.GetParent.argtypes = [W.HWND]
U.GetParent.restype = W.HWND
U.IsWindowVisible.argtypes = [W.HWND]
U.IsWindowEnabled.argtypes = [W.HWND]
U.IsIconic.argtypes = [W.HWND]
U.GetDlgCtrlID.argtypes = [W.HWND]
U.GetMenu.argtypes = [W.HWND]
U.GetMenu.restype = W.HMENU
U.GetMenuItemCount.argtypes = [W.HMENU]
U.GetSubMenu.argtypes = [W.HMENU, C.c_int]
U.GetSubMenu.restype = W.HMENU
U.GetMenuItemID.argtypes = [W.HMENU, C.c_int]
U.GetMenuItemID.restype = W.UINT
U.GetMenuStringW.argtypes = [W.HMENU, W.UINT, W.LPWSTR, C.c_int, W.UINT]
U.GetMenuState.argtypes = [W.HMENU, W.UINT, W.UINT]
U.GetMenuState.restype = W.UINT


def text(hwnd):
    b = C.create_unicode_buffer(4096)
    U.GetWindowTextW(hwnd, b, len(b))
    return b.value


def window(hwnd):
    p = W.DWORD()
    U.GetWindowThreadProcessId(hwnd, C.byref(p))
    cl = C.create_unicode_buffer(256)
    U.GetClassNameW(hwnd, cl, len(cl))
    r = W.RECT()
    U.GetWindowRect(hwnd, C.byref(r))
    return dict(hwnd=int(hwnd), pid=p.value, title=text(hwnd), cls=cl.value, control_id=U.GetDlgCtrlID(hwnd),
                visible=bool(U.IsWindowVisible(hwnd)), enabled=bool(U.IsWindowEnabled(hwnd)),
                minimized=bool(U.IsIconic(hwnd)), owner=int(U.GetWindow(hwnd, 4) or 0),
                parent=int(U.GetParent(hwnd) or 0),
                style=hex(U.GetWindowLongW(hwnd, -16) & 0xffffffff),
                exstyle=hex(U.GetWindowLongW(hwnd, -20) & 0xffffffff),
                rect=[r.left, r.top, r.right, r.bottom])


def windows(pid):
    found = []
    @CB
    def callback(hwnd, _):
        w = window(hwnd)
        if w['pid'] == pid:
            found.append(w)
        return True
    U.EnumWindows(callback, 0)
    return found


def children(hwnd):
    found = []
    @CB
    def callback(child, _):
        found.append(window(child))
        return True
    U.EnumChildWindows(hwnd, callback, 0)
    return found


def menu_items(menu, depth=0):
    if not menu or depth > 5:
        return []
    result = []
    for i in range(U.GetMenuItemCount(menu)):
        b = C.create_unicode_buffer(1024)
        U.GetMenuStringW(menu, i, b, len(b), 0x400)
        sub = U.GetSubMenu(menu, i)
        result.append(dict(position=i, text=b.value, command=U.GetMenuItemID(menu, i),
                           flags=U.GetMenuState(menu, i, 0x400),
                           children=menu_items(sub, depth+1)))
    return result


def inspect(pid, with_children=False, with_menus=False):
    result = windows(pid)
    for w in result:
        if with_children and w['visible']:
            w['children'] = children(w['hwnd'])
        if with_menus:
            w['menu'] = menu_items(U.GetMenu(w['hwnd']))
    return result


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--pid', type=int, required=True)
    ap.add_argument('--children', action='store_true')
    ap.add_argument('--menus', action='store_true')
    ap.add_argument('--output')
    args = ap.parse_args()
    value = json.dumps(inspect(args.pid, args.children, args.menus), ensure_ascii=False, indent=2)
    if args.output:
        from pathlib import Path
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
        Path(args.output).write_text(value, encoding='utf-8')
    print(value)
