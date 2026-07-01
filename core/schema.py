from marshmallow import Schema, ValidationError, fields, validate

from core.exception import APIException


def validate_request(schema_cls, data):
    """统一校验入口：接收 Schema 类和数据，校验失败抛出 APIException 400"""
    schema = schema_cls()
    try:
        return schema.load(data or {})
    except ValidationError as e:
        raise APIException(f"参数校验失败: {e.messages}", 400)
