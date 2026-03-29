from flask import request, jsonify
import base64
import os
from werkzeug.utils import secure_filename
from utils import allowed_file, save_uploaded_file, convert_to_serializable
from config import Config

def register_routes(app, detection_service, database_service=None):
    """注册API路由"""
    
    @app.route('/swagger.json', methods=['GET'])
    def swagger_json():
        """提供Swagger JSON文档"""
        from api.swagger import generate_swagger_spec
        return jsonify(generate_swagger_spec())
    
    @app.route('/annotation', methods=['POST'])
    def annotation():
        """
        PCB异常检测接口
        ---
        接收PCB图像，返回异常检测结果
        """
        # 检查检测器是否初始化
        if detection_service is None:
            return jsonify({
                'success': False,
                'message': 'Detection system not initialized. Please check the service status at /service-status'
            }), 503
        
        if not detection_service.is_ready():
            return jsonify({
                'success': False,
                'message': 'Detection system is not ready. Please check the service status at /service-status'
            }), 503
        
        # 检查文件是否存在
        if 'image' not in request.files:
            return jsonify({
                'success': False,
                'message': 'No image file provided'
            }), 400
        
        file = request.files['image']
        
        # 检查文件名是否为空
        if file.filename == '':
            return jsonify({
                'success': False,
                'message': 'No selected file'
            }), 400
        
        filepath = None
        try:
            # 保存上传的文件
            filepath = save_uploaded_file(file, Config.UPLOAD_FOLDER)
            if not filepath:
                return jsonify({
                    'success': False,
                    'message': 'Invalid file type'
                }), 400
            
            # 处理图像
            result = detection_service.process_image(filepath)
            
            # 构建响应前转换所有数据为可序列化格式
            serializable_result = convert_to_serializable(result)
            
            # 构建响应
            response = {
                'success': True,
                'message': 'Detection completed successfully',
                **serializable_result
            }
            
            # 确保路径使用正斜杠
            if 'result_image' in response:
                response['result_image'] = response['result_image'].replace('\\', '/')
            if 'heatmap_image' in response:
                response['heatmap_image'] = response['heatmap_image'].replace('\\', '/')
            
            # 保存到数据库
            db_save_result = None
            if database_service and database_service.is_available():
                try:
                    # 准备保存到数据库的数据
                    detection_data = {
                        'upload_image_path': filepath,
                        'output_image_path': response['result_image'],
                        'heatmap_image_path': response['heatmap_image']
                    }
                    
                    db_save_result = database_service.save_detection_log(detection_data)
                    
                    if db_save_result['success']:
                        response['database_save'] = {
                            'success': True,
                            'log_id': db_save_result.get('log_id'),
                            'upload_time': db_save_result.get('upload_time'),
                            'message': '检测记录已保存到数据库'
                        }
                        print(f"✅ 检测记录已保存到数据库，ID: {db_save_result.get('log_id')}")
                    else:
                        response['database_save'] = {
                            'success': False,
                            'message': db_save_result.get('message', '保存失败')
                        }
                        print(f"⚠️  数据库保存失败: {db_save_result.get('message')}")
                        
                except Exception as e:
                    print(f"⚠️  保存到数据库时出错: {e}")
                    response['database_save'] = {
                        'success': False,
                        'message': f'数据库保存出错: {str(e)}'
                    }
            else:
                response['database_save'] = {
                    'success': False,
                    'message': '数据库服务不可用'
                }
            
            return jsonify(response)
            
        except Exception as e:
            print(f"❌ Error during detection: {str(e)}")
            import traceback
            traceback.print_exc()
            
            return jsonify({
                'success': False,
                'message': f'Detection failed: {str(e)}'
            }), 500
            
        finally:
            # 清理临时文件
            if filepath and os.path.exists(filepath):
                try:
                    os.remove(filepath)
                except:
                    pass
    
    @app.route('/health', methods=['GET'])
    def health_check():
        """健康检查接口"""
        detection_status = {
            'initialized': detection_service is not None,
            'ready': detection_service.is_ready() if detection_service else False
        }
        
        database_status = {}
        if database_service:
            db_status = database_service.get_db_status()
            database_status = {
                'available': database_service.is_available(),
                'table_exists': db_status.get('table_exists', False),
                'total_logs': database_service.get_detection_log_count() if database_service.is_available() else 0
            }
        
        status = {
            'status': 'healthy' if detection_status['ready'] else 'degraded',
            'detection': detection_status,
            'database': database_status,
            'output_dir': Config.OUTPUT_DIR,
            'service': 'PCB Anomaly Detection',
            'message': 'Service is operational' if detection_status['ready'] else 'Detection service is not ready'
        }
        return jsonify(status)
    
    @app.route('/logs', methods=['GET'])
    def get_logs():
        """获取检测记录"""
        if database_service is None or not database_service.is_available():
            return jsonify({
                'success': False,
                'message': 'Database service not available'
            }), 503
        
        try:
            logs = database_service.get_all_detection_logs()
            
            # 将BLOB数据转换为Base64编码
            for log in logs:
                if log.get('upload'):
                    log['upload'] = base64.b64encode(log['upload']).decode('utf-8')
                if log.get('output'):
                    log['output'] = base64.b64encode(log['output']).decode('utf-8')
                if log.get('clean_heatmap'):
                    log['clean_heatmap'] = base64.b64encode(log['clean_heatmap']).decode('utf-8')
                if log.get('cover_heatmap'):
                    log['cover_heatmap'] = base64.b64encode(log['cover_heatmap']).decode('utf-8')
            
            return jsonify({
                'success': True,
                'data': logs,
            })
        except Exception as e:
            return jsonify({
                'success': False,
                'message': f'Failed to get logs: {str(e)}'
            }), 500
    
    @app.route('/logs/<int:log_id>', methods=['GET'])
    def get_log_detail(log_id):
        """获取指定日志的详细信息"""
        if database_service is None or not database_service.is_available():
            return jsonify({
                'success': False,
                'message': 'Database service not available'
            }), 503
        
        try:
            log_info = database_service.get_detection_log_by_id(log_id)
            if log_info:
                # 将BLOB数据转换为Base64编码
                if log_info.get('upload'):
                    log_info['upload'] = base64.b64encode(log_info['upload']).decode('utf-8')
                if log_info.get('output'):
                    log_info['output'] = base64.b64encode(log_info['output']).decode('utf-8')
                if log_info.get('clean_heatmap'):
                    log_info['clean_heatmap'] = base64.b64encode(log_info['clean_heatmap']).decode('utf-8')
                if log_info.get('cover_heatmap'):
                    log_info['cover_heatmap'] = base64.b64encode(log_info['cover_heatmap']).decode('utf-8')
                
                return jsonify({
                    'success': True,
                    'data': log_info,
                })
            else:
                return jsonify({
                    'success': False,
                    'message': f'Log #{log_id} not found'
                }), 404
        except Exception as e:
            return jsonify({
                'success': False,
                'message': f'Failed to get log detail: {str(e)}'
            }), 500