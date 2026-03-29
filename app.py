from flask import Flask, send_file, jsonify
from flask_swagger_ui import get_swaggerui_blueprint
from flask_cors import CORS
import warnings
import atexit
import io

from config import Config
from services.detection_service import DetectionService
from services.database_service import DatabaseService
from api.routes import register_routes
from utils import JSONEncoder
from image_processor import ImageProcessor

warnings.filterwarnings("ignore")

class PCBDetectionApp:
    """PCB检测应用类"""
    
    def __init__(self):
        self.app = None
        self.detection_service = None
        self.database_service = None
        self._initialize()
    
    def _initialize(self):
        """初始化应用和服务"""
        # 初始化配置
        Config.ensure_directories()
        
        # 创建Flask应用
        self.app = Flask(__name__)
        self.app.config['MAX_CONTENT_LENGTH'] = Config.MAX_CONTENT_LENGTH
        
        CORS(self.app)
        
        # 设置自定义JSON编码器
        self.app.json_encoder = JSONEncoder
        
        # 初始化检测服务
        self._initialize_detection_service()
        
        # 初始化数据库服务
        self._initialize_database_service()
        
        # 设置Swagger UI
        self._setup_swagger()
        
        # 注册路由
        self._register_routes()
        
        # 注册退出处理
        self._register_cleanup()
    
    def _initialize_detection_service(self):
        """初始化检测服务"""
        try:
            self.detection_service = DetectionService(Config)
        except Exception as e:
            self.detection_service = None
    
    def _initialize_database_service(self):
        """初始化数据库服务"""
        try:
            self.database_service = DatabaseService()
        except Exception as e:
            self.database_service = None
    
    def _setup_swagger(self):
        """设置Swagger UI"""
        swaggerui_blueprint = get_swaggerui_blueprint(
            Config.SWAGGER_URL,
            Config.API_URL,
            config={
                'app_name': "PCB Anomaly Detection API",
                'docExpansion': 'none',
                'operationsSorter': 'alpha'
            }
        )
        self.app.register_blueprint(swaggerui_blueprint, url_prefix=Config.SWAGGER_URL)
    
    def _register_routes(self):
        """注册路由"""
        # 使用修改后的register_routes，传递服务实例
        register_routes(self.app, self.detection_service, self.database_service)
        
        # ========== 新增：服务状态检查路由 ==========
        @self.app.route('/service-status', methods=['GET'])
        def service_status():
            """服务状态检查接口"""
            detection_status = {
                'initialized': self.detection_service is not None,
                'ready': self.detection_service.is_ready() if self.detection_service else False,
                'service': 'Detection Service'
            }
            
            database_status = {
                'initialized': self.database_service is not None,
                'available': self.database_service.is_available() if self.database_service else False,
                'service': 'Database Service'
            }
            
            return jsonify({
                'success': True,
                'detection': detection_status,
                'database': database_status,
                'overall': {
                    'operational': (self.detection_service is not None and 
                                   self.detection_service.is_ready()),
                    'message': 'Some services may be unavailable' if 
                               (self.detection_service is None or self.database_service is None) 
                               else 'All services operational'
                }
            })
        
        # ========== 新增：图像下载接口 ==========
        @self.app.route('/database/image/<int:log_id>/<image_type>', methods=['GET'])
        def get_log_image(log_id, image_type):
            """获取日志中的图像数据"""
            if not self.database_service or not self.database_service.is_available():
                return jsonify({
                    'success': False,
                    'message': 'Database not available'
                }), 503
            
            try:
                # 从数据库获取图像数据
                query = f"""
                    SELECT {image_type} as image_data 
                    FROM detection_log 
                    WHERE id = %s
                """
                
                result = self.database_service.execute_query(query, (log_id,))
                
                if not result or not result[0]:
                    return jsonify({
                        'success': False,
                        'message': f'Image not found for log #{log_id}'
                    }), 404
                
                # 安全地获取图像数据
                row = result[0]
                if isinstance(row, dict):
                    image_bytes = row.get('image_data')
                elif isinstance(row, tuple):
                    image_bytes = row[0] if len(row) > 0 else None
                else:
                    image_bytes = None
                
                if not image_bytes:
                    return jsonify({
                        'success': False,
                        'message': f'Image data is empty for log #{log_id}'
                    }), 404
                
                # 确定MIME类型
                mime_type = 'image/jpeg'
                
                # 发送图像
                return send_file(
                    io.BytesIO(image_bytes),
                    mimetype=mime_type,
                    as_attachment=False,
                    download_name=f'log_{log_id}_{image_type}.jpg'
                )
                
            except Exception as e:
                return jsonify({
                    'success': False,
                    'message': f'Failed to get image: {str(e)}'
                }), 500
    
    def _register_cleanup(self):
        """注册清理函数"""
        def cleanup():
            if self.database_service:
                self.database_service.close()
        
        atexit.register(cleanup)
    
    def print_startup_info(self):
        """打印启动信息"""
        
        print(f"🔗 一切就绪，立即开始: http://localhost:5000{Config.SWAGGER_URL}")
    def run(self, host='0.0.0.0', port=5000, debug=True):
        """运行应用"""
        self.print_startup_info()
        self.app.run(host=host, port=port, debug=debug)

def create_app():
    """创建Flask应用（用于工厂模式）"""
    pcb_app = PCBDetectionApp()
    return pcb_app.app, pcb_app.detection_service, pcb_app.database_service

def main():
    """主函数"""
    pcb_app = PCBDetectionApp()
    pcb_app.run(host='0.0.0.0', port=5000, debug=True)

if __name__ == '__main__':
    main()