import os
import numpy as np
from werkzeug.utils import secure_filename
import json

def allowed_file(filename, allowed_extensions={'png', 'jpg', 'jpeg', 'bmp', 'gif'}):
    """检查文件扩展名是否允许"""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in allowed_extensions

def save_uploaded_file(file, upload_folder):
    """保存上传的文件"""
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        filepath = os.path.join(upload_folder, filename)
        file.save(filepath)
        return filepath
    return None
def convert_to_serializable(obj):
    """
    将对象转换为JSON可序列化的格式
    """
    if isinstance(obj, (np.integer, np.int32, np.int64)):
        return int(obj)
    elif isinstance(obj, (np.floating, np.float32, np.float64)):
        return float(obj)
    elif isinstance(obj, np.ndarray):
        return obj.tolist()
    elif isinstance(obj, (list, tuple)):
        return [convert_to_serializable(item) for item in obj]
    elif isinstance(obj, dict):
        return {key: convert_to_serializable(value) for key, value in obj.items()}
    elif isinstance(obj, set):
        return list(obj)
    elif hasattr(obj, '__dict__'):
        return convert_to_serializable(obj.__dict__)
    else:
        return obj

class JSONEncoder(json.JSONEncoder):
    """自定义JSON编码器，处理NumPy类型"""
    def default(self, obj):
        return convert_to_serializable(obj)