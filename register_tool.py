#注册工具
'''
注册工具，将工具添加到工具合集
'''

from typing import Dict,Type
from wx import Panel
TOOL_LIST:Dict[str,Dict[str,Type[Panel]]]={}

def register_tool(category:str,tool_name:str):
    def decorator(tool_class:Type[Panel]):
        if category not in TOOL_LIST:
            TOOL_LIST[category]={}
        TOOL_LIST[category][tool_name]=tool_class
        return tool_class
    return decorator
