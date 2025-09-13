from utils import setup_logging,setup_sys_path
setup_sys_path()
logger = setup_logging()

import wx
import logging
import socket
from logging.handlers import SysLogHandler
from register_tool import register_tool
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime,timezone


class RFC3614Formatter(logging.Formatter):
    def format(self, record):#record是LogRecord对象,必须的参数，在使用logger.info时会自动传入
        #时间戳格式
        timestamp = datetime.fromtimestamp(record.created).strftime("%b %d %H:%M:%S")#
        #主机名
        hostname = socket.gethostname() or "unknown"
        #应用名和进程ID
        app_name = record.name or "unknown"
        proc_id = f"[{record.process}]" if record.process else ""
        # 获取消息内容，替换换行符，下一步使用新格式重新生成日志内容
        message = record.getMessage().replace("\n","\\n")
        #返回rfc3614格式的日志内容
        return f"{timestamp} {hostname} {app_name}{proc_id}: {message}"

class RFC5424Formatter(logging.Formatter):
    def format(self, record):
        # 时间戳(ISO 8601 UTC)
        timestamp = datetime.fromtimestamp(record.created, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
        # 主机名
        hostname = socket.getfqdn() or "unknown-host"
        # 应用名
        app_name = record.name or "unknown-app"
        # 进程ID
        procid = str(record.process) if record.process else "-"
        # 消息ID
        msgid = "-"
        # 结构化数据
        structured_data = (
            f"[device@12345 interface={record.__dict__.get('interface', 'unknown')} "
            f"severity={record.levelname.lower()}]"
        )
        # 获取消息内容，替换换行符，下一步使用新格式重新生成日志内容
        message = record.getMessage().replace("\n", "\\n")
        # RFC 5424格式
        return f"1 {timestamp} {hostname} {app_name} {procid} {msgid} {structured_data} {message}"


def send_logs(host,log,rfc,log_level,facility,port=514):
    syslog_server = (str(host),int(port))#syslog服务器地址和端口号

    #创建syslog日志记录器
    syslog_logger = logging.getLogger("syslog_logger")
    syslog_logger.setLevel(logging.DEBUG)
    #配置SyslogHandler，指定设施值
    syslog_handler = SysLogHandler(address=syslog_server,facility=facility)
    #设置日志格式
    syslog_formatter = RFC3614Formatter() if rfc == "RFC3614" else RFC5424Formatter()
    syslog_handler.setFormatter(syslog_formatter)
    #添加处理器到日志记录器
    syslog_logger.addHandler(syslog_handler)

    # 创建LogRecord对象
    log_record = logging.LogRecord(
        name=syslog_logger.name,
        level=getattr(logging, log_level),
        pathname="",
        lineno=0,
        msg=log,
        args=(),
        exc_info=None
    )
    
    # 格式化日志内容
    formatted_log = syslog_formatter.format(log_record)
    #发送日志
    match log_level:
        case "DEBUG":
            syslog_logger.debug(log)
        case "INFO":
            syslog_logger.info(log)
        case "WARN":
            syslog_logger.warning(log)
        case "ERROR":
            syslog_logger.error(log)
        case "CRITICAL":
            syslog_logger.critical(log)
        case _:
            logger.error("未知的日志级别")
    
    logger.info(formatted_log)#打印格式化后的日志内容
    # 需移除处理器，否则每次调用该方法都会添加一个新的处理器，导致重复发送日志
    syslog_logger.removeHandler(syslog_handler)


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
        rfc_item = ["RFC3614","RFC5424"]
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
        self.preset_choice = [
            "SSH登录失败",
            "SSH登录成功",
            "系统启动",
            "系统关闭",
            "接口UP",
            "接口DOWN",
        ]
        self.log_shortcut = wx.RadioBox(self,label="快捷输入",choices=self.preset_choice,majorDimension=3)
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
        
        #发送日志
        try:
            with ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(send_logs,*(dst_host,log_msg,log_std,log_level,port))
                future.result()#等待任务完成
            logger.info(f"发送日志：{log_msg}，目标主机：{dst_host}，端口：{port}，日志级别：{log_level}，RFC标准：{log_std}")
            msg = wx.MessageBox("发送成功","信息提示",wx.OK|wx.ICON_INFORMATION)
        except Exception as e:
            msg = wx.MessageBox("发送失败","错误提示",wx.OK|wx.ICON_ERROR)
            logger.error(f"发送日志失败：{e}")
            return

    #加载预置日志
    def load_preset_log(self,selection):
        preset_logs = {k:v for k,v in enumerate(self.preset_choice)}
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