'''
网站导航工具
'''

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


