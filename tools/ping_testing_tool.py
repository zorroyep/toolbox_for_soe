#  ping测试工具
from utils import setup_logging,setup_sys_path
setup_sys_path() #设置系统路径
logger = setup_logging()  # 设置日志记录器
import wx
from register_tool import register_tool

@register_tool("网络工具","ping测试工具")
class PingTestingTool(wx.Panel):
    def __init__(self,parent:wx.Panel):
        super().__init__(parent)
        sizer = wx.BoxSizer(wx.VERTICAL)

        #1，添加一个文本框，用于输入IP地址
        self.ip_text = wx.TextCtrl(self,style=wx.TE_READONLY)
        sizer.Add(self.ip_text,0,wx.ALL|wx.EXPAND,5)
        #2，添加一个按钮，用于开始ping测试
        self.ping_btn = wx.Button(self,label="开始ping测试")
        sizer.Add(self.ping_btn,0,wx.ALL|wx.EXPAND,5)
        #3，添加一个文本框，用于显示ping测试结果
        self.result_text = wx.TextCtrl(self,style=wx.TE_READONLY|wx.TE_MULTILINE)
        sizer.Add(self.result_text,1,wx.ALL|wx.EXPAND,5)
        #4，添加一个按钮，用于清除ping测试结果
        self.clear_btn = wx.Button(self,label="清除结果")
        sizer.Add(self.clear_btn,0,wx.ALL|wx.EXPAND,5)
        #5，应用布局器
        self.SetSizer(sizer)
if __name__ == "__main__":
    app = wx.App()
    frame = wx.Frame(None, title="ping测试")
    panel = PingTestingTool(frame)
    frame.SetSizer(wx.BoxSizer(wx.VERTICAL))
    frame.GetSizer().Add(panel, 1, wx.EXPAND)
    frame.Centre()
    frame.Show()
    app.MainLoop()