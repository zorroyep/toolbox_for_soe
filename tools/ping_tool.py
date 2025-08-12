#encoding:utf-8
#  ping测试工具
from tools.utils import setup_logging, setup_sys_path
setup_sys_path()  # 设置系统路径
logger = setup_logging()  # 设置日志记录器
import wx
import asyncio
import threading
import subprocess
import signal
from tools.utils import ipAddressCheck

from register_tool import register_tool
from asyncio import FIRST_COMPLETED, wait


# 异步Ping测试
async def ping_host(host, cancel_event, timeout=5):
    """
    异步Ping指定主机，支持超时和取消。
    
    :param host: 要Ping的主机地址
    :param cancel_event: 用于取消Ping任务的事件对象
    :param timeout: 超时时间(秒)
    :return: 包含Ping结果的字符串
    """
    if cancel_event.is_set():
        return None

    try:
        # 设置ping命令参数
        if hasattr(subprocess, 'CREATE_NEW_PROCESS_GROUP'):  # Windows系统
            proc = await asyncio.create_subprocess_exec(
                'ping', '-n', '1', '-w', str(timeout * 1000), host,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
        else:  # 类Unix系统
            proc = await asyncio.create_subprocess_exec(
                'ping', '-c', '1', '-W', str(timeout), host,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

        # 同时等待进程完成和取消事件
        done, pending = await wait(
            [asyncio.create_task(proc.wait()), asyncio.create_task(cancel_event.wait())],
            return_when=FIRST_COMPLETED
        )

        # 如果取消事件已触发，终止进程
        if cancel_event.is_set():
            if proc.returncode is None:  # 进程仍在运行
                try:
                    # 使用更温和的方式终止进程
                    proc.terminate()
                    try:
                        await asyncio.wait_for(proc.wait(), timeout=2.0)
                    except asyncio.TimeoutError:
                        # 如果terminate不起作用，再强制kill
                        try:
                            proc.kill()
                            await proc.wait()
                        except ProcessLookupError:
                            pass  # 进程已经不存在
                except ProcessLookupError:
                    # 进程已经不存在
                    pass
                except Exception as e:
                    logger.warning(f"终止Ping进程 {host} 时出错: {e}")
            return f"{host} 测试已取消"

        # 读取输出内容
        stdout_data, stderr_data = await proc.communicate()
        
        # 将字节转换为字符串
        stdout_str = stdout_data.decode('gbk', errors='ignore').strip() if stdout_data else ""
        stderr_str = stderr_data.decode('gbk', errors='ignore').strip() if stderr_data else ""
        
        # 分析输出内容判断是否真正连通
        is_reachable = False
        
        # 检查标准输出中是否有成功ping通的标志
        if stdout_str:
            # 查找成功ping通的关键字：bytes from、time=、ttl=
            success_indicators = [
                "bytes from",
                "time=",
                "ttl=",
                "ms",
                "icmp_seq="
            ]
            is_reachable = any(indicator.lower() in stdout_str.lower() for indicator in success_indicators)
        
        # 检查错误输出中是否有网络不可达的信息
        if stderr_str:
            unreachable_indicators = [
                "unreachable",
                "timeout",
                "failure",
                "destination host unreachable",
                "request timed out",
                "100% packet loss"
            ]
            is_unreachable = any(indicator.lower() in stderr_str.lower() for indicator in unreachable_indicators)
            if is_unreachable:
                is_reachable = False
        
        # 如果返回码为0但输出为空，可能是ping命令本身的问题
        if proc.returncode == 0 and not stdout_str and not stderr_str:
            is_reachable = False
            
        # 根据实际连通性返回结果
        if is_reachable:
            # 提取关键信息
            lines = stdout_str.split('\n')
            summary_line = next((line for line in lines if 'packets transmitted' in line.lower()), '')
            time_line = next((line for line in lines if 'time=' in line.lower()), '')
            
            result_msg = f"{host} 可以Ping通"
            if summary_line:
                result_msg += f" ({summary_line.strip()})"
            elif time_line:
                result_msg += f" ({time_line.strip()})"
            else:
                result_msg += f" ({stdout_str.strip()})"
                
            logger.info(f"{host} 可以Ping通，输出: {stdout_str}")
            return result_msg
        else:
            # 提取错误信息
            error_info = stderr_str if stderr_str else stdout_str
            if not error_info:
                error_info = "网络不可达或无响应"
            
            result_msg = f"{host} 无法Ping通"
            if error_info and len(error_info) < 100:  # 限制错误信息长度
                result_msg += f" ({error_info.strip()})"
                
            logger.info(f"{host} 无法Ping通，错误: {error_info}")
            return result_msg
            
    except asyncio.TimeoutError:
        return f"{host} 测试超时"
    except Exception as e:
        logger.error(f"Ping {host} 时发生错误: {e}")
        return f"Ping {host} 时发生错误: {e}"


# 异步Ping网络
async def ping_network(hosts_info, cancel_event, result_callback, progress_callback, max_concurrent=10):
    """
    并发Ping多个主机，支持进度反馈。
    
    :param hosts_info: 主机列表
    :param cancel_event: 取消事件
    :param result_callback: 结果回调函数
    :param progress_callback: 进度回调函数
    :param max_concurrent: 最大并发数
    :return: 所有结果的列表
    """
    all_results = []
    total = len(hosts_info)
    completed = 0
    
    # 分批处理主机，控制并发数量
    try:
        for i in range(0, total, max_concurrent):
            if cancel_event.is_set():
                break
                
            batch = hosts_info[i:i+max_concurrent]
            tasks = [asyncio.create_task(ping_host(host, cancel_event)) for host in batch]
            
            try:
                # 等待一批任务完成
                for future in asyncio.as_completed(tasks):
                    if cancel_event.is_set():
                        # 取消所有剩余任务
                        for task in tasks:
                            if not task.done():
                                task.cancel()
                        break
                        
                    try:
                        result = await future
                        if result:
                            result_callback(result)
                            all_results.append(result)
                    except asyncio.CancelledError:
                        # 任务被取消，跳过
                        pass
                        
                    completed += 1
                    progress_callback(completed, total)
            except Exception as e:
                logger.error(f"处理批次时出错: {e}")
                # 确保取消所有任务
                for task in tasks:
                    if not task.done():
                        task.cancel()
                break
    except KeyboardInterrupt:
        # 捕获Ctrl+C，优雅退出
        logger.info("收到键盘中断信号，正在清理任务...")
        cancel_event.set()
    except Exception as e:
        logger.error(f"ping_network发生错误: {e}")
    finally:
        # 确保所有任务都被取消
        cancel_event.set()
    
    return all_results


@register_tool("网络类", "PING工具")
class PingTester(wx.Panel):
    def __init__(self, parent):
        super().__init__(parent)
        
        # 设置中文字体支持
        font = wx.Font(10, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL)
        self.SetFont(font)

        sizer = wx.BoxSizer(wx.VERTICAL)

        # 主机输入框
        host_label = wx.StaticText(self, label="主机（可输入IP或CIDR，多个用逗号分隔）：")
        sizer.Add(host_label, 0, wx.EXPAND | wx.ALL, 5)
        self.host_inputbox = wx.TextCtrl(self)
        sizer.Add(self.host_inputbox, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 5)

        # 选项设置
        options_sizer = wx.BoxSizer(wx.HORIZONTAL)
        
        # 超时设置
        timeout_label = wx.StaticText(self, label="超时(秒)：")
        options_sizer.Add(timeout_label, 0, wx.ALIGN_CENTER_VERTICAL | wx.LEFT, 5)
        self.timeout_ctrl = wx.SpinCtrl(self, value="5", min=1, max=30)
        options_sizer.Add(self.timeout_ctrl, 0, wx.ALL, 5)
        
        # 并发数设置
        concurrent_label = wx.StaticText(self, label="并发数：")
        options_sizer.Add(concurrent_label, 0, wx.ALIGN_CENTER_VERTICAL | wx.LEFT, 5)
        self.concurrent_ctrl = wx.SpinCtrl(self, value="10", min=1, max=50)
        options_sizer.Add(self.concurrent_ctrl, 0, wx.ALL, 5)
        
        sizer.Add(options_sizer, 0, wx.EXPAND, 5)

        # 按钮区域
        btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
        
        # Ping测试开始按钮
        self.start_ping_btn = wx.Button(self, label="开始Ping测试")
        self.start_ping_btn.Bind(wx.EVT_BUTTON, self.start_ping)
        btn_sizer.Add(self.start_ping_btn, 1, wx.EXPAND | wx.RIGHT, 2)

        # 任务取消按钮
        self.cancel_btn = wx.Button(self, label="取消")
        self.cancel_btn.Bind(wx.EVT_BUTTON, self.cancelTask)
        self.cancel_btn.Disable()
        btn_sizer.Add(self.cancel_btn, 1, wx.EXPAND | wx.LEFT, 2)
        
        sizer.Add(btn_sizer, 0, wx.EXPAND | wx.ALL, 5)

        # 进度条
        self.progress = wx.Gauge(self, range=100)
        sizer.Add(self.progress, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 5)
        
        # 进度文本
        self.progress_text = wx.StaticText(self, label="准备就绪")
        sizer.Add(self.progress_text, 0, wx.LEFT | wx.TOP | wx.BOTTOM, 5)

        # 结果显示框
        self.result_text = wx.TextCtrl(self, style=wx.TE_MULTILINE | wx.TE_READONLY)
        sizer.Add(self.result_text, 1, wx.EXPAND | wx.ALL, 5)
        
        self.SetSizer(sizer)

        self.cancel_event = asyncio.Event()  # 用于取消任务的事件
        self.scan_task = None  # 保存扫描任务的变量
        self.loop = None
        self.loop_thread = None
        
        # 启动事件循环线程
        self._start_event_loop()
        
        # 绑定窗口关闭事件
        self.Bind(wx.EVT_WINDOW_DESTROY, self.on_destroy)

    def _start_event_loop(self):
        """启动事件循环线程"""
        self.loop = asyncio.new_event_loop()
        self.loop_thread = threading.Thread(
            target=self._run_loop, 
            args=(self.loop,), 
            daemon=True
        )
        self.loop_thread.start()

    def _run_loop(self, loop):
        """在新线程中运行事件循环"""
        asyncio.set_event_loop(loop)
        try:
            loop.run_forever()
        finally:
            loop.close()
            logger.info("事件循环已关闭")

    def start_ping(self, event):
        """开始Ping测试"""
        self.cancel_event.clear()
        self.cancel_btn.Enable()
        self.start_ping_btn.Disable()
        self.host_inputbox.Disable()
        self.result_text.Clear()
        self.progress.SetValue(0)
        
        # 获取用户输入
        hosts_info = self.host_inputbox.GetValue().strip()
        timeout = self.timeout_ctrl.GetValue()
        max_concurrent = self.concurrent_ctrl.GetValue()
        
        # 验证输入并解析主机列表
        hosts_list = ipAddressCheck(hosts_info)
        if hosts_list is None or not hosts_list:
            wx.MessageBox("请输入正确的 IP 地址或 CIDR 块", "错误", wx.OK | wx.ICON_ERROR)
            self.start_ping_btn.Enable()
            self.host_inputbox.Enable()
            self.cancel_btn.Disable()
            return

        hosts_info = [str(host) for host in hosts_list]
        self.progress_text.SetLabel(f"准备测试 {len(hosts_info)} 个主机...")

        # 检查事件循环是否已初始化
        if self.loop is None:
            raise RuntimeError("事件循环未初始化")
        # 提交异步Ping任务到事件循环
        self.scan_task = asyncio.run_coroutine_threadsafe(
            ping_network(
                hosts_info, 
                self.cancel_event, 
                self.update_result,
                self.update_progress,
                max_concurrent
            ),
            self.loop
        )
        self.scan_task.add_done_callback(self._on_scan_complete_threadsafe)

    def _on_scan_complete_threadsafe(self, future):
        """线程安全的扫描完成回调"""
        wx.CallAfter(self.on_scan_complete, future)

    def update_result(self, result):
        """更新结果显示（线程安全）"""
        wx.CallAfter(self.result_text.AppendText, result + "\n")

    def update_progress(self, completed, total):
        """更新进度条（线程安全）"""
        progress = int((completed / total) * 100) if total > 0 else 0
        wx.CallAfter(self.progress.SetValue, progress)
        wx.CallAfter(
            self.progress_text.SetLabel, 
            f"已完成 {completed}/{total} 个主机测试"
        )

    def on_scan_complete(self, future):
        """扫描完成处理"""
        try:
            # 检查是否有异常
            future.result()
        except asyncio.CancelledError:
            self.result_text.AppendText("\n任务已取消\n")
            self.progress_text.SetLabel("任务已取消")
        except Exception as e:
            logger.error(f"扫描过程中发生错误: {e}")
            self.result_text.AppendText(f"\n发生错误: {str(e)}\n")
            self.progress_text.SetLabel("测试失败")
        finally:
            # 确保界面状态总是正确恢复
            wx.CallAfter(self._restore_ui_state)
    
    def _restore_ui_state(self):
        """恢复界面状态"""
        try:
            self.start_ping_btn.Enable()
            self.host_inputbox.Enable()
            self.cancel_btn.Disable()
            if not self.cancel_event.is_set():
                self.progress_text.SetLabel("测试完成")
        except Exception as e:
            logger.error(f"恢复界面状态时出错: {e}")

    def cancelTask(self, event):
        """取消当前任务"""
        if not self.scan_task or self.scan_task.done():
            return
            
        try:
            self.cancel_event.set()
            self.cancel_btn.Disable()
            self.progress_text.SetLabel("正在取消任务...")
            
            # 强制唤醒事件循环，确保取消事件立即生效
            if self.loop and self.loop.is_running():
                self.loop.call_soon_threadsafe(lambda: None)
            
            logger.info("用户取消了Ping测试任务")
            
        except Exception as e:
            logger.error(f"取消任务时出错: {e}")
            # 确保UI状态恢复
            wx.CallAfter(self._restore_ui_state)

    def on_destroy(self, event):
        """窗口关闭时清理资源"""
        if self.loop and self.loop.is_running():
            self.loop.call_soon_threadsafe(self.loop.stop)
        
        if self.loop_thread and self.loop_thread.is_alive():
            self.loop_thread.join(timeout=1.0)
            
        event.Skip()


if __name__ == "__main__":
    import signal
    
    def signal_handler(signum, frame):
        """处理Ctrl+C信号"""
        logger.info("收到中断信号，程序正在退出...")
        # 不立即退出，让wxPython正常处理关闭事件
        
    # 设置信号处理器
    signal.signal(signal.SIGINT, signal_handler)
    
    try:
        app = wx.App()
        frame = wx.Frame(None, title="Ping测试工具")
        frame.SetMinSize(wx.Size(600, 500))
        panel = wx.Panel(frame)
        sizer = wx.BoxSizer(wx.VERTICAL)
        pingTester = PingTester(panel)
        sizer.Add(pingTester, 1, wx.EXPAND, 5)
        panel.SetSizer(sizer)
        frame.Show()
        frame.Center()
        app.MainLoop()
    except KeyboardInterrupt:
        logger.info("程序被用户中断")
    except Exception as e:
        logger.error(f"程序运行出错: {e}")