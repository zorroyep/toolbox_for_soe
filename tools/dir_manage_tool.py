'''
目录管理工具
'''
from utils import setup_logging,setup_sys_path
setup_sys_path() #设置系统路径
logger = setup_logging()  # 设置日志记录器

import wx
from pathlib import Path
from register_tool import register_tool
from contextlib import suppress

#删除指定目录指定后缀名的文件
def delete_files_by_suffix(dir_path,suffix):
    dir_path = Path(dir_path)
    for file in dir_path.glob(f"*.{suffix}"):
        with suppress(FileNotFoundError):
            file.unlink()
            logger.info(f"删除文件{file}成功")

@register_tool("文件工具","目录管理工具")
class DirManageTool(wx.Panel):
    def __init__(self,parent:wx.Panel):
        super().__init__(parent)
        #1，创建布局器
        dir_manage_sizer = wx.BoxSizer(wx.VERTICAL)
        #2，添加一个目录管理工具的标题
        dir_manage_title = wx.StaticText(self,label="目录管理工具")
        dir_manage_sizer.Add(dir_manage_title,0,wx.ALL,5)

        #删除指定目录指定后缀名的文件
        delete_box = wx.StaticBox(self,label="删除指定目录指定后缀名的文件")
        delete_box_sizer = wx.StaticBoxSizer(delete_box,wx.HORIZONTAL)
        #输入区
        input_area = wx.BoxSizer(wx.VERTICAL)

        dir_area = wx.BoxSizer(wx.HORIZONTAL)
        dir_label = wx.StaticText(self,label="选择目录:")
        dir_area.Add(dir_label,0,wx.ALL,5)
        self.dir_input = wx.TextCtrl(self,style=wx.TE_READONLY)
        dir_area.Add(self.dir_input,0,wx.ALL,5)
        select_dir_btn = wx.Button(self,label="...")
        select_dir_btn.Bind(wx.EVT_BUTTON,self.on_select_dir)
        dir_area.Add(select_dir_btn,0,wx.ALL,5)
        input_area.Add(dir_area,0,wx.ALL,5)
        #填写后缀名
        suffix_area = wx.BoxSizer(wx.HORIZONTAL)
        suffix_label = wx.StaticText(self,label="后缀名:")
        suffix_area.Add(suffix_label,0,wx.ALL,5)
        self.suffix_input = wx.TextCtrl(self)
        suffix_area.Add(self.suffix_input,0,wx.ALL,5)
        input_area.Add(suffix_area,0,wx.ALL,5)
        delete_box_sizer.Add(input_area,0,wx.ALL,5)
        #删除按钮
        delete_btn = wx.Button(self,label="删除")
        delete_box_sizer.Add(delete_btn,0,wx.ALL,5)
        delete_btn.Bind(wx.EVT_BUTTON,self.on_delete_file_by_suffix)
        

        #添加到主布局器
        dir_manage_sizer.Add(delete_box_sizer,0,wx.ALL,5)
        self.SetSizer(dir_manage_sizer)
        
    def on_delete_file_by_suffix(self,event):
        dir_path = self.dir_input.GetValue()
        suffix = self.suffix_input.GetValue()
        delete_files_by_suffix(dir_path,suffix)

    def on_select_dir(self,event):
        dir_path = wx.DirSelector("选择目录")
        self.dir_input.SetValue(dir_path)


if __name__ == "__main__":
    app = wx.App()
    frame = wx.Frame(None, title="目录管理工具测试")
    panel = DirManageTool(frame)
    frame.SetSizer(wx.BoxSizer(wx.VERTICAL))
    frame.GetSizer().Add(panel, 1, wx.EXPAND)
    frame.SetMinSize(wx.Size(600,300))

    frame.Centre()
    frame.Show()
    app.MainLoop()