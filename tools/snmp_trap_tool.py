# encoding:utf-8
from utils import setup_logging,setup_sys_path
setup_sys_path()
logger = setup_logging()
from register_tool import register_tool
import wx
import asyncio
import threading
import wx.dataview as dv
from dataclasses import dataclass,field
from pysnmp.hlapi.v3arch.asyncio import (
    SnmpEngine, CommunityData, UdpTransportTarget,
    ContextData, UsmUserData,send_notification
)
from pysnmp.hlapi.v3arch.asyncio import (
    usmNoAuthProtocol,usmHMACMD5AuthProtocol,usmHMACSHAAuthProtocol,usmHMAC128SHA224AuthProtocol,usmHMAC192SHA256AuthProtocol,usmHMAC256SHA384AuthProtocol,usmHMAC384SHA512AuthProtocol,#认证协议
    usmNoPrivProtocol,usmDESPrivProtocol,usmAesCfb128Protocol,usmAesCfb192Protocol,usmAesCfb256Protocol,usm3DESEDEPrivProtocol,#加密协议
)
from pysnmp.smi.rfc1902 import ObjectIdentity, ObjectType
from pysnmp.proto.rfc1902 import OctetString, IpAddress,Integer32, Counter32, Gauge32, TimeTicks, Counter64
from pysnmp.proto import rfc1155
from pyasn1.type import univ 
from typing import Optional,List,Tuple,Dict,Any

GENERIC_TRAP = {
    "coldStart": "1.3.6.1.6.3.1.1.5.1",
    "warmStart": "1.3.6.1.6.3.1.1.5.2",
    "linkDown": "1.3.6.1.6.3.1.1.5.3",
    "linkUp": "1.3.6.1.6.3.1.1.5.4",
    "authenticationFailure": "1.3.6.1.6.3.1.1.5.5",
    "egpNeighborLoss": "1.3.6.1.6.3.1.1.5.6",
}

AUTHPROTOCOL = {
    "NoAuth":usmNoAuthProtocol,#无认证协议
    "HMACMD5":usmHMACMD5AuthProtocol,#HMAC-MD5认证协议
    "HMACSHA-1":usmHMACSHAAuthProtocol,#HMAC-SHA-1认证协议
    "HMACSHA-224":usmHMAC128SHA224AuthProtocol,#HMAC-SHA-224认证协议
    "HMACSHA-256":usmHMAC192SHA256AuthProtocol,#HMAC-SHA-256认证协议
    "HMACSHA-384":usmHMAC256SHA384AuthProtocol,#HMAC-SHA-384认证协议
    "HMACSHA-512":usmHMAC384SHA512AuthProtocol,#HMAC-SHA-512认证协议
}
PRIVPROTOCOL = {
    "NoPriv":usmNoPrivProtocol,#无加密协议
    "DES":usmDESPrivProtocol,#DES加密协议
    "AES-128-CFB":usmAesCfb128Protocol,#AES-128-CFB加密协议
    "AES-192-CFB":usmAesCfb192Protocol,#AES-192-CFB加密协议
    "AES-256-CFB":usmAesCfb256Protocol,#AES-256-CFB加密协议
    "3DES-EDE":usm3DESEDEPrivProtocol,#3DES-EDE加密协议
}

def time_validator(time:str):
    if time.isdigit() and int(time) >= 0:
        return int(time)
    else:
        raise ValueError("时间格式错误")
@dataclass
class PduParameter:
    #基本配置
    snmp_version:int = 2
    target_community:str = "public"
    target_host:str = "192.168.1.20"
    target_port:int = 162

    #SNMP变量绑定
    sysUptime:Optional[rfc1155.TimeTicks] = None
    snmp_trap_oid:Optional[univ.ObjectIdentifier] = None
    agent_ip:Optional[IpAddress]=None
    source_community:Optional[OctetString] = None
    enterprise_specific:Optional[univ.ObjectIdentifier] = None
    other_binds:Optional[Dict[str,Any]] = field(default_factory=dict)

    #snmpv3认证参数
    username:Optional[str] = None
    auth_password:Optional[str] = None
    priv_password:Optional[str] = None
    auth_protocol:Optional[str] = None
    priv_protocol:Optional[str] = None

    def __post_init__(self):
        #设置默认值
        if self.sysUptime is None:
            print("sysUptime默认值")
            self.sysUptime = rfc1155.TimeTicks(32768)
        if self.snmp_trap_oid is None:
            print("snmp_trap_oid默认值")
            self.snmp_trap_oid = univ.ObjectIdentifier("1.3.6.1.6.3.1.1.5.2")
        if self.agent_ip is None:
            print("agent_ip默认值")
            self.agent_ip = IpAddress("192.168.0.1")
        if self.source_community is None:
            print("source_community默认值")
            self.source_community = OctetString("public")
        if self.enterprise_specific is None:
            print("enterprise_specific默认值")
            self.enterprise_specific = univ.ObjectIdentifier("1.3.6.1.6.3.1.1.5.2")

def set_oid_var_binds(config:PduParameter):
    print("设置OID变量绑定")
    var_binds = []
    is_snmp_v1 = config.snmp_version == 1
    if config.sysUptime:
        var_binds.append(ObjectType(ObjectIdentity("1.3.6.1.2.1.1.3.0"),config.sysUptime))
    if config.snmp_trap_oid:
        var_binds.append(ObjectType(ObjectIdentity("1.3.6.1.6.3.1.1.4.1.0"),config.snmp_trap_oid))
    if is_snmp_v1 and config.agent_ip:
        var_binds.append(ObjectType(ObjectIdentity("1.3.6.1.6.3.18.1.3.0"),config.agent_ip))
    if is_snmp_v1 and config.source_community:
        var_binds.append(ObjectType(ObjectIdentity("1.3.6.1.6.3.18.1.2.0"),config.source_community))
    if is_snmp_v1 and config.enterprise_specific:
        var_binds.append(ObjectType(ObjectIdentity("1.3.6.1.6.3.18.1.4.0"),config.enterprise_specific))

    #处理其它绑定
    if config.other_binds:
        print("处理其它绑定")
        for oid,value in config.other_binds.items():
            var_binds.append(ObjectType(ObjectIdentity(oid),value))
    print(f"OID变量绑定：{var_binds}")
    return var_binds
    
async def send_snmp_trap(config:PduParameter):
    print("进行SNMP相关配置")
    if config.snmp_version not in [1,2,3]:
        print("SNMP版本号错误")
        return "SNMP版本号错误"
    
    if config.snmp_version == 3:
        if not config.username:
            print("用户名不能为空")
            return "用户名不能为空"
        if config.auth_password and config.auth_protocol !="" and len(config.auth_password) <8:
            print("认证密码长度不能小于8位")
            return "认证密码长度不能小于8位"
        if config.priv_password and config.priv_protocol !="" and len(config.priv_password) <8:
            print("隐私密码长度不能小于8位")
            return "隐私密码长度不能小于8位"
        if config.auth_password == "" and config.priv_password != "":
            print("不允许只有隐私密码，而没有认证加密")
            return "不允许只有隐私密码，而没有认证加密"
        if config.auth_password == "" and config.priv_password == "":
            print("无认证密码，无隐私密码")
            community = UsmUserData(config.username)
        elif config.auth_password != "" and config.priv_password == "":
            print(f"有认证密码，无隐私密码,认证密码：{config.auth_password},认证密码协议：{config.auth_protocol}。")
            community = UsmUserData(config.username,authKey=config.auth_password,authProtocol=config.auth_protocol)
        else:
            community = UsmUserData(config.username,config.auth_password,config.priv_password,authProtocol=config.auth_protocol,privProtocol=config.priv_protocol)
    else:
        mp_model = 0 if config.snmp_version == 1 else 1 if config.snmp_version == 2 else 2
        community = CommunityData(config.target_community,mpModel=mp_model)
    print(f"community:{community}")
    try:
        target = await UdpTransportTarget.create((config.target_host,config.target_port))
        print(f"目标地址：{target}")
    except Exception as e:
        print(f"创建目标地址失败：{e}")
        return "创建目标地址失败"
    var_binds = set_oid_var_binds(config)
    print(f"发送前确认var_binds:{var_binds}")

    #发送trap
    error_indication, _, _, _ = await send_notification(
        SnmpEngine(), community, target, ContextData(), "trap", *var_binds
    )

    if error_indication:
        print(f"❌ 发送失败：{error_indication}")
        return "发送失败"
    else:
        print("✅ SNMP Trap发送成功！")
        return "✅ SNMP Trap发送成功！"

class AddVariableDialog(wx.Dialog):
    '''
    用于添加变量绑定的对话框
    '''
    def __init__(self, parent):
        super().__init__(parent, title="添加变量绑定", size=wx.Size(400, 250))
        panel = wx.Panel(self)
        sizer = wx.BoxSizer(wx.VERTICAL)
        # OID输入
        oid_sizer = wx.BoxSizer(wx.HORIZONTAL)
        oid_label = wx.StaticText(panel, label="OID  :")
        self.oid_text = wx.TextCtrl(panel, value="1.3.6.1.2.1.1.1.0")
        oid_sizer.Add(oid_label, 0, wx.ALL | wx.EXPAND, 5)
        oid_sizer.Add(self.oid_text, 1, wx.ALL | wx.EXPAND, 5)
        # 值输入
        value_sizer = wx.BoxSizer(wx.HORIZONTAL)
        value_label = wx.StaticText(panel, label="值    :")
        self.value_text = wx.TextCtrl(panel, value="")
        value_sizer.Add(value_label, 0, wx.ALL | wx.EXPAND, 5)
        value_sizer.Add(self.value_text, 1, wx.ALL | wx.EXPAND, 5)
        # 类型选择
        type_sizer = wx.BoxSizer(wx.HORIZONTAL)
        type_label = wx.StaticText(panel, label="数据类型:")
        self.type_choice = wx.Choice(panel, choices=[
            "OctetString", "Integer", "OID", "IpAddress", 
            "Counter32", "Gauge32", "TimeTicks", "Counter64"
        ])
        self.type_choice.SetSelection(0)
        type_sizer.Add(type_label, 0, wx.ALL | wx.EXPAND, 5)
        type_sizer.Add(self.type_choice, 1, wx.ALL | wx.EXPAND, 5)

        # 按钮
        btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
        ok_btn = wx.Button(panel, wx.ID_OK, "确定")
        cancel_btn = wx.Button(panel, wx.ID_CANCEL, "取消")
        btn_sizer.Add(ok_btn, 0, wx.ALL, 5)
        btn_sizer.Add(cancel_btn, 0, wx.ALL, 5)
        #把OID输入部分、值输入部分、类型选择部分和按钮部分都添加到sizer中
        sizer.Add(oid_sizer, 0, wx.EXPAND | wx.ALL, 10)
        sizer.Add(value_sizer, 0, wx.EXPAND | wx.ALL, 10)
        sizer.Add(type_sizer, 0, wx.EXPAND | wx.ALL, 10)
        sizer.Add(btn_sizer, 0, wx.ALIGN_CENTER | wx.ALL, 10)
        panel.SetSizer(sizer)
        
    def get_values(self):
        """获取输入的值"""
        oid = self.oid_text.GetValue()
        value = self.value_text.GetValue()
        var_type = self.type_choice.GetStringSelection()
        return oid, value, var_type
@register_tool("SNMP类","SNMP Trap工具")
class SnmpTrapTool(wx.Panel):
    def __init__(self, parent):
        super().__init__(parent)

        main_sizer = wx.BoxSizer(wx.VERTICAL)
        self._init_snmptrap_target_box(main_sizer)
        self._init_snmp_community_params_box(main_sizer)
        self._init_setup_oid_params_box(main_sizer)
        self._init_operation_and_output_box(main_sizer)
        self.SetSizer(main_sizer)

        # 创建事件循环并在新线程中运行
        self.loop = None
        self.loop_thread = None
        #启动事件循环，用于异步任务的执行
        self._start_event_loop()
    def _start_event_loop(self):
        '''创建事件循环并在新线程中运行,多线程可以解决GUI阻塞问题，在子线程中使用异步执行IO操作'''
        self.loop = asyncio.new_event_loop()
        self.loop_thread = threading.Thread(target=self._run_loop,args=(self.loop,),daemon=True)
        self.loop_thread.start()

    def _run_loop(self,loop:asyncio.AbstractEventLoop):
        '''在新线程中运行事件循环'''
        asyncio.set_event_loop(loop)
        try:
            loop.run_forever()
        finally:
            loop.close()
            #logger.info("事件循环已关闭")

    def on_switch_version(self, event):
        selected_index = self.snmp_ver_choice.GetSelection()
        match selected_index:
            case 0:
                self.v3_sizer.ShowItems(False)
                self.v2c_sizer.ShowItems(True)
                self.v1_sizer.ShowItems(True)
            case 1:
                self.v3_sizer.ShowItems(False)
                self.v2c_sizer.ShowItems(True)
                self.v1_sizer.ShowItems(False)
            case 2:
                self.v3_sizer.ShowItems(True)
                self.v2c_sizer.ShowItems(False)
            case _:
                pass

        # if selected_index == 2:  # SNMPv3
        #     self.v2c_sizer.ShowItems(False)
        #     self.v3_sizer.ShowItems(True)
        # else:  # SNMPv1/v2c
        #     self.v2c_sizer.ShowItems(True)
        #     self.v3_sizer.ShowItems(False)
        self.Layout()

    def get_snmp_config(self):
        """获取所有SNMP配置信息"""
        var_type_map = {
            "OctetString": OctetString,
            "OID": univ.ObjectIdentifier,
            "IpAddress": IpAddress,
            "Counter32": Counter32,
            "Gauge32": Gauge32,
            "TimeTicks": rfc1155.TimeTicks,
            "Counter64": Counter64,
        }
        config = PduParameter()
        config.target_host = self.target_ip_text.GetValue()#目标IP
        config.target_port = int(self.target_port_text.GetValue())#目标端口
        snmp_version = self.snmp_ver_choice.GetStringSelection()#SNMP版本
        config.snmp_version = 1 if snmp_version == "SNMPv1" else 2 if snmp_version == "SNMPv2c" else 3
        config.target_community = self.community_text.GetValue()#团体名
        config.sysUptime = rfc1155.TimeTicks(self.sys_uptime_text.GetValue())#agent运行时间，
        config.agent_ip = IpAddress(self.agent_ip_text.GetValue())#agent IP，仅snmpv1需要
        config.source_community = OctetString(self.source_community_text.GetValue())#源团体名，仅snmpv1需要
        #config.enterprise_specific = univ.ObjectIdentifier(self.enterprise_specific_text.GetValue())#企业特定OID，仅snmpv1需要
        config.username = self.user_text.GetValue()#用户名，仅SNMPV3需要
        config.auth_password = self.auth_password_text.GetValue()#认证密码，仅SNMPV3需要
        config.auth_protocol = AUTHPROTOCOL[self.auth_password_choice.GetStringSelection()]#认证协议，仅SNMPV3需要
        config.priv_password = self.priv_password_text.GetValue()#隐私密码，仅SNMPV3需要
        config.priv_protocol = PRIVPROTOCOL[self.priv_password_choice.GetStringSelection()]#隐私协议，仅SNMPV3需要
        trap_choice = self.trap_type_choice.GetStringSelection()#TRAP OID
        if trap_choice in GENERIC_TRAP.keys():
            config.snmp_trap_oid = univ.ObjectIdentifier(GENERIC_TRAP[trap_choice])
            print(f"是通用trap，OID是：{config.snmp_trap_oid}")
        else:
            config.snmp_trap_oid = univ.ObjectIdentifier(self.specific_trap_text.GetValue())
            print(f"是特定trap，OID是：{config.snmp_trap_oid}")
        var_binds_list = {}#变量绑定列表
        for item in self.get_variable_bindings():
            var_type = var_type_map[item["type"]]
            var_binds_list[univ.ObjectIdentifier(item["oid"])] = var_type(item["value"])
        config.other_binds = var_binds_list
        print(f"多余变量绑定列表：{config.other_binds}")
        
        if config.snmp_version == 3:
            print("SNMPv3配置")
            del config.target_community
        else:
            print("SNMPv1/v2c配置")
            del config.username
            del config.auth_password
            del config.priv_password
        print(f"当前配置：{config}")
        self.log_text.AppendText(f"当前配置：{config}\n")
        return config

    def on_send_snmptrap(self, event):
        """根据传入的参数配置，发送SNMP Trap"""
        if self.specific_trap_text.GetValue() == "":
            wx.MessageBox("请输入特定TRAP OID", "警告", wx.OK | wx.ICON_WARNING)
            return
        if self.snmp_ver_choice.GetStringSelection() == "SNMPv3":
            if self.user_text.GetValue() == "":#用户名不能为空
                wx.MessageBox("请输入用户名", "警告", wx.OK | wx.ICON_WARNING)
                return
            if self.auth_password_choice.GetStringSelection() == "NoAuth" and self.priv_password_choice.GetStringSelection() == "NoPriv":
                self.auth_password_text.Clear()
                self.priv_password_text.Clear()
                print("既不加密也不认证")
            elif self.auth_password_choice.GetStringSelection() != "NoAuth" and self.priv_password_choice.GetStringSelection() == "NoPriv":
                self.priv_password_text.Clear()
                print("只加密不认证，清空认证的密码")
            elif self.auth_password_choice.GetStringSelection() == "NoAuth" and self.priv_password_choice.GetStringSelection() != "NoPriv":
                wx.MessageBox("有隐私密码，必须有认证密码", "警告", wx.OK | wx.ICON_WARNING)
                print("有隐私密码，必须有认证密码")
                return
            else:
                print("既加密，又认证")
                pass
            if self.auth_password_choice.GetStringSelection() != "NoAuth" and len(self.auth_password_text.GetValue()) <8:
                wx.MessageBox("认证密码长度不能小于8位", "警告", wx.OK | wx.ICON_WARNING)
                return 
            # elif self.auth_password_choice.GetStringSelection() == "NoAuth":#无认证密码，需要清空输入
            #     self.auth_password_text.Clear()
            #     pass
            # else:
            #     pass

            if self.priv_password_choice.GetStringSelection() != "NoPriv" and len(self.priv_password_text.GetValue()) <8:
                wx.MessageBox("隐私密码长度不能小于8位", "警告", wx.OK | wx.ICON_WARNING)
                return 
            # elif self.priv_password_choice.GetStringSelection() == "NoPriv":#无隐私密码，需要清空输入
            #     self.priv_password_text.Clear()
            #     pass
            # else:
            #     pass
        config = self.get_snmp_config()
        if self.loop is not None:
            future = asyncio.run_coroutine_threadsafe(send_snmp_trap(config), self.loop)
            result = future.result()
            wx.CallAfter(self.log_message, f"发送结果：{result}")
        else:
            wx.MessageBox("事件循环未初始化，无法发送SNMP Trap", "错误", wx.OK | wx.ICON_ERROR)

    def log_message(self, message):
        """向日志框添加消息"""
        self.log_text.AppendText(message + '\n')

    def on_add_variable(self, event):
        """添加新的变量绑定"""
        dialog = AddVariableDialog(self)
        if dialog.ShowModal() == wx.ID_OK:
            oid, value, var_type = dialog.get_values()
            self.var_bind_list.AppendItem([oid, value, var_type])
        dialog.Destroy()
    
    def on_trap_type_choice(self, event):
        """处理陷阱类型选择"""
        selected_index = self.trap_type_choice.GetSelection()
        match selected_index:
            case 0:
                self.specific_trap_text.SetValue("1.3.6.1.6.3.1.1.5.1")
                self.specific_trap_text.Enable(False)
            case 1:
                self.specific_trap_text.SetValue("1.3.6.1.6.3.1.1.5.2")
                self.specific_trap_text.Enable(False)
            case 2:
                self.specific_trap_text.SetValue("1.3.6.1.6.3.1.1.5.3")
                self.specific_trap_text.Enable(False)
            case 3:
                self.specific_trap_text.SetValue("1.3.6.1.6.3.1.1.5.4")
                self.specific_trap_text.Enable(False)
            case 4:
                self.specific_trap_text.SetValue("1.3.6.1.6.3.1.1.5.5")
                self.specific_trap_text.Enable(False)
            case 5:
                self.specific_trap_text.SetValue("1.3.6.1.6.3.1.1.5.6")
                self.specific_trap_text.Enable(False)
            case 6:
                self.specific_trap_text.SetValue("1.3.6.1.4.1.2011.5.25.219.2.1.1")#使用特定TRAP，需要先配置企业OID
                self.specific_trap_text.Enable(True)
        self.Layout()

    def on_remove_variable(self, event):
        """删除选中的变量绑定"""
        selected_items = self.var_bind_list.GetSelections()
        if not selected_items:
            wx.MessageBox("请先选择要删除的变量", "提示", wx.OK | wx.ICON_INFORMATION)
            return
        # 使用DeleteItem方法删除选中的行
        for item in reversed(selected_items):
            if item.IsOk():
                row = self.var_bind_list.ItemToRow(item)
                if row != -1:
                    self.var_bind_list.DeleteItem(row)

    def on_clear_variables(self, event):
        """清空所有变量绑定"""
        self.var_bind_list.DeleteAllItems()

    def get_variable_bindings(self):
        """获取所有变量绑定"""
        bindings = []
        for row in range(self.var_bind_list.GetItemCount()):
            oid = self.var_bind_list.GetTextValue(row, 0)
            value = self.var_bind_list.GetTextValue(row, 1)
            var_type = self.var_bind_list.GetTextValue(row, 2)
            bindings.append({"oid": oid, "value": value, "type": var_type})
        return bindings
    
    def _init_snmptrap_target_box(self,main_sizer):
        # 配置snmp trap目标主机及端口
        target_box = wx.StaticBox(self, label="目标地址配置")
        target_sizer = wx.StaticBoxSizer(target_box, wx.HORIZONTAL)
        target_ip_label = wx.StaticText(target_box, label="目标IP:")
        self.target_ip_text = wx.TextCtrl(target_box,value="192.168.0.1")  # 改为实例属性
        target_port_label = wx.StaticText(target_box, label="目标端口:")
        self.target_port_text = wx.TextCtrl(target_box,value="162")  # 改为实例属性
        target_sizer.Add(target_ip_label, 0, wx.ALL | wx.EXPAND, 5)
        target_sizer.Add(self.target_ip_text, 0, wx.ALL | wx.EXPAND, 5)
        target_sizer.Add(target_port_label, 0, wx.ALL | wx.EXPAND, 5)
        target_sizer.Add(self.target_port_text, 0, wx.ALL | wx.EXPAND, 5)
        main_sizer.Add(target_sizer, 0, wx.ALL | wx.EXPAND, 5)
    
    def _init_snmp_community_params_box(self,main_sizer):
        # 配置snmp trap版本信息、团体名、用户名、认证密码、隐私密码
        snmp_box = wx.StaticBox(self, label="SNMP版本")
        snmp_sizer = wx.StaticBoxSizer(snmp_box, wx.HORIZONTAL)
        # 版本选择及必填参数部分
        self.snmp_ver_choice = wx.Choice(snmp_box, choices=["SNMPv1", "SNMPv2c", "SNMPv3"])
        self.snmp_ver_choice.Bind(wx.EVT_CHOICE, self.on_switch_version)
        self.snmp_ver_choice.SetSelection(1)
        self.sys_uptime_label = wx.StaticText(snmp_box, label="sysUptime:")
        self.sys_uptime_text = wx.TextCtrl(snmp_box,value="12345")

        # SNMPv1/v2c控件
        self.community_label = wx.StaticText(snmp_box, label="团体名:")
        self.community_text = wx.TextCtrl(snmp_box, size=wx.Size(120, -1), value="public")
        # SNMPv1专属控件
        self.v1_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.agent_ip_label = wx.StaticText(snmp_box, label="代理IP:")
        self.agent_ip_text = wx.TextCtrl(snmp_box,value="192.168.0.1")
        self.source_community_label = wx.StaticText(snmp_box, label="源团体名:")
        self.source_community_text = wx.TextCtrl(snmp_box,value="public")
        self.v1_sizer.Add(self.agent_ip_label, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 5)
        self.v1_sizer.Add(self.agent_ip_text, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 5)
        self.v1_sizer.Add(self.source_community_label, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 5)
        self.v1_sizer.Add(self.source_community_text, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 5)

        # 创建水平布局的Sizer,用于SNMPv1/v2c
        self.v2c_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.v2c_sizer.Add(self.community_label, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 5)
        self.v2c_sizer.Add(self.community_text, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 5)
        self.v2c_sizer.Add(self.v1_sizer,0,wx.ALL | wx.ALIGN_CENTER_VERTICAL, 5)

        # SNMPv3专属控件
        self.user_label = wx.StaticText(snmp_box, label="用户名:")
        self.user_text = wx.TextCtrl(snmp_box, size=wx.Size(80, -1))
        self.auth_password_label = wx.StaticText(snmp_box, label="认证密码:")
        self.auth_password_choice = wx.Choice(snmp_box, choices=[choice for choice in AUTHPROTOCOL.keys()])
        self.auth_password_choice.SetSelection(0)
        #self.auth_password_choice.Bind(wx.EVT_CHOICE, self.on_switch_auth_password)
        self.auth_password_text = wx.TextCtrl(snmp_box, size=wx.Size(80, -1))
        self.priv_password_label = wx.StaticText(snmp_box, label="隐私密码:")
        self.priv_password_choice = wx.Choice(snmp_box, choices=[choice for choice in PRIVPROTOCOL.keys()])
        self.priv_password_choice.SetSelection(0)
        #self.priv_password_choice.Bind(wx.EVT_CHOICE, self.on_switch_priv_password)
        self.priv_password_text = wx.TextCtrl(snmp_box, size=wx.Size(80, -1))
        # 创建水平布局的Sizer,用于SNMPv3
        self.v3_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.v3_sizer.Add(self.user_label, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 5)
        self.v3_sizer.Add(self.user_text, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 5)
        self.v3_sizer.Add(self.auth_password_label, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 5)
        self.v3_sizer.Add(self.auth_password_choice, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 5)
        self.v3_sizer.Add(self.auth_password_text, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 5)
        self.v3_sizer.Add(self.priv_password_label, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 5)
        self.v3_sizer.Add(self.priv_password_choice, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 5)
        self.v3_sizer.Add(self.priv_password_text, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 5)
        
        
        
        # 都添加到当前box的sizer，再根据用户选择显示哪个版本的配置项
        snmp_sizer.Add(self.snmp_ver_choice, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 5)
        snmp_sizer.Add(self.sys_uptime_label, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 5)
        snmp_sizer.Add(self.sys_uptime_text, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 5)
        snmp_sizer.Add(self.v2c_sizer, 0, wx.ALL | wx.EXPAND, 5)
        snmp_sizer.Add(self.v3_sizer, 0, wx.ALL | wx.EXPAND, 5)
        # 初始显示，默认显示v2的
        self.v3_sizer.ShowItems(False)
        self.v1_sizer.ShowItems(False)
        main_sizer.Add(snmp_sizer, 0, wx.ALL | wx.EXPAND, 5)

    def _init_setup_oid_params_box(self,main_sizer):
        # 配置trap类型(即OID)和变量绑定，上中下三个部分，上边是trap类型选择，中间是变量绑定，下边是添加变量绑定按钮
        trap_box = wx.StaticBox(self, label="Trap类型和变量绑定")
        trap_sizer = wx.StaticBoxSizer(trap_box, wx.VERTICAL)#trap类型和变量绑定的总sizer，垂直布局，上半部分用于trap类型选择，中间部分用于变量绑定，下半部分用于添加变量绑定按钮
        trap_type_sizer = wx.BoxSizer(wx.HORIZONTAL)#上半部分的trap类型选择部分，水平布局
        trap_type_label = wx.StaticText(trap_box, label="Trap类型:")
        self.trap_type_choice = wx.Choice(trap_box, choices=[
            "coldStart", "warmStart", "linkDown", "linkUp",
            "authenticationFailure", "egpNeighborLoss", "enterpriseSpecific"
        ])
        self.trap_type_choice.Bind(wx.EVT_CHOICE, self.on_trap_type_choice)
        self.trap_type_choice.SetSelection(6)
        trap_type_sizer.Add(trap_type_label, 0, wx.ALL | wx.EXPAND, 5)#trap类型选择的标签
        trap_type_sizer.Add(self.trap_type_choice, 0, wx.ALL | wx.EXPAND, 5)#trap类型选择的下拉列表
        # 自定义的trap类型，需要手动输入trap oid
        specific_trap_label = wx.StaticText(trap_box, label="指定Trap值:")
        self.specific_trap_text = wx.TextCtrl(trap_box, value="", size=wx.Size(120, -1))
        trap_type_sizer.Add(specific_trap_label, 0, wx.ALL | wx.EXPAND, 5)
        trap_type_sizer.Add(self.specific_trap_text, 0, wx.ALL | wx.EXPAND, 5)
        
        # 变量绑定表格 (使用DataViewListCtrl)
        var_bind_sizer = wx.BoxSizer(wx.VERTICAL)#中间部分的变量绑定部分，垂直布局
        var_bind_lael = wx.StaticText(trap_box, label="变量绑定:")
        var_bind_sizer.Add(var_bind_lael, 0, wx.ALL | wx.EXPAND, 5)
        self.var_bind_list = dv.DataViewListCtrl(trap_box,size=wx.Size(300,200),style=dv.DV_HORIZ_RULES|dv.DV_VERT_RULES|dv.DV_MULTIPLE)
        self.var_bind_list.AppendTextColumn("OID", width=200)
        self.var_bind_list.AppendTextColumn("值", width=150)
        self.var_bind_list.AppendTextColumn("类型", width=100)
        # 添加一些默认的变量绑定
        self.var_bind_list.AppendItem(["1.3.6.1.2.1.1.5.0", "sysname", "OctetString"])
        var_bind_sizer.Add(self.var_bind_list,0,wx.EXPAND)
        
        # 变量绑定操作按钮
        var_bind_btn_sizer = wx.BoxSizer(wx.HORIZONTAL)#下半部分的按钮部分，水平布局
        self.add_var_btn = wx.Button(trap_box, label="添加变量")
        self.remove_var_btn = wx.Button(trap_box, label="删除变量")
        self.clear_vars_btn = wx.Button(trap_box, label="清空变量")
        # 绑定按钮事件
        self.add_var_btn.Bind(wx.EVT_BUTTON, self.on_add_variable)
        self.remove_var_btn.Bind(wx.EVT_BUTTON, self.on_remove_variable)
        self.clear_vars_btn.Bind(wx.EVT_BUTTON, self.on_clear_variables)
        #组装按钮
        var_bind_btn_sizer.Add(self.add_var_btn, 0, wx.ALL, 5)
        var_bind_btn_sizer.Add(self.remove_var_btn, 0, wx.ALL, 5)
        var_bind_btn_sizer.Add(self.clear_vars_btn, 0, wx.ALL, 5)
        
        #将上半部分的trap类型选择部分、中间部分的变量绑定部分、下半部分的按钮部分添加到trap_sizer中
        trap_sizer.Add(trap_type_sizer, 0, wx.EXPAND)
        trap_sizer.Add(var_bind_sizer, 0, wx.EXPAND)
        trap_sizer.Add(var_bind_btn_sizer, 0, wx.ALIGN_CENTER)
        main_sizer.Add(trap_sizer, 0, wx.ALL | wx.EXPAND, 5)

    def _init_operation_and_output_box(self,main_sizer):
        # 配置操作按钮与日志显示
        operator_box = wx.StaticBox(self, label="操作按钮与日志显示")
        operator_sizer = wx.StaticBoxSizer(operator_box, wx.VERTICAL)
        self.send_button = wx.Button(operator_box, label="发送Trap") 
        self.log_text = wx.TextCtrl(operator_box, style=wx.TE_MULTILINE | wx.TE_READONLY)  # 改为实例属性
        operator_sizer.Add(self.send_button, 1, wx.ALL | wx.EXPAND, 5)
        operator_sizer.Add(self.log_text, 9, wx.ALL | wx.EXPAND, 5)
        self.send_button.Bind(wx.EVT_BUTTON, self.on_send_snmptrap)
        main_sizer.Add(operator_sizer, 0, wx.ALL | wx.EXPAND, 5)



if __name__ == '__main__':
    app = wx.App()
    frame = wx.Frame(parent=None, title='SNMP Trap Tool')
    sizer = wx.BoxSizer(wx.VERTICAL)
    panel = wx.Panel(frame)
    snmp_trap_tool = SnmpTrapTool(panel)
    sizer.Add(snmp_trap_tool, 0, wx.ALL | wx.EXPAND, 5)
    panel.SetSizer(sizer)
    frame.Center()
    frame.SetSize(wx.Size(1000, 600))
    frame.Show()
    app.MainLoop()