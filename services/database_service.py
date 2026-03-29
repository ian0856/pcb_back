import logging
from database.connection import DatabaseConnection
from datetime import datetime
from image_processor import ImageProcessor

logger = logging.getLogger(__name__)

class DatabaseService:
    """数据库服务类 - 仅提供查询功能"""
    
    def __init__(self):
        self.db = DatabaseConnection()
        self.image_processor = ImageProcessor()
        self._initialize()
    
    def _initialize(self):
        """初始化数据库连接"""
        if self.db.connect():
            # 测试连接
            self.db.test_connection()
    
    def is_available(self):
        """检查数据库是否可用"""
        return self.db.is_connected()
    
    def get_db_status(self):
        """获取数据库状态"""
        return {
            'connected': self.db.is_connected(),
            'host': self.db.config.MYSQL_HOST,
            'port': self.db.config.MYSQL_PORT,
            'database': self.db.config.MYSQL_DATABASE
        }
    
    def execute_query(self, query, params=None):
        """执行查询语句"""
        if not self.is_available():
            return None
        
        try:
            return self.db.execute_query(query, params)
        except Exception as e:
            logger.error(f"执行查询失败: {e}")
            return None
    def save_detection_log(self, detection_data):
        """
        保存检测日志到detection_log表
        
        Args:
            detection_data: dict，包含以下字段：
                - upload_image_path: 上传图像文件路径
                - output_image_path: 标注结果图像路径
                - heatmap_image_path: 热力图图像路径
                - original_image: PIL.Image对象（原始图像）
                - output_image: PIL.Image对象（标注图像）
                - heatmap_image: PIL.Image对象（热力图）
                - points: regions数组JSON对象
        Returns:
            dict: 保存结果，包含success和message
        """
        if not self.is_available():
            return {'success': False, 'message': '数据库不可用'}
        
        try:

            points = detection_data.get('points', '')
            
            # 读取图像文件
            upload_image = self.image_processor.read_image_file(detection_data.get('upload_image_path'))
            output_image = self.image_processor.read_image_file(detection_data.get('output_image_path'))
            heatmap_image = self.image_processor.read_image_file(detection_data.get('heatmap_image_path'))
            
            if not all([upload_image, output_image, heatmap_image]):
                logger.error("❌ 无法读取所有图像文件")
                return {'success': False, 'message': '无法读取图像文件'}
            
            # 创建覆盖热力图
            cover_heatmap = self.image_processor.create_cover_heatmap(upload_image, heatmap_image)
            
            if not cover_heatmap:
                logger.error("❌ 创建覆盖热力图失败")
                return {'success': False, 'message': '创建覆盖热力图失败'}
            
            # 转换图像为字节流
            upload_bytes = self.image_processor.image_to_bytes(upload_image)
            output_bytes = self.image_processor.image_to_bytes(output_image)
            clean_heatmap_bytes = self.image_processor.image_to_bytes(heatmap_image)
            cover_heatmap_bytes = self.image_processor.image_to_bytes(cover_heatmap)
            
            if not all([upload_bytes, output_bytes, clean_heatmap_bytes, cover_heatmap_bytes]):
                logger.error("❌ 图像转字节失败")
                return {'success': False, 'message': '图像转字节失败'}
            
            # 准备插入数据
            upload_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            status = 'success'
            
            # 执行插入
            query = """
                INSERT INTO detection_log (
                    upload, upload_time, status, 
                    output, clean_heatmap, cover_heatmap, points
                ) VALUES (%s, %s, %s, %s, %s, %s, %s)
            """
            
            params = (
                upload_bytes,           # upload (longblob)
                upload_time,           # upload_time (datetime)
                status,                # status (varchar)
                output_bytes,          # output (longblob)
                clean_heatmap_bytes,   # clean_heatmap (longblob)
                cover_heatmap_bytes,    # cover_heatmap (longblob)
                points
            )
            
            result = self.execute_query(query, params)
            
            if result:
                # 安全地获取affected_rows和last_id
                if isinstance(result, dict):
                    affected_rows = result.get('affected_rows', 0)
                    last_id = result.get('last_id', 0)
                else:
                    affected_rows = 0
                    last_id = 0
                
                if affected_rows > 0:
                    logger.info(f"✅ 检测日志保存成功，ID: {last_id}")
                    
                    # 清理临时图像对象
                    del upload_image, output_image, heatmap_image, cover_heatmap
                    del upload_bytes, output_bytes, clean_heatmap_bytes, cover_heatmap_bytes
                    
                    return {
                        'success': True, 
                        'message': '保存成功',
                        'log_id': last_id,
                        'upload_time': upload_time
                    }
                else:
                    logger.error("❌ 插入数据库失败，影响行数为0")
                    return {'success': False, 'message': '插入数据库失败'}
            else:
                logger.error("❌ 插入数据库失败，返回结果为None")
                return {'success': False, 'message': '插入数据库失败'}
                
        except Exception as e:
            logger.error(f"❌ 保存检测日志失败: {e}")
            import traceback
            traceback.print_exc()
            return {'success': False, 'message': f'保存失败: {str(e)}'}
    
    # ========== 查询方法 ==========
    
    def get_all_detection_logs(self):
        """
        获取detection_log表所有数据
        
        Returns:
            list: 所有日志记录列表，包含BLOB数据
        """
        if not self.is_available():
            return []
        
        try:
            query = """
                SELECT id, upload_time, status, 
                       upload, output, clean_heatmap, cover_heatmap
                FROM detection_log 
                ORDER BY upload_time DESC
            """
            
            result = self.execute_query(query)
            
            if result:
                formatted_result = []
                for row in result:
                    if isinstance(row, dict):
                        # 处理字典类型结果
                        formatted_result.append({
                            'id': row.get('id'),
                            'upload_time': row.get('upload_time'),
                            'status': row.get('status'),
                            'upload': row.get('upload'),
                            'output': row.get('output'),
                            'clean_heatmap': row.get('clean_heatmap'),
                            'cover_heatmap': row.get('cover_heatmap')
                        })
                    elif isinstance(row, tuple):
                        # 处理元组类型结果
                        formatted_result.append({
                            'id': row[0] if len(row) > 0 else None,
                            'upload_time': row[1] if len(row) > 1 else None,
                            'status': row[2] if len(row) > 2 else None,
                            'upload': row[3] if len(row) > 3 else None,
                            'output': row[4] if len(row) > 4 else None,
                            'clean_heatmap': row[5] if len(row) > 5 else None,
                            'cover_heatmap': row[6] if len(row) > 6 else None
                        })
                return formatted_result
            return []
            
        except Exception as e:
            logger.error(f"获取所有检测日志失败: {e}")
            return []
    
    def get_detection_log_by_id(self, log_id):
        """
        根据ID获取指定检测日志
        
        Args:
            log_id: 日志ID
        Returns:
            dict: 日志信息，包含BLOB数据
        """
        if not self.is_available():
            return None
        
        try:
            query = """
                SELECT id, upload_time, status, 
                       upload, output, clean_heatmap, cover_heatmap
                FROM detection_log 
                WHERE id = %s
            """
            
            result = self.execute_query(query, (log_id,))
            
            if result and result[0]:
                row = result[0]
                if isinstance(row, dict):
                    return {
                        'id': row.get('id'),
                        'upload_time': row.get('upload_time'),
                        'status': row.get('status'),
                        'upload': row.get('upload'),
                        'output': row.get('output'),
                        'clean_heatmap': row.get('clean_heatmap'),
                        'cover_heatmap': row.get('cover_heatmap')
                    }
                elif isinstance(row, tuple):
                    return {
                        'id': row[0] if len(row) > 0 else None,
                        'upload_time': row[1] if len(row) > 1 else None,
                        'status': row[2] if len(row) > 2 else None,
                        'upload': row[3] if len(row) > 3 else None,
                        'output': row[4] if len(row) > 4 else None,
                        'clean_heatmap': row[5] if len(row) > 5 else None,
                        'cover_heatmap': row[6] if len(row) > 6 else None
                    }
            return None
            
        except Exception as e:
            logger.error(f"获取检测日志失败: {e}")
            return None
    def close(self):
        """关闭数据库连接"""
        self.db.disconnect()