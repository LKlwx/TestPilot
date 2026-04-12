class APIException(Exception):
    # 自定义API异常类
    def __init__(self, msg="接口异常", code=500):
        self.msg = msg
        self.code = code
        super().__init__(self.msg)

class AuthException(APIException):
    # 认证异常
    def __init__(self, msg="权限不足，请先登录"):
        super().__init__(msg, code=401)

class NotFoundException(APIException):
    def __init__(self, msg="资源不存在"):
        super().__init__(msg, code=404)
