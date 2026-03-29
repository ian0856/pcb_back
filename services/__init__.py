import logging
from datetime import datetime
from database.connection import DatabaseConnection
from image_processor import ImageProcessor

logger = logging.getLogger(__name__)

class DatabaseService:
    """数据库服务类"""
    
    def __init__(self):
        self.db = DatabaseConnection()
        self.image_processor = ImageProcessor()
        self._initialize()
    
    def _initialize(self):
        """初始化数据库连接"""
        if self.db.connect():
            logger.info("✅ 数据库服务初始化成功")
            
            # 测试连接
            if self.db.test_connection():
                logger.info("✅ 数据库连接测试通过")
                
                # 检查表结构
                self._check_table_structure()
            else:
                logger.warning("⚠️  数据库连接测试失败，但服务将继续运行")
        else:
            logger.warning("⚠️  数据库连接失败，服务将以无数据库模式运行")
    
    def _check_table_structure(self):
        """检查表结构"""
        try:
            # 检查detection_log表是否存在
            query = """
                SELECT COUNT(*) as count 
                FROM information_schema.tables 
                WHERE table_schema = %s AND table_name = 'detection_log'
            """
            result = self.execute_query(query, (self.db.config.MYSQL_DATABASE,))
            
            if result and result[0]:
                # 安全地获取count值
                if isinstance(result[0], dict):
                    count = result[0].get('count', 0)
                elif isinstance(result[0], tuple):
                    count = result[0][0] if result[0] else 0
                else:
                    count = 0
                
                if count > 0:
                    logger.info("✅ detection_log表存在")
                    
                    # 检查列是否存在
                    query = """
                        SELECT COLUMN_NAME, DATA_TYPE 
                        FROM information_schema.columns 
                        WHERE table_schema = %s AND table_name = 'detection_log'
                    """
                    columns = self.execute_query(query, (self.db.config.MYSQL_DATABASE,))
                    
                    if columns:
                        logger.info("📊 detection_log表结构:")
                        for col in columns:
                            if isinstance(col, dict):
                                col_name = col.get('COLUMN_NAME', 'Unknown')
                                col_type = col.get('DATA_TYPE', 'Unknown')
                            elif isinstance(col, tuple):
                                col_name = col[0] if len(col) > 0 else 'Unknown'
                                col_type = col[1] if len(col) > 1 else 'Unknown'
                            else:
                                col_name = 'Unknown'
                                col_type = 'Unknown'
                            logger.info(f"  - {col_name}: {col_type}")
                    return True
                else:
                    logger.warning("⚠️  detection_log表不存在")
                    return False
            else:
                logger.warning("⚠️  检查表存在性失败")
                return False
                
        except Exception as e:
            logger.error(f"❌ 检查表结构失败: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def is_available(self):
        """检查数据库是否可用"""
        return self.db.is_connected()
    
    def get_db_status(self):
        """获取数据库状态"""
        table_exists = False
        if self.db.is_connected():
            try:
                table_exists = self._check_table_structure()
            except:
                table_exists = False
        
        return {
            'connected': self.db.is_connected(),
            'host': self.db.config.MYSQL_HOST,
            'port': self.db.config.MYSQL_PORT,
            'database': self.db.config.MYSQL_DATABASE,
            'table_exists': table_exists
        }
    
    def execute_query(self, query, params=None):
        """执行查询语句"""
        if not self.is_available():
            logger.warning("⚠️  数据库不可用，跳过查询")
            return None
        
        try:
            return self.db.execute_query(query, params)
        except Exception as e:
            logger.error(f"❌ 执行查询失败: {e}")
            return None
    
    def _safe_get(self, data, key, default=None, index=None):
        """
        安全地获取数据，支持字典和元组
        """
        if isinstance(data, dict):
            return data.get(key, default)
        elif isinstance(data, tuple):
            if index is not None and 0 <= index < len(data):
                return data[index]
            return default
        else:
            return default
    
    # ========== 检测日志相关操作 ==========
    
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
        Returns:
            dict: 保存结果，包含success和message
        """
        if not self.is_available():
            return {'success': False, 'message': '数据库不可用'}
        
        try:
            logger.info("💾 开始保存检测日志到数据库...")
            
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
                    output, clean_heatmap, cover_heatmap
                ) VALUES (%s, %s, %s, %s, %s, %s)
            """
            
            params = (
                upload_bytes,           # upload (longblob)
                upload_time,           # upload_time (datetime)
                status,                # status (varchar)
                output_bytes,          # output (longblob)
                clean_heatmap_bytes,   # clean_heatmap (longblob)
                cover_heatmap_bytes    # cover_heatmap (longblob)
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
    
    def get_detection_log(self, log_id):
        """
        获取检测日志
        
        Args:
            log_id: 日志ID
        Returns:
            dict: 包含图像字节数据的信息
        """
        if not self.is_available():
            return None
        
        try:
            query = """
                SELECT id, upload_time, status, 
                       LENGTH(upload) as upload_size,
                       LENGTH(output) as output_size,
                       LENGTH(clean_heatmap) as heatmap_size,
                       LENGTH(cover_heatmap) as cover_size
                FROM detection_log 
                WHERE id = %s
            """
            
            result = self.execute_query(query, (log_id,))
            
            if result and result[0]:
                row = result[0]
                if isinstance(row, dict):
                    return row
                elif isinstance(row, tuple):
                    # 将元组转换为字典
                    return {
                        'id': row[0] if len(row) > 0 else None,
                        'upload_time': row[1] if len(row) > 1 else None,
                        'status': row[2] if len(row) > 2 else None,
                        'upload_size': row[3] if len(row) > 3 else None,
                        'output_size': row[4] if len(row) > 4 else None,
                        'heatmap_size': row[5] if len(row) > 5 else None,
                        'cover_size': row[6] if len(row) > 6 else None
                    }
            return None
            
        except Exception as e:
            logger.error(f"❌ 获取检测日志失败: {e}")
            return None
    
    def get_detection_log_count(self):
        """获取检测日志数量"""
        if not self.is_available():
            return 0
        
        try:
            query = "SELECT COUNT(*) as count FROM detection_log"
            result = self.execute_query(query)
            
            if result and result[0]:
                row = result[0]
                if isinstance(row, dict):
                    return row.get('count', 0)
                elif isinstance(row, tuple):
                    return row[0] if row and len(row) > 0 else 0
            return 0
            
        except Exception as e:
            logger.error(f"❌ 获取日志数量失败: {e}")
            return 0
    
    def get_recent_logs(self, limit=10):
        """获取最近的检测日志"""
        if not self.is_available():
            return []
        
        try:
            query = """
                SELECT id, upload_time, status 
                FROM detection_log 
                ORDER BY upload_time DESC 
                LIMIT %s
            """
            
            result = self.execute_query(query, (limit,))
            
            if result:
                formatted_result = []
                for row in result:
                    if isinstance(row, dict):
                        formatted_result.append(row)
                    elif isinstance(row, tuple):
                        formatted_result.append({
                            'id': row[0] if len(row) > 0 else None,
                            'upload_time': row[1] if len(row) > 1 else None,
                            'status': row[2] if len(row) > 2 else None
                        })
                return formatted_result
            return []
            
        except Exception as e:
            logger.error(f"❌ 获取最近日志失败: {e}")
            return []
    
    def close(self):
        """关闭数据库连接"""
        self.db.disconnect()
        logger.info("✅ 数据库服务已关闭")