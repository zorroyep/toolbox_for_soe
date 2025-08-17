'''
一对一socket服务端
'''
from utils import setup_logging,setup_sys_path
setup_sys_path() #设置系统路径
logger = setup_logging()  # 设置日志记录器

import wx
import threading
import socket
from typing import Callable
from register_tool import register_tool

def run_server_daemon(run_flag:threading.Event, update_result:Callable):
    '''
    服务端线程函数
    :param run_flag: 线程运行标志
    :param update_result: 更新结果到文本框的函数
    :return: None
    '''
    server_socket = socket.socket(socket.AF_INET,socket.SOCK_STREAM)
    server_socket.bind(("127.0.0.1",8888))
    server_socket.listen(1)
    server_socket.settimeout(1)
    logger.info("服务端启动")
    while run_flag.is_set():
        try:
            conn,client_addr = server_socket.accept()
            logger.info(f"客户端{client_addr}连接成功")
            while True:#添加内层循环以持续接收数据
                data = conn.recv(1024)
                if data:
                    logger.info(f"客户端{client_addr}发送数据:{data}")
                    update_result(f"收到客户端{client_addr}数据:{data}")
                    conn.send("hello".encode())
                else:
                    logger.info(f"客户端{client_addr}断开连接")
                    break
            conn.close()
        except socket.timeout:
            pass
    server_socket.close()
    logger.info("服务端关闭")
@register_tool("网络类","socket服务端")
class SocketServerTool(wx.Panel):
    def __init__(self,parent:wx.Frame):
        super().__init__(parent)

        #1，创建主布局器
        server_sizer = wx.BoxSizer(wx.VERTICAL)
        #2，操作区
        operation_area = wx.StaticBox(self,label="操作区")
        operation_area_sizer = wx.StaticBoxSizer(operation_area,wx.HORIZONTAL)
        #端口输入
        self.port_input = wx.TextCtrl(self)
        operation_area_sizer.Add(self.port_input,1,wx.ALL,5)
        self.port_input.SetValue("8888")
        #启动按钮
        self.start_btn = wx.Button(self,label="启动")
        self.start_btn.Bind(wx.EVT_BUTTON,self.on_start_server)
        operation_area_sizer.Add(self.start_btn,0,wx.ALL,5)
        #取消按钮
        self.stop_btn = wx.Button(self,label="取消")
        self.stop_btn.Bind(wx.EVT_BUTTON,self.on_stop_server)
        operation_area_sizer.Add(self.stop_btn,0,wx.ALL,5)
        #添加到主布局器
        server_sizer.Add(operation_area_sizer,0,wx.ALL,5)

        #3，数据输出区
        output_area = wx.StaticBox(self,label="数据输出区")
        output_area_sizer = wx.StaticBoxSizer(output_area,wx.VERTICAL)
        self.output_text = wx.TextCtrl(self,style=wx.TE_READONLY|wx.TE_MULTILINE,size=wx.Size(300,200))
        output_area_sizer.Add(self.output_text,1,wx.ALL,5)
        #添加到主布局器
        server_sizer.Add(output_area_sizer,0,wx.ALL,5)
        
        #4，设置布局器
        self.SetSizer(server_sizer)

        #5，初始化操作，
        self.stop_btn.Disable()#初始化取消按钮为禁用状态
        self.run_server_flag = threading.Event()#服务端是否运行标志
        self.run_server_task = None#服务端线程

    def on_start_server(self,event):
        '''
        启动服务端
        '''
        self.start_btn.Disable()#禁用启动按钮
        self.stop_btn.Enable()#启用取消按钮
        self.run_server_task = threading.Thread(target=run_server_daemon,args=(self.run_server_flag,self._update_result))
        self.run_server_task.start()
        self.run_server_flag.set()#设置服务端运行标志
        logger.info("服务线程启动")

    def on_stop_server(self,event):
        '''
        停止服务端
        '''
        if self.run_server_task and self.run_server_task.is_alive():
            self.run_server_flag.clear()#清除服务端运行标志
            self.run_server_task.join()#等待服务端线程结束
            logger.info("服务端线程已结束")
        self.stop_btn.Disable()#禁用取消按钮
        self.start_btn.Enable()#启用启动按钮

    def _update_result(self,result):
        #更新结果到文本框，给子线程调用，CallAfter确保在主线程更新
        wx.CallAfter(self.update_result,result)
    def update_result(self,result):
        self.output_text.AppendText(result)
        self.output_text.AppendText("\n")


if __name__ == "__main__":
    app = wx.App()
    frame = wx.Frame(parent=None,title="socket服务端")
    tool = SocketServerTool(frame)
    frame.SetMinSize(wx.Size(300,300))
    frame.Center()
    frame.Show()
    app.MainLoop()


