from utils import setup_logging,setup_sys_path
setup_sys_path()
logger = setup_logging()

import wx
from register_tool import register_tool


@register_tool("网络类","日志发送工具")
class LogsToolsPanel(wx.Panel):
    def __init__(self, parent):
        super().__init__(parent)

        sizer = wx.BoxSizer(wx.HORIZONTAL)#主布局,水平方向，分为两个部分，最左边是参数配置部分，中间是IP地址输入，syslog输入部分和发送按钮

        #参数配置区域
        config_box = wx.StaticBox(self,label="参数配置")
        config_sizer = wx.StaticBoxSizer(config_box,wx.VERTICAL)#参数配置布局,垂直方向
        #配置端口号
        port_label = wx.StaticText(self,label="端口号(默认514)：")
        config_sizer.Add(port_label,0,wx.EXPAND|wx.TOP,10)
        self.port_config = wx.TextCtrl(self,size=wx.Size(100,-1))
        self.port_config.SetHint("1-65535")
        config_sizer.Add(self.port_config,0,wx.EXPAND|wx.BOTTOM,10)

        #RFC标准
        rfc_label = wx.StaticText(self,label="RFC标准：")
        config_sizer.Add(rfc_label,0,wx.EXPAND|wx.TOP,10)
        rfc_item = ["RFC3164","RFC5424"]
        self.rfc_choice = wx.Choice(self,choices=rfc_item)
        self.rfc_choice.SetSelection(0)
        config_sizer.Add(self.rfc_choice,0,wx.EXPAND|wx.BOTTOM,10)

        #日志级别
        log_level_item = ["TRACE","DEBUG","INFO","WARN","ERROR"]
        log_level_label = wx.StaticText(self,label="日志级别：")
        config_sizer.Add(log_level_label,0,wx.EXPAND|wx.TOP,10)
        self.log_level_choice = wx.Choice(self,choices=log_level_item)
        self.log_level_choice.SetSelection(2)#默认WARN
        config_sizer.Add(self.log_level_choice,0,wx.EXPAND|wx.BOTTOM,10)

        sizer.Add(config_sizer,1,wx.EXPAND|wx.RIGHT,5)

        #日志区
        operator_box = wx.StaticBox(self,label="操作区")
        operator_sizer = wx.StaticBoxSizer(operator_box,wx.VERTICAL)
        #IP地址输入区
        dst_ip_label = wx.StaticText(self,label="目标主机IP：")#目标主机ip标签
        operator_sizer.Add(dst_ip_label,0,wx.EXPAND|wx.TOP,10)
        self.dst_input = wx.TextCtrl(self,size=wx.Size(200,-1))
        operator_sizer.Add(self.dst_input,0,wx.EXPAND|wx.BOTTOM,10)
       
        #发送按钮
        send_btn = wx.Button(self,label="发送")
        send_btn.Bind(wx.EVT_BUTTON,lambda event:self.send(event,))
        operator_sizer.Add(send_btn,0,wx.EXPAND|wx.BOTTOM,10)
     
        #日志输入区
        log_input_label = wx.StaticText(self,label="日志输入：")
        operator_sizer.Add(log_input_label,0,wx.EXPAND|wx.TOP,10)
        self.log_input = wx.TextCtrl(self,size=wx.Size(200,100),style=wx.TE_MULTILINE)
        operator_sizer.Add(self.log_input,0,wx.EXPAND|wx.BOTTOM,10)
        sizer.Add(operator_sizer,5,wx.EXPAND|wx.LEFT,5)
  
        #快捷输入日志
        preset_choice = [
            "预置日志01",
            "预置日志02",
            "预置日志03",
            "预置日志04",
            "预置日志05",
            "预置日志06"
        ]
        self.log_shortcut = wx.RadioBox(self,label="快捷输入",choices=preset_choice,majorDimension=3)
        self.log_shortcut.Bind(wx.EVT_RADIOBOX,self.on_log_shortcut)
        operator_sizer.Add(self.log_shortcut,0,wx.EXPAND|wx.BOTTOM,10)

        #应用全局布局
        self.SetSizer(sizer)

        self.load_preset_log(0)#默认选择第一个

    # 发送日志绑定按钮
    def send(self,event):
        dst_host = self.dst_input.GetValue()
        port = int(self.port_config.GetValue() or 514)
        log_msg = str(self.log_input.GetValue())
        log_level = str(self.log_level_choice.GetStringSelection()) or "INFO"
        log_std = str(self.rfc_choice.GetStringSelection()) or "RFC3164"
        if dst_host is None or dst_host == "":
            msg = wx.MessageBox("请输入目标主机IP","错误提示",wx.OK|wx.ICON_ERROR)
            logger.error("未输入目标主机IP")
            return
        msg = wx.MessageBox("发送成功","信息提示",wx.OK|wx.ICON_INFORMATION)
        logger.info(f"发送日志：{log_msg}，目标主机：{dst_host}，端口：{port}，日志级别：{log_level}，RFC标准：{log_std}")


    #加载预置日志
    def load_preset_log(self,selection):
        preset_logs = {
            0:"预置日志1",
            1:"预置日志2",
            2:"预置日志3"
        }
        if selection in preset_logs:
            self.log_input.SetValue(preset_logs[selection])
    #快捷输入日志绑定事件函数
    def on_log_shortcut(self,event):
        self.load_preset_log(event.GetSelection())








if __name__ ==  "__main__":
    app = wx.App()
    frame = wx.Frame(None,title="日志工具")
    frame.SetMinSize(wx.Size(500,400))  # 将最小大小设置移到这里
    panel = wx.Panel(frame)
    sizer = wx.BoxSizer(wx.VERTICAL)
    logsToolsPanel = LogsToolsPanel(panel)
    sizer.Add(logsToolsPanel,0,wx.EXPAND,5)
    panel.SetSizer(sizer)
    frame.Show()
    frame.Center()
    app.MainLoop()