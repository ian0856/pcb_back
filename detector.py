import os
import sys
import numpy as np
import torch
import cv2
import faiss
from PIL import Image
from torchvision import transforms
from patchcore.common import NetworkFeatureAggregator, NearestNeighbourScorer, FaissNN

# 设置官方库路径
PATCHCORE_SRC = os.path.join(os.path.dirname(__file__), 'patchcore-inspection', 'src')
if PATCHCORE_SRC not in sys.path:
    sys.path.insert(0, PATCHCORE_SRC)

# 只导入确实存在的模块
try:
    from patchcore import backbones  # 注意是 backbones (复数)
    from patchcore import sampler
    from patchcore import patchcore
    print("✓ Successfully imported official PatchCore library")
except ImportError as e:
    print(f"✗ Import error: {e}")
    raise


class PatchCore:
    """
    基于官方Amazon PatchCore库的异常检测类
    """
    
    def __init__(self, config):
        self.config = config
        self.device = 'cuda' if torch.cuda.is_available() else 'cpu'
        
        # 配置参数
        self.image_size = getattr(config, 'IMAGE_SIZE', 224)
        self.backbone_name = getattr(config, 'BACKBONE', 'resnet50')
        self.layers_to_extract = getattr(config, 'LAYERS', ['layer2', 'layer3'])
        self.pretrain_embed_dimension = getattr(config, 'PRETRAIN_EMBED_DIM', 1024)
        self.target_embed_dimension = getattr(config, 'TARGET_EMBED_DIM', 1024)
        self.coreset_sampling_ratio = getattr(config, 'CORESET_SAMPLING_RATIO', 0.1)
        self.anomaly_scorer_num_nn = getattr(config, 'ANOMALY_SCORER_NUM_NN', 1)
        
        # 官方模型组件
        self.feature_aggregator = None
        self.memory_bank = None
        self.index = None
        self.anomaly_scorer = None
        
        # 预处理
        self.transform = transforms.Compose([
            transforms.Resize((self.image_size, self.image_size)),
            transforms.ToTensor(),
            transforms.Normalize(mean=[0.485, 0.456, 0.406],
                               std=[0.229, 0.224, 0.225])
        ])
        
        # 保存结果
        self.last_img_path = None
        self.last_anomaly_map = None
        self.last_feat_size = None
        self.last_original_size = None
        
        print(f"PatchCore initialized with device: {self.device}")
        print(f"  Backbone: {self.backbone_name}")
        print(f"  Image size: {self.image_size}")
    
    def build_memory_bank(self, normal_dir):
        """
        使用官方库构建记忆库
        """
        print(f"Building memory bank from: {normal_dir}")
        
        # 1. 创建backbone模型
        print("Loading backbone...")
        backbone_model = backbones.load(
            self.backbone_name
        )
        backbone_model.to(self.device)
        backbone_model.eval()
        
        # 2. 创建特征聚合器
        print("Creating feature aggregator...")
        self.feature_aggregator = NetworkFeatureAggregator(
            backbone=backbone_model,
            layers_to_extract_from=self.layers_to_extract,
            device=self.device
        )
        
        # 3. 创建异常评分器（稍后使用）
        print(f"Creating anomaly scorer...")
        self.anomaly_scorer = NearestNeighbourScorer(
            n_nearest_neighbours=self.anomaly_scorer_num_nn
        )
        
        # 4. 收集所有训练图像
        img_paths = []
        for root, dirs, files in os.walk(normal_dir):
            for file in files:
                if file.lower().endswith(('.jpg', '.JPG')):
                    img_paths.append(os.path.join(root, file))
        print(f"共有 {len(img_paths)} 张训练图像")
        
        # 5. 提取所有图像的特征
        all_features = []
        for idx, img_path in enumerate(img_paths):
            img = Image.open(img_path).convert('RGB')
            img_tensor = self.transform(img).unsqueeze(0).to(self.device)
            
            with torch.no_grad():
                features_dict = self.feature_aggregator(img_tensor)
            if 'layer2' in features_dict and 'layer3' in features_dict:
                f2 = features_dict['layer2']
                f3 = features_dict['layer3']
                
                # 调整 layer2 的尺寸以匹配 layer3
                f2 = torch.nn.functional.interpolate(
                    f2, 
                    size=f3.shape[-2:], 
                    mode='bilinear', 
                    align_corners=False
                )
                
                # 拼接特征
                fused_feature = torch.cat([f2, f3], dim=1)
                
                # 重塑为 [N, C] 形状
                B, C, H, W = fused_feature.shape
                fused_feature = fused_feature.permute(0, 2, 3, 1).reshape(-1, C)
                
                # 归一化
                fused_feature = torch.nn.functional.normalize(fused_feature, dim=1)
                
                all_features.append(fused_feature)
        
        # 6. 合并特征并应用coreset采样
        print("Applying coreset sampling...")
        features_tensor = torch.cat(all_features, dim=0)
        
        coreset_sampler = sampler.ApproximateGreedyCoresetSampler(
            percentage=self.coreset_sampling_ratio,
            device=self.device
        )
        self.memory_bank = coreset_sampler.run(features_tensor)
        
        print(f"Memory bank shape: {self.memory_bank.shape}")
        
        # 7. 构建FAISS索引
        print("Building FAISS index...")
        memory_bank_np = self.memory_bank.cpu().numpy()
        faiss.normalize_L2(memory_bank_np)
        self.index = faiss.IndexFlatIP(memory_bank_np.shape[1])
        self.index.add(memory_bank_np)
        
        print("✓ Memory bank built successfully")
        
        # 训练异常评分器
        print("Training anomaly scorer...")
        all_features_np = [f.cpu().numpy() for f in all_features]
        self.anomaly_scorer.fit(all_features_np)
        print("✓ Anomaly scorer trained successfully")
    
    def detect(self, img):
        """
        检测图像异常
        """
        if self.feature_aggregator is None:
            raise RuntimeError("Model not initialized. Call build_memory_bank first.")
        
        if self.index is None:
            raise RuntimeError("FAISS index not initialized. Call build_memory_bank first.")
        
        if isinstance(img, str):
            original_img = Image.open(img).convert('RGB')
            self.last_img_path = img
        else:
            original_img = img
            self.last_img_path = None
        
        original_size = original_img.size
        
        # 预处理
        img_tensor = self.transform(original_img).unsqueeze(0).to(self.device)
        
        # 提取特征
        with torch.no_grad():
            features_dict = self.feature_aggregator(img_tensor)
        
        # 合并 layer2 和 layer3 的特征（与训练时相同）
        if 'layer2' in features_dict and 'layer3' in features_dict:
            f2 = features_dict['layer2']
            f3 = features_dict['layer3']
            
            # 调整 layer2 的尺寸以匹配 layer3
            f2 = torch.nn.functional.interpolate(
                f2, 
                size=f3.shape[-2:], 
                mode='bilinear', 
                align_corners=False
            )
            
            # 拼接特征
            fused_feature = torch.cat([f2, f3], dim=1)
            
            # 重塑为 [N, C] 形状
            B, C, H, W = fused_feature.shape
            fused_feature = fused_feature.permute(0, 2, 3, 1).reshape(-1, C)
            
            # 归一化
            fused_feature = torch.nn.functional.normalize(fused_feature, dim=1)
            
            # 转换为 numpy 并归一化（确保）
            query_np = fused_feature.cpu().numpy()
            query_np = query_np / (np.linalg.norm(query_np, axis=1, keepdims=True) + 1e-8)
            
            # 直接使用 FAISS 索引搜索
            similarities, _ = self.index.search(query_np, 1)
            
            # 异常分数 = 1 - 相似度（相似度越高越正常）
            anomaly_map = (1.0 - similarities).reshape(H, W)
            
            # 后处理
            anomaly_map = cv2.GaussianBlur(anomaly_map, (5, 5), 0)
            anomaly_map = anomaly_map - np.percentile(anomaly_map, 5)
            anomaly_map = np.clip(anomaly_map, 0, None)
            if anomaly_map.max() > 0:
                anomaly_map = anomaly_map / anomaly_map.max()
            
            # 计算整体异常分数
            score = float(np.percentile(anomaly_map, 99))
            
            # 保存结果
            self.last_anomaly_map = anomaly_map
            self.last_feat_size = (H, W)
            self.last_original_size = original_size
            
            print(f"Detection completed - score: {score:.4f}")
            return score, anomaly_map, (H, W), original_size
        else:
            raise RuntimeError("Failed to extract features from image")
    
    def get_bboxes(self, anomaly_map, feat_size, original_size):
        """
        从异常图中提取边界框（改进版 - 更宽松）
        """
        H, W = feat_size
        orig_W, orig_H = original_size
        
        # 直接使用较低阈值，确保能检测到异常
        threshold = np.percentile(anomaly_map, 70)  # 降低到70
        
        # 如果异常图最大值很低，进一步降低阈值
        max_anomaly = np.max(anomaly_map)
        if max_anomaly < 0.5:
            threshold = np.percentile(anomaly_map, 50)  # 异常不明显时用中位数
        
        # 创建掩码
        mask = (anomaly_map > threshold).astype(np.uint8)
        
        # 如果掩码为空，直接用最大值的一半作为阈值
        if mask.sum() == 0:
            threshold = max_anomaly * 0.5
            mask = (anomaly_map > threshold).astype(np.uint8)
        
        # 形态学操作：先膨胀再腐蚀，连接相邻区域
        kernel = np.ones((5, 5), np.uint8)
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
        
        # 连通组件分析
        num, labels, stats, _ = cv2.connectedComponentsWithStats(mask)
        
        boxes = []
        for i in range(1, num):
            area = stats[i, cv2.CC_STAT_AREA]
            
            # 降低最小面积要求
            min_area = max(10, H * W * 0.001)  # 至少10个像素或0.1%
            if area < min_area:
                continue
            
            x, y, w, h = (
                stats[i, cv2.CC_STAT_LEFT],
                stats[i, cv2.CC_STAT_TOP],
                stats[i, cv2.CC_STAT_WIDTH],
                stats[i, cv2.CC_STAT_HEIGHT],
            )
            
            # 计算区域异常得分（取最大值，更敏感）
            region_mask = (labels == i)
            region_score = float(np.max(anomaly_map[region_mask]))
            
            # 转换到原始图像坐标
            x1 = int(x * orig_W / W)
            y1 = int(y * orig_H / H)
            x2 = int((x + w) * orig_W / W)
            y2 = int((y + h) * orig_H / H)
            
            # 确保坐标在图像范围内
            x1 = max(0, x1)
            y1 = max(0, y1)
            x2 = min(orig_W, x2)
            y2 = min(orig_H, y2)
            
            boxes.append({
                "bbox": (x1, y1, x2, y2),
                "score": region_score,
                "center": ((x1 + x2) // 2, (y1 + y2) // 2),
                "area": (x2 - x1) * (y2 - y1)
            })
        
        # 如果没有找到框，直接使用整个热力图中最亮的区域
        if not boxes:
            # 找到异常值最大的位置
            max_idx = np.unravel_index(np.argmax(anomaly_map), anomaly_map.shape)
            y, x = max_idx
            
            # 创建以最大点为中心的框
            box_h = max(20, H // 8)
            box_w = max(20, W // 8)
            
            x1 = max(0, x - box_w // 2)
            y1 = max(0, y - box_h // 2)
            x2 = min(W, x + box_w // 2)
            y2 = min(H, y + box_h // 2)
            
            x1_orig = int(x1 * orig_W / W)
            y1_orig = int(y1 * orig_H / H)
            x2_orig = int(x2 * orig_W / W)
            y2_orig = int(y2 * orig_H / H)
            
            boxes = [{
                "bbox": (x1_orig, y1_orig, x2_orig, y2_orig),
                "score": float(anomaly_map[y, x]),
                "center": ((x1_orig + x2_orig) // 2, (y1_orig + y2_orig) // 2),
                "area": (x2_orig - x1_orig) * (y2_orig - y1_orig)
            }]
        
        # 按得分排序返回所有框（不过滤）
        return sorted(boxes, key=lambda x: x["score"], reverse=True)[:3]
    
    def visualize_results(self, output_dir):
        """
        保存可视化结果
        """
        os.makedirs(output_dir, exist_ok=True)
        
        if self.last_img_path is None:
            raise RuntimeError("No image processed. Call detect() first.")
        
        # 读取原始图像
        img = cv2.imread(self.last_img_path)
        if img is None:
            raise RuntimeError(f"Cannot read image: {self.last_img_path}")
        
        img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        H, W = img.shape[:2]
        
        # 调整异常图大小
        amap = cv2.resize(self.last_anomaly_map, (W, H))
        
        # 归一化
        amap_norm = (amap - amap.min()) / (amap.max() + 1e-8)
        
        # 创建热力图
        heatmap = cv2.applyColorMap((amap_norm * 255).astype(np.uint8), cv2.COLORMAP_JET)
        heatmap = cv2.cvtColor(heatmap, cv2.COLOR_BGR2RGB)
        
        # 半透明叠加
        alpha = 0.6
        overlay = cv2.addWeighted(img, 1 - alpha, heatmap, alpha, 0)
        
        # 绘制边界框
        boxes = self.get_bboxes(self.last_anomaly_map, self.last_feat_size, self.last_original_size)
        for b in boxes:
            x1, y1, x2, y2 = b["bbox"]
            cv2.rectangle(overlay, (x1, y1), (x2, y2), (0, 255, 0), 2)
            text = f"{b['score']:.2f}"
            cv2.putText(overlay, text, (x1, y1 - 5),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
        
        # 保存结果
        heatmap_path = os.path.join(output_dir, "heatmap.png")
        cv2.imwrite(heatmap_path, cv2.cvtColor(heatmap, cv2.COLOR_RGB2BGR))
        
        result_path = os.path.join(output_dir, "result.png")
        cv2.imwrite(result_path, cv2.cvtColor(overlay, cv2.COLOR_RGB2BGR))
        
        print(f"Results saved to:\n  - Heatmap: {heatmap_path}\n  - Result: {result_path}")
        return result_path, heatmap_path