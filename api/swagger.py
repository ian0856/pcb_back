def generate_swagger_spec():
    """生成Swagger JSON规范"""
    return {
        "swagger": "2.0",
        "info": {
            "title": "PCB Anomaly Detection API",
            "description": "基于无监督异常检测的PCB缺陷检测系统API",
            "version": "1.0.0",
            "contact": {
                "name": "PCB Detection System"
            }
        },
        "host": "localhost:5000",
        "basePath": "/",
        "schemes": ["http"],
        "tags": [
            {
                "name": "检测服务",
                "description": "PCB异常检测相关接口"
            },
            {
                "name": "系统管理",
                "description": "系统状态和健康检查接口"
            },
            {
                "name": "检测记录",
                "description": "检测记录查询接口"
            }
        ],
        "paths": {
            "/swagger.json": {
                "get": {
                    "tags": ["系统管理"],
                    "summary": "获取Swagger API文档",
                    "description": "返回Swagger规范的API文档JSON数据",
                    "produces": ["application/json"],
                    "responses": {
                        "200": {
                            "description": "成功返回API文档",
                            "schema": {
                                "type": "object"
                            }
                        }
                    }
                }
            },
            "/annotation": {
                "post": {
                    "tags": ["检测服务"],
                    "summary": "上传PCB图像进行异常检测",
                    "description": "上传PCB图像，系统会检测异常区域并返回标注结果和热力图，同时可选保存检测记录到数据库",
                    "consumes": ["multipart/form-data"],
                    "produces": ["application/json"],
                    "parameters": [
                        {
                            "name": "image",
                            "in": "formData",
                            "type": "file",
                            "required": True,
                            "description": "需要检测的PCB图像文件（支持jpg、png、jpeg格式）"
                        }
                    ],
                    "responses": {
                        "200": {
                            "description": "检测成功",
                            "schema": {
                                "type": "object",
                                "properties": {
                                    "success": {"type": "boolean", "example": True},
                                    "message": {"type": "string", "example": "Detection completed successfully"},
                                    "anomaly_score": {"type": "number", "example": 0.85},
                                    "anomaly_level": {"type": "string", "example": "high"},
                                    "regions_count": {"type": "integer", "example": 3},
                                    "result_image": {"type": "string", "example": "/output/result_20231201_123456.jpg"},
                                    "heatmap_image": {"type": "string", "example": "/output/heatmap_20231201_123456.jpg"},
                                    "detection_summary": {
                                        "type": "object",
                                        "properties": {
                                            "total_regions": {"type": "integer"},
                                            "mean_confidence": {"type": "number"},
                                            "max_confidence": {"type": "number"},
                                            "min_confidence": {"type": "number"}
                                        }
                                    },
                                    "database_save": {
                                        "type": "object",
                                        "properties": {
                                            "success": {"type": "boolean"},
                                            "log_id": {"type": "integer"},
                                            "upload_time": {"type": "string"},
                                            "message": {"type": "string"}
                                        }
                                    }
                                }
                            }
                        },
                        "400": {
                            "description": "请求错误（未提供文件或文件类型无效）",
                            "schema": {
                                "type": "object",
                                "properties": {
                                    "success": {"type": "boolean", "example": False},
                                    "message": {"type": "string", "example": "No image file provided"}
                                }
                            }
                        },
                        "503": {
                            "description": "服务未就绪",
                            "schema": {
                                "type": "object",
                                "properties": {
                                    "success": {"type": "boolean", "example": False},
                                    "message": {"type": "string", "example": "Detection system is not ready"}
                                }
                            }
                        },
                        "500": {
                            "description": "服务器内部错误",
                            "schema": {
                                "type": "object",
                                "properties": {
                                    "success": {"type": "boolean", "example": False},
                                    "message": {"type": "string", "example": "Detection failed: ..."}
                                }
                            }
                        }
                    }
                }
            },
            "/health": {
                "get": {
                    "tags": ["系统管理"],
                    "summary": "健康检查",
                    "description": "检查服务状态、检测器初始化状态和数据库连接状态",
                    "produces": ["application/json"],
                    "responses": {
                        "200": {
                            "description": "服务状态信息",
                            "schema": {
                                "type": "object",
                                "properties": {
                                    "status": {"type": "string", "enum": ["healthy", "degraded"], "example": "healthy"},
                                    "detection": {
                                        "type": "object",
                                        "properties": {
                                            "initialized": {"type": "boolean", "example": True},
                                            "ready": {"type": "boolean", "example": True}
                                        }
                                    },
                                    "database": {
                                        "type": "object",
                                        "properties": {
                                            "available": {"type": "boolean", "example": True},
                                            "table_exists": {"type": "boolean", "example": True},
                                            "total_logs": {"type": "integer", "example": 42}
                                        }
                                    },
                                    "output_dir": {"type": "string", "example": "./output"},
                                    "service": {"type": "string", "example": "PCB Anomaly Detection"},
                                    "message": {"type": "string", "example": "Service is operational"}
                                }
                            }
                        }
                    }
                }
            },
            "/logs": {
                "get": {
                    "tags": ["检测记录"],
                    "summary": "获取所有检测记录",
                    "description": "返回detection_log表中所有检测记录",
                    "produces": ["application/json"],
                    "responses": {
                        "200": {
                            "description": "成功返回所有检测记录",
                            "schema": {
                                "type": "object",
                                "properties": {
                                    "success": {"type": "boolean", "example": True},
                                    "data": {
                                        "type": "array",
                                        "items": {
                                            "type": "object",
                                            "properties": {
                                                "id": {"type": "integer", "example": 42},
                                                "upload_time": {"type": "string", "format": "date-time", "example": "2023-12-01 10:30:45"},
                                                "status": {"type": "string", "example": "success"},
                                                "upload_size": {"type": "integer", "example": 102400},
                                                "output_size": {"type": "integer", "example": 102400},
                                                "heatmap_size": {"type": "integer", "example": 51200},
                                                "cover_size": {"type": "integer", "example": 102400}
                                            }
                                        }
                                    }
                                }
                            }
                        },
                        "503": {
                            "description": "数据库服务不可用",
                            "schema": {
                                "type": "object",
                                "properties": {
                                    "success": {"type": "boolean", "example": False},
                                    "message": {"type": "string", "example": "Database service not available"}
                                }
                            }
                        },
                        "500": {
                            "description": "服务器内部错误",
                            "schema": {
                                "type": "object",
                                "properties": {
                                    "success": {"type": "boolean", "example": False},
                                    "message": {"type": "string", "example": "Failed to get logs: ..."}
                                }
                            }
                        }
                    }
                }
            },
            "/logs/{log_id}": {
                "get": {
                    "tags": ["检测记录"],
                    "summary": "根据ID获取指定检测记录",
                    "description": "根据日志ID返回完整的检测记录信息",
                    "produces": ["application/json"],
                    "parameters": [
                        {
                            "name": "log_id",
                            "in": "path",
                            "type": "integer",
                            "required": True,
                            "description": "日志ID"
                        }
                    ],
                    "responses": {
                        "200": {
                            "description": "成功返回日志详情",
                            "schema": {
                                "type": "object",
                                "properties": {
                                    "success": {"type": "boolean", "example": True},
                                    "data": {
                                        "type": "object",
                                        "properties": {
                                            "id": {"type": "integer", "example": 42},
                                            "upload_time": {"type": "string", "format": "date-time", "example": "2023-12-01 10:30:45"},
                                            "status": {"type": "string", "example": "success"},
                                            "upload_size": {"type": "integer", "example": 102400},
                                            "output_size": {"type": "integer", "example": 102400},
                                            "heatmap_size": {"type": "integer", "example": 51200},
                                            "cover_size": {"type": "integer", "example": 102400}
                                        }
                                    }
                                }
                            }
                        },
                        "404": {
                            "description": "日志不存在",
                            "schema": {
                                "type": "object",
                                "properties": {
                                    "success": {"type": "boolean", "example": False},
                                    "message": {"type": "string", "example": "Log with id 999 not found"}
                                }
                            }
                        },
                        "503": {
                            "description": "数据库服务不可用",
                            "schema": {
                                "type": "object",
                                "properties": {
                                    "success": {"type": "boolean", "example": False},
                                    "message": {"type": "string", "example": "Database service not available"}
                                }
                            }
                        },
                        "500": {
                            "description": "服务器内部错误",
                            "schema": {
                                "type": "object",
                                "properties": {
                                    "success": {"type": "boolean", "example": False},
                                    "message": {"type": "string", "example": "Failed to get log: ..."}
                                }
                            }
                        }
                    }
                }
            }
        },
        "definitions": {
            "DetectionResult": {
                "type": "object",
                "properties": {
                    "anomaly_score": {"type": "number"},
                    "anomaly_level": {"type": "string"},
                    "regions_count": {"type": "integer"},
                    "detection_summary": {"type": "object"}
                }
            },
            "DatabaseSaveResult": {
                "type": "object",
                "properties": {
                    "success": {"type": "boolean"},
                    "log_id": {"type": "integer"},
                    "upload_time": {"type": "string"},
                    "message": {"type": "string"}
                }
            },
            "DetectionLog": {
                "type": "object",
                "properties": {
                    "id": {"type": "integer"},
                    "upload_time": {"type": "string"},
                    "status": {"type": "string"},
                    "upload_size": {"type": "integer"},
                    "output_size": {"type": "integer"},
                    "heatmap_size": {"type": "integer"},
                    "cover_size": {"type": "integer"}
                }
            }
        }
    }