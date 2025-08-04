from pathlib import Path
import sys

def register_file_path():
    '''
    把当前文件所在目录添加到系统路径中
    '''
    current_file = Path(__file__).resolve() #当前文件的绝对路径
    current_dir = current_file.parent.parent #当前文件的父目录
    if str(current_dir) not in sys.path:
        sys.path.append(str(current_dir)) #添加到系统路径中
        print(f"已将目录{current_dir}添加到系统路径中")
    else:
        print(f"目录{current_dir}已在系统路径中，无需重复添加")

register_file_path()  #调用注册方法，确保当前目录在系统路径中