#  ping测试工具
from utils import setup_logging,setup_sys_path
setup_sys_path() #设置系统路径
logger = setup_logging()  # 设置日志记录器
import wx
import asyncio
import threading,subprocess
from utils import ipAddressCheck
from register_tool import register_tool

# ping指定主机，异步任务
async def ping_host(host, cancel_event:asyncio.Event,timeout=2):
    """
    异步Ping指定主机。

    :param host: 要Ping的主机地址
    :param cancel_event: 用于取消Ping任务的事件对象
    :param timeout: 超时时间，单位秒
    :return: 如果Ping通，返回包含主机信息的字符串；如果Ping不通或任务取消，返回相应信息
    """
    if cancel_event.is_set():# 如果取消事件已设置，直接返回None
        logger.info(f"Ping {host} 任务已取消，直接返回None")
        return None

    try:
        if hasattr(subprocess, 'CREATE_NEW_PROCESS_GROUP'):  # CREATE_NEW_PROCESS_GROUP 是 Windows 系统特有的标志
            logger.info("Windows系统，使用windows平台的ping命令参数")
            ping_task = await asyncio.create_subprocess_exec(
                'ping', '-n', '1', '-w', str(timeout*1000), host,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
        else:
            logger.info("类Unix系统，使用类Unix平台的ping命令参数")
            ping_task = await asyncio.create_subprocess_exec(
                'ping', '-c', '1', '-w', str(timeout), host,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
        logger.info(f"子进程已经创建完成，开始执行Ping {host} 任务，等待结果...")

        # 等待ping命令完成或被取消,
        # ping_task.wait()和cancel_event.wait()返回的都是一个协程对象，而非task对象，
        # 而asyncio.wait()需要的是task对象，通常传入 Task 列表，若传入协程，会被自动包装为 Task，但建议显式使用 asyncio.create_task() 包装
        done,pending = await asyncio.wait(
            [asyncio.create_task(ping_task.wait()),asyncio.create_task(cancel_event.wait())],
            return_when=asyncio.FIRST_COMPLETED,
            timeout=timeout
        )
        logger.info(f"Ping {host} 任务完成或被取消，等待结果处理...")

        #判断任务是被取消还是正常完成
        if cancel_event.is_set():
            if ping_task.returncode is None:#任务被取消，但是任务已经在运行中
                logger.info(f"Ping {host} 任务被取消，尝试终止子进程...")
                try:
                    ping_task.terminate()#先尝试温和方式终止子进程
                    try:
                        await asyncio.wait_for(ping_task.wait(),timeout=1)#等待子进程自行结束，超时一秒，可以让子进程有时间清理资源
                    except asyncio.TimeoutError:
                        logger.warning(f"Ping {host} 子进程未能在1秒内结束，强制终止...")
                    try:    
                        ping_task.kill()#如果强制终止也失败，直接结束进程
                        await ping_task.wait()#显式调用子进程的wait方法，确保子进程终止完成并回收资源，因此建议与上面的Kill方法配合使用
                    except ProcessLookupError:
                        logger.warning(f"Ping {host} 子进程已不存在，PASS")

                except ProcessLookupError:
                    logger.error(f"Ping {host} 子进程不存在,不需要终止")
            logger.info(f"Ping {host} 任务被取消，直接返回None")
            return f"用户取消Ping {host} 任务"
        
        # 取消事件未设置，说明ping命令已完成，开始处理结果
        stdout,stderr = await ping_task.communicate()#需要获取子进程的输出和错误信息，确保管道资源被正确释放，ping_task.wait() 只会返回子进程的返回码，不会获取输出和错误信息，
        #stdout和stderr都是字节类型，需要解码为字符串，并且需要根据操作系统的不同进行解码
        if hasattr(subprocess, 'CREATE_NEW_PROCESS_GROUP'):  # Windows系统，使用gbk编码
            logger.info("Windows系统，使用gbk编码解码输出")
            stdout = stdout.decode('gbk', errors='ignore')
            logger.info(f"stdout:{stdout}")
            stderr = stderr.decode('gbk', errors='ignore')
            logger.info(f"stderr:{stderr}")
        else:  # 类Unix系统，使用utf-8编码
            logger.info("类Unix系统，使用utf-8编码解码输出")
            stdout = stdout.decode('utf-8', errors='ignore')
            logger.info(f"stdout:{stdout}")
            stderr = stderr.decode('utf-8', errors='ignore')
            logger.info(f"stderr:{stderr}")
        #分析输出内容是否包含Ping成功的关键字
        is_reachable = False
        if stdout:# 如果stdout不为空，说明Ping命令有输出内容
            success_keywords = [
                "TTL=", 
                "time=", 
                "bytes from",
                "最长",
                "最短",
                "平均",
                ]
            failure_keywords = [
                "请求超时",
                "目标主机不可达",
                "packets lost",
                "100% 丢失",
            ]
            # 检查输出内容是否包含成功的关键字
            if any(keyword.lower() in stdout.lower()for keyword in success_keywords):
                is_reachable = True
            elif any(keyword.lower() in stdout.lower() for keyword in failure_keywords):
                is_reachable = False
            else:
                logger.info(f"Ping {host} 输出内容不包含成功或失败的关键字，判断为不可达")
                is_reachable = False
        elif stderr:# 如果stderr不为空，说明Ping命令有错误输出
            logger.info(f"Ping {host} 输出内容包含错误信息，判断为不可达")
            is_reachable = False
        else:# 如果stdout和stderr都为空，说明Ping命令没有输出内容
            return f"Ping {host} 没有输出成功或错误信息，无法判断主机是否可达"

        #判断主机是否可达
        if is_reachable:
            logger.info(f"Ping {host} 成功，主机可达")
            return f"Ping {host} 成功，主机可达"
        else:
            logger.info(f"Ping {host} 失败，主机不可达")
            return f"Ping {host} 失败，主机不可达"
    except asyncio.TimeoutError:
        logger.error(f"Ping {host}任务超时")
        return f"Ping {host} 超时"
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
    frame.SetMinSize(wx.Size(400, 300))
    panel = wx.Panel(frame)
    sizer = wx.BoxSizer(wx.VERTICAL)
    pingTester = PingTester(panel)
    sizer.Add(pingTester,1,wx.EXPAND,5)#Add方法的第二个参数0表示控制或子sizer不会随着父容器的大小变化而变化，比例因子大于0时，表示控件或子sizer会根据比例因子的值来调整大小
    panel.SetSizer(sizer)
    frame.Show()
    frame.Center()
    app.MainLoop()