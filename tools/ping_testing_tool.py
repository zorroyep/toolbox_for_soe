#  ping测试工具
from utils import setup_logging,setup_sys_path
setup_sys_path() #设置系统路径
logger = setup_logging()  # 设置日志记录器
import wx
import asyncio
import contextlib
import threading,subprocess
from concurrent.futures import Future
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
    if cancel_event.is_set():# 任务未运行时如果被取消则
        logger.info(f"该任务未运行，用户取消Ping {host} 任务")
        return f"该任务未运行，用户取消Ping {host} 任务"

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

        # 等待ping命令完成或被取消,使用cancel_event协调取消逻辑
        # ping_task.wait()和cancel_event.wait()返回的都是一个协程对象，而非task对象，
        # 而asyncio.wait()需要的是task对象，通常传入 Task 列表，若传入协程，会被自动包装为 Task，但建议显式使用 asyncio.create_task() 包装
        done,pending = await asyncio.wait(#asyncio.wait()方法返回值是两个set类型的future对象，done是已完成的任务，pending是未完成的任务
            [asyncio.create_task(ping_task.wait()),asyncio.create_task(cancel_event.wait())],
            return_when=asyncio.FIRST_COMPLETED,
            timeout=timeout
        )
        logger.info(f"Ping {host} 任务完成或被取消，等待结果处理...")

        #判断任务是被取消还是正常完成
        if cancel_event.is_set():
            with contextlib.suppress(ProcessLookupError):
                if ping_task.returncode is None:
                    ping_task.terminate()
                    with contextlib.suppress(asyncio.TimeoutError):
                        await asyncio.wait_for(ping_task.wait(), timeout=1)  # 等待子进程自行结束，超时一秒
            logger.info(f"运行中取消Ping {host} 任务，子进程已终止")
            return f"运行中取消Ping {host} 任务"

        
        # 取消事件未设置，说明ping命令已完成，开始处理结果
        stdout,stderr = await ping_task.communicate()#需要获取子进程的输出和错误信息，确保管道资源被正确释放，ping_task.wait() 只会返回子进程的返回码，不会获取输出和错误信息，
        if stderr:
            logger.error(f"Ping {host} 子进程返回错误信息，判断为不可达")
            return f"Ping {host} 子进程返回错误信息，判断为不可达"

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
            is_reachable = any(str(keyword) in str(stdout) for keyword in success_keywords)
            if not is_reachable and any(str(keyword) in str(stdout) for keyword in failure_keywords):
                is_reachable = False
            return f"ping {host} 成功，主机可达" if is_reachable else f"ping {host} 失败，主机不可达"
                               

    except asyncio.TimeoutError:
        logger.error(f"Ping {host} 任务超时")
        return f"Ping {host} 任务超时"
    except Exception as e:
        logger.error(f"Ping {host} 时发生错误: {e}")
        return f"Ping {host} 时发生错误: {e}"


# 异步Ping网络
async def ping_network(hosts_info, cancel_event:asyncio.Event, result_callback,max_concurrent_tasks=10):
    '''
    异步Ping网络中的多个主机。

    :param hosts_info: 主机信息列表，可以是IP地址或CIDR块
    :param cancel_event: 取消事件，用于取消任务
    :param result_callback: 结果回调函数，用于处理每个主机的Ping结果
    :param process_callback: 进度回调函数，用于处理任务进度
    :param max_concurrent_tasks: 最大并发任务数，默认10个任务并发执行
    :return: 所有主机的Ping结果列表
    '''
    all_results = []# 用于存储所有主机的Ping结果
    total = len(hosts_info)# 任务总数
    completed = 0# 已完成的任务数

    #分批添加任务，控制并发数量，默认是10个任务并发执行
    try:
        semaphore = asyncio.Semaphore(max_concurrent_tasks)  # 使用asyncio信号量控制并发数量

        async def semaphore_task(host):
            if cancel_event.is_set():
                logger.info(f"本批次任务已取消，跳过处理")
                return "本批次任务已取消，跳过处理"
            async with semaphore:
                if cancel_event.is_set():
                    logger.info(f"本批次任务已取消，跳过处理")
                    return "本批次任务已取消，跳过处理"
                return await ping_host(host, cancel_event)  # 调用ping_host函数进行Ping操作

        tasks = [ asyncio.create_task(semaphore_task(host))for host in hosts_info]# 将所有任务添加到任务列表中
        pending = set(tasks)  # asyncio.wait()方法的第一个参数是可迭代的future对象，使用set可以确保每个任务只被执行一次
        while pending and not cancel_event.is_set():
            done,pending = await asyncio.wait(pending,return_when=asyncio.FIRST_COMPLETED)#asyncio.wait()方法返回值是两个set类型的future对象，done是已完成的任务，pending是未完成的任务
            for future in done:
                logger.info(f"任务{future}完成")
                try:
                    result = future.result()  # 获取任务结果
                    if result:
                        all_results.append(result)  # 将结果返回给主线程，用于更新UI
                        completed += 1  # 更新已完成的任务数
                        result_callback(result,completed,total)
                except Exception as e:
                    logger.error(f"处理任务结果时发生错误: {e}")

        if pending:
            cancel_event.set()  # 如果有未完成的任务，设置取消事件
            await asyncio.gather(*pending, return_exceptions=True)  # 等待所有未完成的任务完成，忽略异常
    
    except Exception as e:
        logger.error(f"Ping网络任务异常: {e}")
    finally:
        return all_results  # 返回所有主机的Ping结果列表



@register_tool("网络类","PING工具")
class PingTester(wx.Panel):
    def __init__(self, parent):
        super().__init__(parent)

        #设置中文字体支持
        font = wx.Font(12, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL)
        self.SetFont(font)

        sizer = wx.BoxSizer(wx.VERTICAL)# 垂直布局


        # 主机输入框
        host_lable = wx.StaticText(self, label="主机：(可输入IP或CIDR，多个用逗号分隔):")
        sizer.Add(host_lable, 0, wx.EXPAND|wx.ALL, 5)
        self.host_inputbox = wx.TextCtrl(self)
        sizer.Add(self.host_inputbox, 0, wx.EXPAND|wx.ALL|wx.LEFT|wx.RIGHT|wx.BOTTOM, 5)

        #按钮区域
        btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
        # Ping测试开始按钮
        self.start_ping_btn = wx.Button(self, label="开始Ping测试")
        self.start_ping_btn.Bind(wx.EVT_BUTTON, self.start_ping)
        btn_sizer.Add(self.start_ping_btn, 1, wx.EXPAND|wx.RIGHT, 2)
        # 任务取消按钮
        self.cancel_btn = wx.Button(self, label="取消")
        self.cancel_btn.Bind(wx.EVT_BUTTON, self.cancel_tasks)
        self.cancel_btn.Disable()
        btn_sizer.Add(self.cancel_btn, 1, wx.EXPAND|wx.LEFT, 2)
        sizer.Add(btn_sizer,0,wx.EXPAND|wx.ALL,5)

        #进度条
        self.progress_bar = wx.Gauge(self,range=100)
        sizer.Add(self.progress_bar,0,wx.EXPAND|wx.LEFT|wx.RIGHT,5)
        #进度条文本
        self.progress_text = wx.StaticText(self,label="准备就绪")
        sizer.Add(self.progress_text,0,wx.LEFT|wx.TOP|wx.BOTTOM,5)

        # 结果显示框
        self.result_text = wx.TextCtrl(self, style=wx.TE_MULTILINE | wx.TE_READONLY)
        sizer.Add(self.result_text, 1, wx.EXPAND|wx.ALL, 5)

        # 设置布局
        self.SetSizer(sizer)
    
        #功能逻辑
        self.cancel_event = asyncio.Event()  # 用于取消任务的事件
        self.scan_task = None  # 保存扫描任务的变量
        # 创建事件循环并在新线程中运行
        self.loop = None
        self.loop_thread = None
        self._start_event_loop()# 启动事件循环

    def _start_event_loop(self):
        self.loop = asyncio.new_event_loop()  # 创建新的事件循环
        self.loop_thread = threading.Thread(target=self._run_loop,args=(self.loop,), daemon=True)  # 创建线程运行事件循环
        self.loop_thread.start()  # 启动线程

    def _run_loop(self,loop):
        asyncio.set_event_loop(loop)
        try:
            loop.run_forever()
        finally:
            loop.close()  # 确保事件循环在退出时被关闭
            logger.info("事件循环已关闭")

    def start_ping(self, event:asyncio.Event):# 开始Ping测试按钮事件处理函数
        '''
        开始Ping测试，获取用户输入的主机信息，并异步执行Ping任务。
        :param event: 事件对象，未使用
        由于需要在子线程中运行任务，所以需要使用asyncio.run_coroutine_threadsafe方法将异步任务提交到事件循环中
        并且需要在子线程代码中使用wx.CallAfter方法，这样可以实现线程安全的在主线程中更新GUI
        '''
        self.cancel_event.clear()# 清除取消事件，准备开始新的Ping任务
        self.cancel_btn.Enable()# 启用取消按钮
        self.start_ping_btn.Disable()# 禁用开始Ping按钮，防止重复点击
        self.host_inputbox.Disable()# 禁用主机输入框，防止重复输入
        self.result_text.Clear() # 清空结果显示框
        self.progress_bar.SetValue(0)  # 重置进度条
        self.progress_text.SetLabel("准备就绪")# 重置进度条文本

        # 获取用户输入的主机信息
        hosts_info = self.host_inputbox.GetValue()
        hosts_list = ipAddressCheck(hosts_info)# 检查主机信息是否有效

        if hosts_list is None or not hosts_list:
            wx.MessageBox("请输入正确的 IP 地址或 CIDR 块", "错误", wx.OK | wx.ICON_ERROR)
            self.start_ping_btn.Enable()
            self.host_inputbox.Enable()
            self.cancel_btn.Disable()
            return

        hosts_info = [str(host) for host in hosts_list]
        self.progress_text.SetLabel(f"准备测试 {len(hosts_info)} 个主机...")# 更新进度条文本

        #检查事件循环是否已初始化
        if self.loop is None or self.loop.is_closed():
            raise RuntimeError("事件循环未初始化或已关闭，请先调用_start_event_loop方法")

        # 提交异步Ping任务到事件循环，在同步代码中调用异步函数需要使用asyncio.run_coroutine_threadsafe方法，该方法第一个参数是异步方法，第二个参数是asyncio异步事件循环
        # 该方法返回一个concurrent.futures.Future对象，用于获取异步任务的结果
        self.scan_task = asyncio.run_coroutine_threadsafe(
            ping_network(
                hosts_info,
                self.cancel_event,
                self.update_task_progress,
                max_concurrent_tasks=10
                ),
            self.loop
        )
        self.scan_task.add_done_callback(self.on_scan_complete_threadsafe)
        #添加任务完成回调函数，用于在任务完成后更新GUI；回调函数会在调用的时候自动传入一个concurrent.futures.Future对象，用于获取任务的结果
        #因此在定义回调函数时，必须有一个参数，用于接收concurrent.futures.Future对象

    # 异步任务完成回调函数，用于扫描任务完成后更新GUI,只定义一个wx.CallAfter方法，调用另外一个方法来执行UI更新操作。
    # 之所以要定义两个方法，多一次调用就是为了分离功能，一个用于切换到主线程，一个用于在主线程中更新UI
    def on_scan_complete_threadsafe(self, future:Future):

        '''异步任务完成回调函数，用于扫描任务完成后更新GUI'''
        wx.CallAfter(self._on_scan_complete, future)#wx.CallAfter方法用于在主线程中调用异步任务完成回调函数，避免在子线程中更新GUI
    def _on_scan_complete(self, future:Future):
        '''扫描任务完成回调函数，用于在任务完成后更新GUI'''
        try:
            future.result()
            self.result_text.AppendText("\n扫描完成！")#扫描完成后更新结果文本框
            self.progress_text.SetLabel("扫描完成")#扫描完成后更新进程条文本
        except Exception as e:
            self.result_text.AppendText(f"\n扫描完成！\n错误信息：{e}")#扫描完成后更新结果文本框
            self.progress_text.SetLabel("扫描完成")
        finally:
            self._restore_ui_state()#恢复UI状态
            logger.info("扫描任务完成")


    def update_task_progress(self, result,completed,total):#传递给start_ping方法的更新结果函数
        '''更新结果显示，线程安全'''
        wx.CallAfter(self._update_task_progress,result,completed,total)

    def _update_task_progress(self,result,completed,total):#更新任务进度，内部方法
        self.result_text.AppendText(result+"\n")
        process = int((completed/total)*100) if total >0 else 0
        self.progress_bar.SetValue(process)#更新进度条
        self.progress_text.SetLabel(f"已完成{completed}/{total}")#更新进度文本

    
    def _restore_ui_state(self):
        '''恢复UI状态'''
        self.start_ping_btn.Enable()  # 启用开始Ping按钮
        self.host_inputbox.Enable()  # 启用主机输入框
        self.cancel_btn.Disable()  # 禁用取消按钮
        if not self.cancel_event.is_set():
            self.progress_text.SetLabel("准备就绪")
        else:
            self.progress_text.SetLabel("任务已取消")

    def cancel_tasks(self, event):# 取消Ping测试按钮事件处理函数
        '''
        取消当前Ping任务，并恢复UI状态。
        :param event: 事件对象,wx.Button使用bind方法绑定事件时，会自动传递事件对象
        '''
        async def _wait_for_cancellation():
            await asyncio.sleep(0.5)
            wx.CallAfter(self.progress_text.SetLabel,"任务取消完成")
            wx.CallAfter(self._restore_ui_state)
        if not self.scan_task or self.scan_task.done():
            return
        try:
            self.cancel_event.set()#设置取消事件，通知任务取消
            self.cancel_btn.Disable()
            self.progress_text.SetLabel("正在取消任务")
            #
            if self.loop and self.loop.is_running():
                asyncio.run_coroutine_threadsafe(_wait_for_cancellation(),self.loop)
            logger.info("已发送取消事件")
        except Exception as e:
            logger.error(f"取消任务时出错：{e}")
            wx.CallAfter(self._restore_ui_state)

if __name__ ==  "__main__":
    app = wx.App()
    frame = wx.Frame(None)
    frame.SetMinSize(wx.Size(800, 600))
    panel = wx.Panel(frame)
    sizer = wx.BoxSizer(wx.VERTICAL)
    pingTester = PingTester(panel)
    sizer.Add(pingTester,1,wx.EXPAND,5)#Add方法的第二个参数0表示控制或子sizer不会随着父容器的大小变化而变化，比例因子大于0时，表示控件或子sizer会根据比例因子的值来调整大小
    panel.SetSizer(sizer)
    frame.Show()
    frame.Center()
    app.MainLoop()