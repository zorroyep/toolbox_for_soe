'''
目录管理工具
'''
from pathlib import Path
import sys
current_file = Path(__file__).resolve() #当前文件的绝对路径
current_dir = current_file.parent.parent #当前文件的父目录
if str(current_dir) not in sys.path:
    sys.path.append(str(current_dir)) #添加到系统路径中
    print(f"已将目录{current_dir}添加到系统路径中")
else:
    print(f"目录{current_dir}已在系统路径中，无需重复添加")
from tools.utils import common_tool


import wx
from register_tool import register_tool

@register_tool("文件工具","目录管理工具")
class DirManageTool(wx.Panel):
    def __init__(self,parent:wx.Panel):
        super().__init__(parent)
        #1，创建布局器
        dir_manage_sizer = wx.BoxSizer(wx.VERTICAL)
        #2，添加一个目录管理工具的标题
        dir_manage_title = wx.StaticText(self,label="目录管理工具")
        dir_manage_sizer.Add(dir_manage_title,0,wx.ALL,5)
        
        self.SetSizer(dir_manage_sizer)
        
        common_tool() #调用通用工具方法


if __name__ == "__main__":
    app = wx.App()
    frame = wx.Frame(None, title="目录管理工具测试")
    panel = DirManageTool(frame)
    frame.SetSizer(wx.BoxSizer(wx.VERTICAL))
    frame.GetSizer().Add(panel, 1, wx.EXPAND)
    frame.Centre()
    frame.Show()
    app.MainLoop()