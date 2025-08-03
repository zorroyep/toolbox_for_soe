'''
目录管理工具
'''

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
