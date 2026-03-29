import os
import torch
import numpy as np
from detector import PatchCore
from utils import analyze_anomaly_score, get_detection_summary
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
        
        print(f"📥 Processing image: {os.path.basename(image_path)}")
        
        # 检测异常
        anomaly_score, anomaly_map, original_size, feat_size = self.detector.detect(image_path)
        
        print(f"📊 Basic detection info:")
        print(f"  • Anomaly Score: {anomaly_score:.4f}")
        print(f"  • Image Size: {original_size[0]}x{original_size[1]}")
        
        # 查找显著区域
        best_bboxes = self._find_best_regions(anomaly_map, original_size, feat_size)
        
        # 生成可视化结果
        result_path, heatmap_path = self.detector.visualize_results(self.config.OUTPUT_DIR)
        
        # 分析结果
        anomaly_analysis = analyze_anomaly_score(anomaly_score)
        detection_summary = get_detection_summary(anomaly_map, best_bboxes)
        
        # 确保返回可序列化数据
        serializable_bboxes = []
        for bbox in best_bboxes:
            x1, y1, x2, y2 = bbox['bbox']
            center_x, center_y = bbox['center']
            
            serializable_bboxes.append({
                'bbox': (int(x1), int(y1), int(x2), int(y2)),
                'score': float(bbox['score']),
                'area': int(bbox['area']),
                'center': (int(center_x), int(center_y))
            })
        
        return {
            'anomaly_score': float(anomaly_analysis['score']),
            'anomaly_level': anomaly_analysis['level'],
            'anomaly_message': anomaly_analysis['message'],
            'regions_count': int(len(best_bboxes)),
            'result_image': str(result_path),
            'heatmap_image': str(heatmap_path),
            'detection_summary': detection_summary,
            'regions': serializable_bboxes,
            'original_size': (int(original_size[0]), int(original_size[1]))
        }
    
    def _find_best_regions(self, anomaly_map, original_size, feat_size):
        """查找最佳异常区域"""
        best_bboxes = []
        best_config = None
        
        # 尝试预设的配置
        for percentile, min_ratio in self.config.DETECTION_CONFIGS:
            print(f"\n  Testing config: percentile={percentile}, min_ratio={min_ratio}")
            bboxes = self.detector.get_bboxes(anomaly_map, feat_size, original_size)
            
            if bboxes:
                print(f"    Found {len(bboxes)} regions")
                if not best_bboxes or (1 <= len(bboxes) <= 3):
                    best_bboxes = bboxes
                    best_config = (percentile, min_ratio)
                    if 1 <= len(bboxes) <= 3:
                        print(f"    ✓ Good config: {len(bboxes)} regions found")
                        break
        
        # 如果没有找到区域，使用更宽松的配置
        if not best_bboxes:
            print(f"\n⚠️  No regions found with strict thresholds, trying more lenient...")
            bboxes = self.detector.get_bboxes(anomaly_map, feat_size, original_size)
            best_bboxes = bboxes
        
        print(f"\n📊 Final regions found: {len(best_bboxes)}")
        
        return best_bboxes