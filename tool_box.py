#工具合集GUI
'''
一个小工具合集，可以用来测试网络，爬虫，API，数据库，网站等等
一共二级页面
一级页面：显示工具分类
二级页面：显示具体的工具NoteBook样式
类名命名规则：驼峰命名法，首字母大写
方法名命名规则：驼峰命名法，首字母小写
变量名命名规则：下划线命名法，全小写
常量名命名规则：下划线命名法，单词首字母大写
'''

import wx
import importlib,os
from typing import Dict,Callable,Type
#import tools.ping_testing_tool
from register_tool import TOOL_LIST

#自动引入所有的工具类
def auto_import_tool(tools_ptah:str):
    '''
    自动引入所有的工具类
    :param tools_dir: 工具目录
    '''
    #1，获取工具目录的绝对路径
    current_path = os.path.dirname(os.path.abspath(__file__))
    tools_abs_path = os.path.join(current_path,tools_ptah)

    #2，检查目录是否存在
    if not os.path.isdir(tools_abs_path):
        print(f"目录{tools_abs_path}不存在")
        return
    #3，遍历目录下所有文件，需要排除__init__.py文件和隐藏文件
    for file_name in os.listdir(tools_abs_path):
        if file_name.endswith(".py") and not file_name.startswith(("__",".")):
            module_name = f"{tools_ptah}.{file_name[:-3]}"
            try:
                importlib.import_module(module_name)
                print(f"导入模块{module_name}成功")
            except Exception as e:
                print(f"导入模块{module_name}失败，错误信息：{e}")



class ToolDetailPanel(wx.Panel):
    def __init__(self,parent:wx.Panel,tools:Dict[str,Type[wx.Panel]],on_back:Callable):
        '''
        工具详情面板，显示具体的工具操作界面，使用Notebook展示每个工具的操作页面
        :param parent: 父窗口
        :param tools: 工具列表，每个元素是一个工具名称和工具类
        :param on_back: 点击返回按钮回调函数
        '''
        super().__init__(parent)
        self.tools_by_name = tools
        self.on_back = on_back

        #1，创建布局器
        tool_sizer = wx.BoxSizer(wx.VERTICAL)

        #2，添加一个返回到工具分类界面的按钮
        back_btn = wx.Button(self,label="返回")
        back_btn.Bind(wx.EVT_BUTTON,lambda event:self.on_back())
        tool_sizer.Add(back_btn,0,wx.ALL,5)

        #3，添加一个Notebook，用来展示每个工具的操作页面
        self.tool_notebook = wx.Notebook(self)
        for tool_name,tool_class in self.tools_by_name.items():
            #创建一个工具页面
            # Create tool page with notebook as parent
            tool_page = tool_class(self.tool_notebook)
            # Add to Notebook
            self.tool_notebook.AddPage(tool_page, tool_name)
        tool_sizer.Add(self.tool_notebook,1,wx.ALL|wx.EXPAND,5)
        self.SetSizer(tool_sizer)
        

class CategoryPanel(wx.Panel):
    def __init__(self,parent:wx.Panel,tools_category_list:list[str],on_category_click:Callable):
        '''
        分类面板，显示若干工具按钮，点击按钮切换到具体工具操作界面
        :param parent: 父窗口
        :param tools_list: 工具列表，每个元素是一个分类名称
        :param on_category_click: 点击分类回调函数
        '''
        super().__init__(parent)
        self.tools_category_list = tools_category_list
        self.on_category_click = on_category_click
        #1，创建布局器
        category_sizer = wx.BoxSizer(wx.VERTICAL)
        #2，添加分类按钮
        for category_name in self.tools_category_list:
            category_btn = wx.Button(self,label=category_name)
            category_btn.Bind(wx.EVT_BUTTON,self.on_category_click)
            category_sizer.Add(category_btn,0,wx.ALL|wx.EXPAND,5)
        self.SetSizer(category_sizer)


class ToolBoxMainFrame(wx.Frame):
    def __init__(self,tool_list:Dict[str,Dict[str,Type[wx.Panel]]]):
        '''
        工具合集主窗口，可以在工具分类的panel和具体工具操作界面之间切换
        :param tool_list: 工具列表，每个元素是一个分类名称
        '''

        
        super().__init__(parent=None,title="工具合集")

        #1，创建面板布局器
        self.panel_sizer = wx.BoxSizer(wx.VERTICAL)
        #2，添加一个界面容器
        self.panel = wx.Panel(self)
        #3，把工具分类界面加载到面板中
        self.tools_category_list = list(tool_list.keys())
        self.category_panel = CategoryPanel(self.panel, self.tools_category_list, self.on_category_click)
        self.panel_sizer.Add(self.category_panel, 1, wx.ALL|wx.EXPAND, 5)
        #4，应用布局器并展示窗口
        self.panel.SetSizer(self.panel_sizer)
        self.Center()
        self.Show()
        

    def on_category_click(self, event):
        '''
        点击分类回调函数，切换到具体工具操作界面
        '''
        # 获取点击的分类名称
        category_name = event.GetEventObject().GetLabel()
        #self.panel_sizer.Clear()
        self.category_panel.Hide()
        #1，获取分类下的所有工具
        tools_by_name = TOOL_LIST.get(category_name, {})#获取不到时，返回一个空字典
        #2，创建工具详情面板
        self.detail_panel = ToolDetailPanel(self.panel,tools_by_name,self.on_back)
        #3，替换分类面板为工具详情面板
        self.panel_sizer.Add(self.detail_panel, 1, wx.ALL|wx.EXPAND, 5)
        #4，刷新窗口
        self.panel.Layout()
        pass
    def on_back(self):
        '''
        点击返回按钮回调函数，返回工具分类界面
        '''
        self.detail_panel.Hide()
        self.category_panel.Show()
        self.panel.Layout()
        pass

if __name__ == "__main__":
    app = wx.App()
    auto_import_tool("tools")
    frame = ToolBoxMainFrame(TOOL_LIST)
    print(TOOL_LIST)
    frame.Show()
    app.MainLoop()