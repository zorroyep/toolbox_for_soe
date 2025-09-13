
import wx
import threading
import asyncio
import websockets
import queue
import json
import time

command = {
    "1":"volume up",
    "2":"volume down",
    "3":"up",
    "4":"down",
    "5":"alt+f4",
    "6":"alt+tab",
    "7":"win+d",


}


class WebSocketServerFrame(wx.Frame):
    def __init__(self, parent, title):
        super(WebSocketServerFrame, self).__init__(parent, title=title, size=wx.Size(800, 600))
        
        # 服务器状态变量
        self.server_running = False
        self.server_thread = None
        self.server = None
        self.port = 8765  # 默认端口
        
        # 消息队列，用于后台线程与GUI线程通信
        self.message_queue = queue.Queue()
        
        # 创建UI
        self.InitUI()
        
        # 启动消息处理定时器
        self.timer = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, self.ProcessQueue, self.timer)
        self.timer.Start(100)  # 每100ms检查一次队列
        
        self.Centre()
        self.Show(True)
    
    def _run_loop(self):
        """在新线程中运行事件循环"""
        asyncio.set_event_loop(self.loop)
        try:
            self.loop.run_forever()
        finally:
            if not self.loop.is_closed():
                print("子线程事件循环关闭")
                self.loop.close()

    def StartServer(self):
        try:
            # 修复：当服务器未在运行时才启动
            if self.server_running:
                print("server already running")
                return
                
            # 定义客户端处理函数，确保正确接收websocket和path参数
            # 将原来的handle_client函数：
            # async def handle_client(websocket, path):
            #     await self.HandleClient(websocket, path)
            
            # 修改为：
            async def handle_client(websocket):
                await self.HandleClient(websocket)
            
            # 创建服务器实例 - 绑定到localhost而不是0.0.0.0
            async def start_server():
                self.server = await websockets.serve(
                    handle_client, 
                    "localhost",
                    self.port
                )
                self.server_running = True
                print("服务端实例已创建")
                
                # 保持服务器运行，直到收到停止指令或出现异常
                try:
                    if self.server is not None and hasattr(self.server, 'wait_closed'):
                        wait_closed = self.server.wait_closed()
                        # 仅在wait_closed为可等待对象且不是类型为"Never"时才await
                        if (
                            (asyncio.iscoroutine(wait_closed) or asyncio.isfuture(wait_closed) or callable(getattr(wait_closed, '__await__', None)))
                            and type(wait_closed).__name__ != "Never"
                        ):
                            await wait_closed
                        # 如果不是可等待对象或为Never，则不需要await，直接跳过
                        else:
                            pass  # wait_closed 不是 awaitable 或为Never时直接跳过
                except Exception as e:
                    print(f"服务器运行异常: {e}")
                    self.QueueMessage("log", f"服务器运行异常: {str(e)}")
                finally:
                    self.server_running = False
                    self.QueueMessage("status", "服务器已停止")
                    # 确保UI状态正确
                    wx.CallAfter(self.start_btn.Enable)
                    wx.CallAfter(self.stop_btn.Disable)
                    wx.CallAfter(self.port_ctrl.Enable)
            
            # 提交任务到事件循环
            future = asyncio.run_coroutine_threadsafe(start_server(), self.loop)
            print("服务器启动任务提交到事件循环")
            
            # 发送状态更新到GUI
            self.QueueMessage("status", f"服务器在 ws://localhost:{self.port} 上运行")
            
        except Exception as e:
            print(f"服务器启动异常:{e}")
            self.QueueMessage("log", f"服务器错误: {str(e)}")
            self.QueueMessage("status", "服务器启动失败")
            
            # 启动失败时的清理工作
            self.server_running = False
            # 确保UI状态正确
            wx.CallAfter(self.start_btn.Enable)
            wx.CallAfter(self.stop_btn.Disable)
            wx.CallAfter(self.port_ctrl.Enable)

    def OnStopServer(self, event):
        if self.server_running and self.server and self.loop and not self.loop.is_closed():
            self.server_running = False
            self.start_btn.Enable()
            self.stop_btn.Disable()
            self.port_ctrl.Enable()
            self.status_text.SetLabel("服务器停止中...")
            self.LogMessage("停止服务器...")
            
            # 通知服务器停止
            async def stop_server():
                if self.server is not None:
                    self.server.close()
                    try:
                        await self.server.wait_closed() # type: ignore
                    except AttributeError:
                        # For older versions of websockets that don't have wait_closed
                        pass
                    print("服务器已成功关闭")
                else:
                    print("服务器实例不存在，无法关闭")
            
            # 提交停止任务到事件循环
            asyncio.run_coroutine_threadsafe(stop_server(), self.loop)
    
    async def HandleClient(self, websocket):
        client_address = websocket.remote_address
        print(f"客户端连接: {client_address}")
        self.QueueMessage("log", f"客户端连接: {client_address}")
    
        try:
            await websocket.send("hello,连接已建立")
            async for message in websocket:
                print(f"收到来自 {client_address} 的消息: {message}")
                self.QueueMessage("log", f"收到来自 {client_address} 的消息: {message}")
                
                # 处理消息并生成响应
                response = self.ProcessMessage(message)
                self.QueueMessage("log", f"发送到 {client_address} 的响应: {response}")
                
                await websocket.send(response)
                print(f"发送到 {client_address} 的响应: {response}")
        except websockets.exceptions.ConnectionClosedOK:
            # 客户端正常关闭连接
            print(f"客户端 {client_address} 正常断开连接")
            self.QueueMessage("log", f"客户端正常断开连接: {client_address}")
        except websockets.exceptions.ConnectionClosedError:
            # 客户端异常关闭连接
            print(f"客户端 {client_address} 异常断开连接")
            self.QueueMessage("log", f"客户端异常断开连接: {client_address}")
        except websockets.exceptions.ConnectionClosed:
            # 兼容旧版本
            print(f"客户端 {client_address} 断开连接")
            self.QueueMessage("log", f"客户端断开连接: {client_address}")
        except Exception as e:
            print(f"与 {client_address} 通信出错: {str(e)}")
            self.QueueMessage("log", f"与 {client_address} 通信出错: {str(e)}")
    
    def ProcessMessage(self, message):
        """根据客户端消息生成响应"""
        # 确保消息是字符串类型
        message_str = str(message)
        try:
            # 尝试解析JSON消息
            data = json.loads(message_str)
            
            # 修复：先检查data是否为字典类型
            if isinstance(data, dict) and "command" in data:
                command = data["command"]
                if command == "ping":
                    print("收到ping命令")
                    return json.dumps({"response": "pong", "timestamp": time.time()})
                elif command == "echo":
                    print("收到echo命令")
                    return json.dumps({"response": data.get("data", ""), "type": "echo"})
                elif command == "time":
                    print("收到time命令")
                    return json.dumps({"response": time.ctime(), "type": "time"})
                else:
                    print(f"收到未知命令: {command}")
                    return json.dumps({"response": f"未知命令: {command}", "type": "error"})
            else:
                # 如果不是字典或没有command字段，直接返回收到的内容
                return f"服务器已接收: {message_str}"
        except json.JSONDecodeError:
            # 如果不是JSON，简单返回处理后的文本
            return f"服务器已接收: {message_str}"
        except Exception as e:
            # 捕获其他可能的异常
            print(f"处理消息时发生错误: {str(e)}")
            return f"处理消息时发生错误: {str(e)}"

    def ProcessQueue(self, event):
        """处理队列中的消息，更新GUI"""
        while not self.message_queue.empty():
            try:
                message_type, content = self.message_queue.get()
                if message_type == "log":
                    self.LogMessage(content)
                elif message_type == "status":
                    self.status_text.SetLabel(content)
                    self.LogMessage(content)
                self.message_queue.task_done()
            except Exception as e:
                print(f"处理队列消息出错: {e}")
    
    def LogMessage(self, message):
        """在日志区域添加消息"""
        timestamp = time.strftime("%H:%M:%S")
        self.log_text.AppendText(f"[{timestamp}] {message}\n")
        # 自动滚动到底部
        self.log_text.SetInsertionPointEnd()
    
    def QueueMessage(self, message_type, content):
        """将消息放入队列，用于后台线程与GUI线程通信"""
        self.message_queue.put((message_type, content))
    
    def OnStartServer(self, event):
        if not self.server_running:
            # 获取端口号
            try:
                self.port = int(self.port_ctrl.GetValue())
                if self.port < 1 or self.port > 65535:
                    raise ValueError
            except ValueError:
                wx.MessageBox("请输入有效的端口号 (1-65535)", "错误", wx.OK | wx.ICON_ERROR)
                return

            self.start_btn.Disable()
            self.stop_btn.Enable()
            self.port_ctrl.Disable()
            self.status_text.SetLabel("服务器启动中...")
            self.LogMessage("启动服务器...")
            
            # 在新线程中启动WebSocket服务器
            # 创建事件循环
            self.loop = asyncio.new_event_loop()
            # 在新线程中运行事件循环
            self.server_thread = threading.Thread(target=self._run_loop, daemon=True)
            self.server_thread.start()
            self.StartServer()
        print("服务器启动按钮点击")
    
    def InitUI(self):
        panel = wx.Panel(self)
        
        # 服务器设置区域
        settings_box = wx.BoxSizer(wx.HORIZONTAL)
        
        port_label = wx.StaticText(panel, label="端口:")
        settings_box.Add(port_label, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 5)
        
        self.port_ctrl = wx.TextCtrl(panel, value=str(self.port), size=wx.Size(80, -1))
        settings_box.Add(self.port_ctrl, 0, wx.ALL, 5)
        
        # 服务器控制区域
        control_box = wx.BoxSizer(wx.HORIZONTAL)
        
        self.start_btn = wx.Button(panel, label="启动服务器")
        self.Bind(wx.EVT_BUTTON, self.OnStartServer, self.start_btn)
        control_box.Add(self.start_btn, 0, wx.ALL, 5)
        
        self.stop_btn = wx.Button(panel, label="停止服务器")
        self.stop_btn.Disable()
        self.Bind(wx.EVT_BUTTON, self.OnStopServer, self.stop_btn)
        control_box.Add(self.stop_btn, 0, wx.ALL, 5)
        
        self.status_text = wx.StaticText(panel, label="服务器未运行")
        control_box.Add(self.status_text, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 5)
        
        # 日志显示区域
        log_box = wx.BoxSizer(wx.VERTICAL)
        
        log_label = wx.StaticText(panel, label="服务器日志:")
        log_box.Add(log_label, 0, wx.ALL, 5)
        
        self.log_text = wx.TextCtrl(panel, style=wx.TE_MULTILINE | wx.TE_READONLY | wx.HSCROLL)
        log_box.Add(self.log_text, 1, wx.ALL | wx.EXPAND, 5)
        
        # 主布局
        main_sizer = wx.BoxSizer(wx.VERTICAL)
        main_sizer.Add(settings_box, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP, 5)
        main_sizer.Add(control_box, 0, wx.EXPAND | wx.ALL, 5)
        main_sizer.Add(log_box, 1, wx.EXPAND | wx.ALL, 5)
        
        panel.SetSizer(main_sizer)
        print("UI初始化完成")

def main():
    app = wx.App()
    WebSocketServerFrame(None, title="WebSocket服务器")
    app.MainLoop()

if __name__ == "__main__":
    main()