"""Read native tab captions exposed by Windows UI Automation (no input/OCR)."""
import comtypes.client
import re


def tab_names(hwnd):
    types=comtypes.client.GetModule('UIAutomationCore.dll')
    automation=comtypes.client.CreateObject(types.CUIAutomation,interface=types.IUIAutomation)
    element=automation.ElementFromHandle(hwnd)
    items=element.FindAll(2,automation.CreateTrueCondition())
    return [items.GetElement(i).CurrentName for i in range(items.Length)
            if items.GetElement(i).CurrentControlType==50019]


def invoke_popup(pid, pattern):
    """Invoke one actual popup item in this process, without global input."""
    from win32_probe import windows
    menus=[w for w in windows(pid) if w['cls']=='#32768' and w['visible']]
    if len(menus)!=1:
        raise ValueError('Expected one native popup in the selected process')
    types=comtypes.client.GetModule('UIAutomationCore.dll')
    automation=comtypes.client.CreateObject(types.CUIAutomation,interface=types.IUIAutomation)
    items=automation.ElementFromHandle(menus[0]['hwnd']).FindAll(4,automation.CreateTrueCondition())
    matches=[items.GetElement(i) for i in range(items.Length)
             if re.search(pattern,items.GetElement(i).CurrentName or '',re.I)]
    if len(matches)!=1:
        raise ValueError('Popup command absent or ambiguous')
    name=matches[0].CurrentName
    matches[0].GetCurrentPattern(10000).QueryInterface(types.IUIAutomationInvokePattern).Invoke()
    return name
