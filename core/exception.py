class APIException(Exception):
    def __init__(self, msg="接口异常", code=500):
        self.msg = msg
        self.code = code
        super().__init__(self.msg)

class AuthException(APIException):
    def __init__(self, msg="权限不足，请先登录"):
        super().__init__(msg, code=401)

class NotFoundException(APIException):
    def __init__(self, msg="资源不存在"):
        super().__init__(msg, code=404)
