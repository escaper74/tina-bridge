"""Small, process-scoped Win32 adapter for the installed legacy TINA-TI UI.

No keyboard/mouse injection or global clipboard. Menu commands are resolved from
the running process; controls and screenshots remain scoped to its windows.
"""
import argparse
import ctypes as C
from ctypes import wintypes as W
import json
from pathlib import Path
import time
from win32_probe import U, windows, children, window, menu_items

K = C.WinDLL('kernel32', use_last_error=True)
K.OpenProcess.argtypes = [W.DWORD, W.BOOL, W.DWORD]
K.OpenProcess.restype = W.HANDLE
K.QueryFullProcessImageNameW.argtypes = [W.HANDLE, W.DWORD, W.LPWSTR, C.POINTER(W.DWORD)]
K.CloseHandle.argtypes = [W.HANDLE]
U.PostMessageW.argtypes = [W.HWND, W.UINT, W.WPARAM, W.LPARAM]
U.PostMessageW.restype = W.BOOL
U.SendMessageTimeoutW.argtypes = [W.HWND, W.UINT, W.WPARAM, W.LPARAM, W.UINT, W.UINT, C.POINTER(C.c_size_t)]
U.SendMessageTimeoutW.restype = W.LPARAM


def send(hwnd, msg, wp=0, lp=0):
    result = C.c_size_t()
    if not U.SendMessageTimeoutW(hwnd, msg, wp, lp, 0x2, 3000, C.byref(result)):
        raise TimeoutError(f'Window message failed or timed out: {hwnd}/{msg}')
    return result.value


def process_path(pid):
    p = K.OpenProcess(0x1000, False, pid)
    if not p:
        raise OSError(C.get_last_error(), 'Cannot query TINA process')
    try:
        b = C.create_unicode_buffer(32768)
        n = W.DWORD(len(b))
        if not K.QueryFullProcessImageNameW(p, 0, b, C.byref(n)):
            raise OSError(C.get_last_error(), 'Cannot read process executable')
        return Path(b.value)
    finally:
        K.CloseHandle(p)


def validate(pid, exe, hwnd=None):
    actual = process_path(pid)
    if str(actual).casefold() != str(Path(exe).resolve()).casefold():
        raise RuntimeError(f'Process path mismatch: {actual}')
    if hwnd and window(hwnd)['pid'] != pid:
        raise RuntimeError('Target window no longer belongs to this TINA process')


def read_text(hwnd):
    b = C.create_unicode_buffer(8192)
    send(hwnd, 0x000d, len(b), C.addressof(b))
    return b.value


def state(pid):
    out = []
    for w in windows(pid):
        if not w['visible']:
            continue
        w['children'] = []
        for c in children(w['hwnd']):
            if not c['visible']:
                continue
            try:
                c['text'] = read_text(c['hwnd'])
                if c['cls'] in ('TGroupButton', 'TCheckBox', 'Button'):
                    c['checked'] = send(c['hwnd'], 0x00f0)
            except TimeoutError:
                c['text_error'] = 'timeout'
            w['children'].append(c)
        w['menu'] = menu_items(U.GetMenu(w['hwnd']))
        out.append(w)
    return out


def flatten_menu(items, prefix=()):
    result = []
    for item in items:
        path = prefix + (item['text'],)
        if item['children']:
            result.extend(flatten_menu(item['children'], path))
        else:
            result.append({**item, 'path': list(path)})
    return result


def command(hwnd, command_id):
    entries = flatten_menu(menu_items(U.GetMenu(hwnd)))
    matches = [m for m in entries if m['command'] == command_id]
    if len(matches) != 1 or matches[0]['flags'] & 0x803:
        raise RuntimeError('Command absent, ambiguous, a separator, or disabled')
    if not U.IsWindowEnabled(hwnd):
        raise RuntimeError('Window is disabled, likely blocked by a modal')
    if not U.PostMessageW(hwnd, 0x111, command_id, 0):
        raise OSError(C.get_last_error(), 'Cannot dispatch menu command')
    return matches[0]


def capture(hwnd, path):
    from PIL import Image
    G = C.WinDLL('gdi32', use_last_error=True)
    U.GetWindowDC.argtypes = [W.HWND]
    U.GetWindowDC.restype = W.HDC
    U.ReleaseDC.argtypes = [W.HWND, W.HDC]
    U.PrintWindow.argtypes = [W.HWND, W.HDC, W.UINT]
    G.CreateCompatibleDC.argtypes = [W.HDC]
    G.CreateCompatibleDC.restype = W.HDC
    G.CreateCompatibleBitmap.argtypes = [W.HDC, C.c_int, C.c_int]
    G.CreateCompatibleBitmap.restype = W.HBITMAP
    G.SelectObject.argtypes = [W.HDC, W.HGDIOBJ]
    G.SelectObject.restype = W.HGDIOBJ
    G.GetDIBits.argtypes = [W.HDC, W.HBITMAP, W.UINT, W.UINT, C.c_void_p, C.c_void_p, W.UINT]
    G.DeleteObject.argtypes = [W.HGDIOBJ]
    G.DeleteDC.argtypes = [W.HDC]
    class Header(C.Structure):
        _fields_ = [('size', W.DWORD), ('width', W.LONG), ('height', W.LONG),
                    ('planes', W.WORD), ('bits', W.WORD), ('compression', W.DWORD),
                    ('imageSize', W.DWORD), ('xppm', W.LONG), ('yppm', W.LONG),
                    ('colors', W.DWORD), ('important', W.DWORD)]
    r = window(hwnd)['rect']
    width, height = r[2]-r[0], r[3]-r[1]
    if not (0 < width < 12000 and 0 < height < 12000):
        raise ValueError('Window has no capturable bounds')
    source = U.GetWindowDC(hwnd)
    dc = G.CreateCompatibleDC(source)
    bitmap = G.CreateCompatibleBitmap(source, width, height)
    old = G.SelectObject(dc, bitmap)
    try:
        if not U.PrintWindow(hwnd, dc, 2):
            raise RuntimeError('PrintWindow failed')
        G.SelectObject(dc, old)
        header = Header(C.sizeof(Header), width, -height, 1, 32, 0, 0, 0, 0, 0, 0)
        data = C.create_string_buffer(width*height*4)
        if G.GetDIBits(dc, bitmap, 0, height, data, C.byref(header), 0) != height:
            raise RuntimeError('GetDIBits failed')
        Image.frombytes('RGB', (width, height), data.raw, 'raw', 'BGRX').save(path)
    finally:
        G.SelectObject(dc, old)
        G.DeleteObject(bitmap)
        G.DeleteDC(dc)
        U.ReleaseDC(hwnd, source)
    return {'path': str(path), 'width': width, 'height': height}


if __name__ == '__main__':
    import settings
    ap = argparse.ArgumentParser()
    ap.add_argument('--pid', type=int, required=True)
    ap.add_argument('--exe', default=settings.executable())
    ap.add_argument('--hwnd', type=int)
    ap.add_argument('--output')
    ap.add_argument('action', choices=['state', 'screenshot', 'command', 'set-text', 'button'])
    ap.add_argument('--command-id', type=int)
    ap.add_argument('--text')
    args = ap.parse_args()
    try:
        validate(args.pid, args.exe, args.hwnd)
        if args.action == 'state':
            result = state(args.pid)
        elif args.action == 'screenshot':
            result = capture(args.hwnd, args.output)
        elif args.action == 'command':
            result = command(args.hwnd, args.command_id)
        elif args.action == 'set-text':
            w = window(args.hwnd)
            if not w['visible'] or not w['enabled'] or w['cls'] not in ('Edit', 'TEdit', 'TFloatEdit', 'TComboBox', 'ComboBox'):
                raise RuntimeError('Target is not an editable visible control')
            b = C.create_unicode_buffer(args.text)
            send(args.hwnd, 0x000c, 0, C.addressof(b))
            result = {'hwnd': args.hwnd, 'text': read_text(args.hwnd)}
        else:
            w = window(args.hwnd)
            if not w['visible'] or not w['enabled'] or w['cls'] not in ('TButton', 'Button', 'TBitBtn'):
                raise RuntimeError('Target is not an enabled visible button')
            U.PostMessageW(args.hwnd, 0x00f5, 0, 0)
            result = {'button': w}
        if args.output and args.action != 'screenshot':
            Path(args.output).write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
        if args.action == 'state' and args.output:
            result = [{k:v for k,v in w.items() if k not in ('children','menu')} for w in result]
        print(json.dumps({'ok': True, 'result': result}, ensure_ascii=False))
    except Exception as exc:
        print(json.dumps({'ok': False, 'error': type(exc).__name__, 'message': str(exc)}, ensure_ascii=False))
        raise SystemExit(1)
