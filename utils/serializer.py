# backend/utils/serializer.py - 新建文件
from neo4j.time import Date, DateTime, Time
from datetime import date, datetime
import json

class Neo4jJSONEncoder(json.JSONEncoder):
    """自定义 JSON 编码器处理 Neo4j 类型"""
    def default(self, obj):
        if isinstance(obj, (Date, DateTime, Time)):
            return str(obj)
        if isinstance(obj, (date, datetime)):
            return obj.isoformat()
        return super().default(obj)

def to_json_serializable(obj):
    """转换为 JSON 可序列化对象"""
    if obj is None:
        return None
    if isinstance(obj, (Date, DateTime, Time)):
        return str(obj)
    if isinstance(obj, (date, datetime)):
        return obj.isoformat()
    if isinstance(obj, dict):
        return {k: to_json_serializable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [to_json_serializable(item) for item in obj]
    return obj