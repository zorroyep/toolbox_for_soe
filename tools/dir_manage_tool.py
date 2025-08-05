'''
目录管理工具
'''
from utils import setup_logging,setup_sys_path
setup_sys_path() #设置系统路径
logger = setup_logging()  # 设置日志记录器

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
        


if __name__ == "__main__":
    app = wx.App()
    frame = wx.Frame(None, title="目录管理工具测试")
    panel = DirManageTool(frame)
    frame.SetSizer(wx.BoxSizer(wx.VERTICAL))
    frame.GetSizer().Add(panel, 1, wx.EXPAND)
    frame.Centre()
    frame.Show()
    app.MainLoop()