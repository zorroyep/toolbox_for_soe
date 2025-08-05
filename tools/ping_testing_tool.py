#  ping测试工具
from utils import setup_logging,setup_sys_path
setup_sys_path() #设置系统路径
logger = setup_logging()  # 设置日志记录器
import wx
import asyncio
import threading,subprocess
from utils import ipAddressCheck
from register_tool import register_tool

# 异步Ping测试
async def ping_host(host, cancel_event):
    """
    异步Ping指定主机。

    :param host: 要Ping的主机地址
    :param cancel_event: 用于取消Ping任务的事件对象
    :return: 如果Ping通，返回包含主机信息的字符串；如果Ping不通或任务取消，返回相应信息
    """
    if cancel_event.is_set():
        return None

    try:
        if hasattr(subprocess, 'CREATE_NEW_PROCESS_GROUP'):  # 修改为 subprocess
            logger.info("Windows系统")
            create = asyncio.create_subprocess_exec(
                'ping', '-n', '1', host,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP  # 修改为 subprocess
            )
        else:
            logger.info("类Unix系统")
            create = asyncio.create_subprocess_exec(
                'ping', '-c', '1', host,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
        proc = await create
        stdout, stderr = await proc.communicate()

        if proc.returncode == 0:
            logger.info(f"{host} 可以Ping通")
            return f"{host} 可以Ping通"
        else:
            logger.info(f"{host} 无法Ping通")
            return f"{host} 无法Ping通"
    except Exception as e:
        logger.error(f"Ping {host} 时发生错误: {e}")
        return f"Ping {host} 时发生错误: {e}"


# 异步Ping网络
async def ping_network(hosts_info, cancel_event, result_callback):
    all_results = []
    for host in hosts_info:
        if cancel_event.is_set():
            break
        result = await ping_host(host, cancel_event)
        if result:
            result_callback(result)
            all_results.append(result)
    return all_results

@register_tool("网络类","PING工具")
class PingTester(wx.Panel):
    def __init__(self, parent):
        super().__init__(parent)

        sizer = wx.BoxSizer(wx.VERTICAL)

        # 主机输入框
        host_lable = wx.StaticText(self, label="主机：")
        sizer.Add(host_lable, 0, wx.EXPAND, 5)
        self.host_inputbox = wx.TextCtrl(self)
        sizer.Add(self.host_inputbox, 0, wx.EXPAND, 5)

        # Ping测试开始按钮
        self.start_ping_btn = wx.Button(self, label="开始Ping测试")
        self.start_ping_btn.Bind(wx.EVT_BUTTON, self.start_ping)
        sizer.Add(self.start_ping_btn, 0, wx.EXPAND, 5)

        # 任务取消按钮
        self.cancel_btn = wx.Button(self, label="取消")
        self.cancel_btn.Bind(wx.EVT_BUTTON, self.cancelTask)
        self.cancel_btn.Disable()
        sizer.Add(self.cancel_btn, 0, wx.EXPAND, 5)

        # 结果显示框
        self.result_text = wx.TextCtrl(self, style=wx.TE_MULTILINE | wx.TE_READONLY)
        sizer.Add(self.result_text, 1, wx.EXPAND, 5)
        self.SetSizer(sizer)

        self.cancel_event = asyncio.Event()  # 用于取消任务的事件
        self.scan_task = None  # 保存扫描任务的变量
        # 创建事件循环并在新线程中运行
        self.loop = asyncio.new_event_loop()
        threading.Thread(target=self._runLoop, daemon=True).start()

    def _runLoop(self):
        asyncio.set_event_loop(self.loop)
        self.loop.run_forever()

    def start_ping(self, event):
        self.cancel_event.clear()
        self.cancel_btn.Enable()
        self.start_ping_btn.Disable()
        self.host_inputbox.Disable()
        self.result_text.Clear()

        hosts_info = self.host_inputbox.GetValue()
        hosts_list = ipAddressCheck(hosts_info)

        if hosts_list is None:
            wx.MessageBox("请输入正确的 IP 地址或 CIDR 块", "错误", wx.OK | wx.ICON_ERROR)
            self.start_ping_btn.Enable()
            self.host_inputbox.Enable()
            self.cancel_btn.Disable()
            return

        hosts_info = [str(host) for host in hosts_list]

        # 提交异步Ping任务到事件循环
        self.scan_task = asyncio.run_coroutine_threadsafe(
            ping_network(hosts_info, self.cancel_event, self.updateResult),
            self.loop
        )
        self.scan_task.add_done_callback(self._onScanCompleteThreadsafe)

    def _onScanCompleteThreadsafe(self, future):
        wx.CallAfter(self.onScanComplete, future)

    def updateResult(self, result):
        wx.CallAfter(self.result_text.AppendText, result + "\n")

    def onScanComplete(self, future):
        self.start_ping_btn.Enable()
        self.host_inputbox.Enable()
        self.cancel_btn.Disable()
        wx.CallAfter(self.result_text.AppendText, "\n扫描完成！")

    def cancelTask(self, event):
        self.cancel_event.set()
        if self.scan_task:
            self.scan_task.cancel()
        wx.MessageBox("任务已取消", "提示", wx.OK | wx.ICON_INFORMATION)
        self.start_ping_btn.Enable()
        self.host_inputbox.Enable()
        self.cancel_btn.Disable()


if __name__ ==  "__main__":
    app = wx.App()
    frame = wx.Frame(None)
    panel = wx.Panel(frame)
    sizer = wx.BoxSizer(wx.VERTICAL)
    pingTester = PingTester(panel)
    sizer.Add(pingTester,0,wx.EXPAND,5)
    panel.SetSizer(sizer)
    frame.Show()
    frame.Center()
    app.MainLoop()