import os
import torch
import numpy as np
from detector import PatchCore
import warnings

warnings.filterwarnings("ignore")

class DetectionService:
    """异常检测服务"""
    
    def __init__(self, config):
        self.config = config
        self.detector = None
        self._initialize_detector()
    
    def _initialize_detector(self):
        """初始化检测器"""
        print("🚀 Initializing PCB Anomaly Detection System...")
        try:
            self.detector = PatchCore(self.config)
            self.detector.build_memory_bank('train_images/good')
            print("✅ Detection system initialized successfully!")
        except Exception as e:
            print(f"❌ Failed to initialize detection system: {e}")
            raise
    
    def is_ready(self):
        """检查服务是否就绪"""
        return self.detector is not None and self.detector.memory_bank is not None
    
    def process_image(self, image_path):
        """
        处理单张图像
        Args:
            image_path: 图像文件路径
        Returns:
            dict: 检测结果
        """
        if not self.is_ready():
            raise RuntimeError("Detection service is not ready")
        
        # 检测异常
        anomaly_score, anomaly_map, feat_size, original_size = self.detector.detect(image_path)
        
        # 查找显著区域
        best_bboxes = self._find_best_regions(anomaly_map, original_size, feat_size)
        
        # 生成可视化结果
        result_path, heatmap_path = self.detector.visualize_results(self.config.OUTPUT_DIR)
        
        return {
            'regions_count': int(len(best_bboxes)),
            'result_image': str(result_path),
            'heatmap_image': str(heatmap_path),
            'regions':best_bboxes
        }
    
    def _find_best_regions(self, anomaly_map, original_size, feat_size):
        """查找最佳异常区域"""
        bboxes = self.detector.get_bboxes(anomaly_map, feat_size, original_size)
        
        # 处理返回结果，统一转换为 x, y, width, height 格式
        processed_bboxes = []
        for bbox in bboxes:
            x1, y1, x2, y2 = bbox['bbox']
            x = int(x1)
            y = int(y1)
            width = int(x2) - int(x1)
            height = int(y2) - int(y1)
            
            processed_bboxes.append({
                'x': x,
                'y': y,
                'width': width,
                'height': height,
            })
        
        return processed_bboxes