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

def analyze_anomaly_score(score):
    """分析异常分数"""
    if score > 10.0:
        level = "HIGH ANOMALY"
        message = "Score > 10.0"
    elif score > 5.0:
        level = "MEDIUM ANOMALY"
        message = "5.0 < Score <= 10.0"
    elif score > 2.0:
        level = "LOW ANOMALY"
        message = "2.0 < Score <= 5.0"
    else:
        level = "VERY LOW ANOMALY"
        message = "Score <= 2.0"
    
    return {
        'level': level,
        'message': message,
        'score': float(score)  # 确保转换为Python float
    }

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

def get_detection_summary(anomaly_map, bboxes):
    """获取检测摘要"""
    norm_map = (anomaly_map - anomaly_map.min()) / (anomaly_map.max() - anomaly_map.min() + 1e-8)
    
    summary = {
        'total_pixels': int(norm_map.size),
        'anomaly_regions': len(bboxes),
        'regions': []
    }
    
    # 区域详细信息
    for i, bbox_info in enumerate(bboxes):
        x1, y1, x2, y2 = bbox_info['bbox']
        
        # 确保所有坐标都是Python原生类型
        center_x, center_y = bbox_info['center']
        
        summary['regions'].append({
            'id': i + 1,
            'bbox': [int(x1), int(y1), int(x2), int(y2)],  # 转换为Python int
            'score': float(bbox_info['score']),  # 转换为Python float
            'area': int(bbox_info['area']),  # 转换为Python int
            'center': [int(center_x), int(center_y)]  # 转换为Python int列表
        })
    
    return summary

class JSONEncoder(json.JSONEncoder):
    """自定义JSON编码器，处理NumPy类型"""
    def default(self, obj):
        return convert_to_serializable(obj)