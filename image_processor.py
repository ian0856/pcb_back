import numpy as np
from PIL import Image
import cv2
import io

class ImageProcessor:
    """图像处理工具类"""
    
    @staticmethod
    def image_to_bytes(image):
        """
        将PIL图像转换为字节流
        Args:
            image: PIL.Image对象
        Returns:
            bytes: 图像的字节数据
        """
        if image is None:
            return None
        
        try:
            img_byte_arr = io.BytesIO()
            image.save(img_byte_arr, format='JPEG', quality=95)
            return img_byte_arr.getvalue()
        except Exception as e:
            return None
    
    @staticmethod
    def bytes_to_image(image_bytes):
        """
        将字节流转换为PIL图像
        Args:
            image_bytes: 图像的字节数据
        Returns:
            PIL.Image对象
        """
        if image_bytes is None:
            return None
        
        try:
            return Image.open(io.BytesIO(image_bytes))
        except Exception as e:
            return None
    
    @staticmethod
    def create_cover_heatmap(original_image, heatmap_image):
        """
        创建热力图覆盖在原图上的图像
        Args:
            original_image: 原始PIL图像
            heatmap_image: 热力图PIL图像
        Returns:
            PIL.Image: 覆盖后的图像
        """
        try:
            # 确保两个图像尺寸相同
            if original_image.size != heatmap_image.size:
                heatmap_image = heatmap_image.resize(original_image.size)
            
            # 将PIL图像转换为numpy数组
            original_np = np.array(original_image)
            heatmap_np = np.array(heatmap_image)
            
            # 确保原始图像是RGB
            if len(original_np.shape) == 2:
                original_np = cv2.cvtColor(original_np, cv2.COLOR_GRAY2RGB)
            
            # 确保热力图是RGB
            if len(heatmap_np.shape) == 2:
                # 如果是灰度图，转换为热力图颜色
                heatmap_np = cv2.applyColorMap(heatmap_np, cv2.COLORMAP_JET)
                heatmap_np = cv2.cvtColor(heatmap_np, cv2.COLOR_BGR2RGB)
            
            # 调整热力图透明度（alpha blending）
            alpha = 0.6  # 热力图透明度
            beta = 1 - alpha
            
            # 混合图像
            cover_np = cv2.addWeighted(
                original_np.astype(np.float32),
                beta,
                heatmap_np.astype(np.float32),
                alpha,
                0
            ).astype(np.uint8)
            
            # 转换为PIL图像
            cover_image = Image.fromarray(cover_np)
            
            # 添加标题
            from PIL import ImageDraw, ImageFont
            draw = ImageDraw.Draw(cover_image)
            
            try:
                font = ImageFont.truetype("arial.ttf", 20)
            except:
                font = ImageFont.load_default()
            
            title = "Heatmap Overlay (Alpha: 60%)"
            draw.text((10, 10), title, fill='white', font=font)
            
            return cover_image
            
        except Exception as e:
            print(f"❌ 创建覆盖热力图失败: {e}")
            return None
    
    @staticmethod
    def read_image_file(file_path):
        """
        读取图像文件
        Args:
            file_path: 图像文件路径
        Returns:
            PIL.Image对象
        """
        try:
            return Image.open(file_path)
        except Exception as e:
            print(f"❌ 读取图像文件失败: {e}")
            return None
    
    @staticmethod
    def save_temp_image(image, file_path):
        """
        临时保存图像
        Args:
            image: PIL.Image对象
            file_path: 保存路径
        """
        try:
            image.save(file_path, format='JPEG', quality=95)
            return True
        except Exception as e:
            print(f"❌ 保存图像失败: {e}")
            return False