import pymysql
import logging
from contextlib import contextmanager
from config import Config

# 设置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class DatabaseConnection:
    """MySQL数据库连接管理器"""
    
    def __init__(self):
        self.config = Config
        self.connection = None
    
    def connect(self):
        """建立数据库连接"""
        try:
            self.connection = pymysql.connect(
                host=self.config.MYSQL_HOST,
                port=self.config.MYSQL_PORT,
                user=self.config.MYSQL_USER,
                password=self.config.MYSQL_PASSWORD,
                database=self.config.MYSQL_DATABASE,
                charset=self.config.MYSQL_CHARSET,
                connect_timeout=self.config.MYSQL_CONNECT_TIMEOUT,
                read_timeout=self.config.MYSQL_READ_TIMEOUT,
                autocommit=True,  # 自动提交
                cursorclass=pymysql.cursors.DictCursor  # 明确指定使用DictCursor
            )
            logger.info(f"✅ 数据库连接成功: {self.config.MYSQL_HOST}:{self.config.MYSQL_PORT}/{self.config.MYSQL_DATABASE}")
            return True
        except pymysql.Error as e:
            logger.error(f"❌ 数据库连接失败: {e}")
            return False
    
    def disconnect(self):
        """关闭数据库连接"""
        if self.connection:
            try:
                self.connection.close()
                logger.info("✅ 数据库连接已关闭")
            except Exception as e:
                logger.error(f"❌ 关闭数据库连接失败: {e}")
            finally:
                self.connection = None
    
    def is_connected(self):
        """检查连接是否有效"""
        if not self.connection:
            return False
        
        try:
            # 简单的心跳检测
            with self.connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                return True
        except:
            return False
    
    def get_connection(self):
        """获取当前连接，如果未连接则尝试连接"""
        if not self.is_connected():
            self.connect()
        return self.connection
    
    @contextmanager
    def get_cursor(self, cursor_type=None):
        """获取数据库游标的上下文管理器"""
        connection = self.get_connection()
        cursor = None
        try:
            if cursor_type:
                cursor = connection.cursor(cursor_type)
            else:
                cursor = connection.cursor()
            yield cursor
        finally:
            if cursor:
                cursor.close()
    
    def execute_query(self, query, params=None, fetch_dict=True):
        """执行查询语句并返回结果"""
        if not self.is_connected():
            logger.warning("⚠️  数据库不可用，跳过查询")
            return None
        
        try:
            with self.get_cursor() as cursor:
                cursor.execute(query, params or ())
                
                if query.strip().upper().startswith('SELECT'):
                    result = cursor.fetchall()
                    logger.debug(f"📊 查询成功，返回 {len(result)} 行数据")
                    return result
                else:
                    affected_rows = cursor.rowcount
                    last_id = cursor.lastrowid
                    logger.debug(f"📊 操作成功，影响 {affected_rows} 行，最后ID: {last_id}")
                    return {'affected_rows': affected_rows, 'last_id': last_id}
        except Exception as e:
            logger.error(f"❌ 执行查询失败: {e}")
            return None
    
    def test_connection(self):
        """测试数据库连接"""
        try:
            with self.get_cursor() as cursor:
                cursor.execute("SELECT VERSION()")
                version = cursor.fetchone()
                
                if version:
                    # 如果是元组，取第一个元素
                    if isinstance(version, tuple):
                        version_info = version[0]
                    else:
                        version_info = version.get('VERSION()', 'Unknown')
                    logger.info(f"📊 MySQL版本: {version_info}")
                else:
                    logger.info("📊 MySQL版本: Unknown")
                
                # 显示数据库信息
                cursor.execute("SELECT DATABASE()")
                db_name = cursor.fetchone()
                
                if db_name:
                    if isinstance(db_name, tuple):
                        db_info = db_name[0]
                    else:
                        db_info = db_name.get('DATABASE()', 'Unknown')
                    logger.info(f"📊 当前数据库: {db_info}")
                else:
                    logger.info("📊 当前数据库: Unknown")
                
                return True
        except Exception as e:
            logger.error(f"❌ 数据库连接测试失败: {e}")
            return False