import os

class Config:
    # 模型权重路径
    WEIGHTS_PATH = './resnet18-5c106cde.pth'
    
    # 正常图像目录
    NORMAL_IMAGES_DIR = "./train_images/good"
    
    # 输出目录
    OUTPUT_DIR = "./outputs"
    
    # 上传目录
    UPLOAD_FOLDER = "./temp_uploads"
    
    # 检测参数
    DETECTION_CONFIGS = [
        (98, 0.03),  # 高阈值，大区域
        (95, 0.02),  # 中等阈值
        (90, 0.01),  # 低阈值，小区域
    ]
    
    # Flask配置
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB
    
    # Swagger配置
    SWAGGER_URL = '/api/docs'
    API_URL = '/swagger.json'
    
    # MySQL数据库配置（简化版） - 修复属性名称
    MYSQL_HOST = 'localhost'  # 改为MYSQL_HOST，保持一致
    MYSQL_PORT = 3306
    MYSQL_USER = 'root'
    MYSQL_PASSWORD = 'cy050127'
    MYSQL_DATABASE = 'pdb'
    MYSQL_CHARSET = 'utf8mb4'
    
    # 连接超时设置
    MYSQL_CONNECT_TIMEOUT = 10
    MYSQL_READ_TIMEOUT = 30
    
    @staticmethod
    def ensure_directories():
        """确保所有必要的目录都存在"""
        directories = [
            Config.OUTPUT_DIR,
            Config.UPLOAD_FOLDER,
            os.path.dirname(Config.WEIGHTS_PATH)
        ]
        
        for directory in directories:
            if directory:  # 确保目录路径不为空
                os.makedirs(directory, exist_ok=True)