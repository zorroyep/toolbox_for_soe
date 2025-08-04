'''
网站导航工具
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
import wx
import wx.adv
import webbrowser
from register_tool import register_tool

website_list = [
    {"name":"百度","url":"https://www.baidu.com"},
    {"name":"Google","url":"https://www.google.com"},
    {"name":"Bing","url":"https://www.bing.com"},
    {"name":"必应","url":"https://www.bing.com"},
    {"name":"360搜索","url":"https://www.so.com"},
]

@register_tool("WEB工具","网站导航工具")
class WebsiteNavigate(wx.Panel):
    def __init__(self,parent:wx.Panel):
        super().__init__(parent)

        #1,创建布局器
        navigate_sizer = wx.BoxSizer(wx.VERTICAL)

        #2,添加一个网站导航工具的标题
        

        #3,添加一个网站导航工具的列表
        for website in website_list:
            link = wx.adv.HyperlinkCtrl(self,id=wx.ID_ANY,label=website["name"],url=website["url"])
            link.Bind(wx.adv.EVT_HYPERLINK,self.openlink)
            navigate_sizer.Add(link,0,wx.ALL,5)
        self.SetSizer(navigate_sizer)

    def openlink(self,event):
        url = event.GetURL()
        webbrowser.open(url)


if __name__ == "__main__":
    app = wx.App()
    frame = wx.Frame(None, title="网站导航工具")
    panel = WebsiteNavigate(frame)
    frame.SetSizer(wx.BoxSizer(wx.VERTICAL))
    frame.GetSizer().Add(panel, 1, wx.EXPAND)
    frame.Centre()
    frame.Show()
    app.MainLoop()