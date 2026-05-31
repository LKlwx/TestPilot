from marshmallow import Schema, fields, validate, ValidationError, validates_schema


def _validate_password(value):
    if len(value) < 8:
        raise ValidationError("密码长度不能少于8位")
    if len(value) > 128:
        raise ValidationError("密码长度不能超过128位")
    if not any(c.isalpha() for c in value):
        raise ValidationError("密码必须包含字母")
    if not any(c.isdigit() for c in value):
        raise ValidationError("密码必须包含数字")


class AddTestCaseSchema(Schema):
    name = fields.String(required=True, validate=validate.Length(min=1, max=100))
    method = fields.String(required=True, validate=validate.OneOf(["GET", "POST", "PUT", "DELETE"]))
    url = fields.String(required=True, validate=validate.Length(max=500))
    module = fields.String()
    headers = fields.String()
    body = fields.String()
    expect = fields.String()
    extract_var = fields.String()


class UpdateTestCaseSchema(Schema):
    name = fields.String(validate=validate.Length(min=1, max=100))
    method = fields.String(validate=validate.OneOf(["GET", "POST", "PUT", "DELETE"]))
    url = fields.String(validate=validate.Length(max=500))
    module = fields.String()
    headers = fields.String()
    body = fields.String()
    expect = fields.String()
    extract_var = fields.String()


class AddUICaseSchema(Schema):
    name = fields.String(required=True, validate=validate.Length(min=1, max=100))
    url = fields.String(required=True, validate=validate.Length(max=500))
    steps = fields.String()
    loc_type = fields.String(validate=validate.OneOf(["xpath", "id", "css"]))
    loc_value = fields.String()


class UpdateUICaseSchema(Schema):
    name = fields.String(validate=validate.Length(min=1, max=100))
    url = fields.String(validate=validate.Length(max=500))
    steps = fields.String()
    loc_type = fields.String(validate=validate.OneOf(["xpath", "id", "css"]))
    loc_value = fields.String()


class AddPerformanceCaseSchema(Schema):
    name = fields.String(required=True, validate=validate.Length(min=1, max=100))
    url = fields.String(required=True, validate=validate.Length(max=500))
    method = fields.String(validate=validate.OneOf(["GET", "POST", "PUT", "DELETE"]))
    headers = fields.String()
    body = fields.String()
    concurrency = fields.Integer(validate=validate.Range(min=1, max=10000))
    total = fields.Integer(validate=validate.Range(min=1, max=100000))
    ramp_steps = fields.Integer(validate=validate.Range(min=1, max=50), load_default=1)
    steady_duration = fields.Integer(validate=validate.Range(min=0, max=3600), load_default=0)


class UpdatePerformanceCaseSchema(Schema):
    name = fields.String(validate=validate.Length(min=1, max=100))
    url = fields.String(validate=validate.Length(max=500))
    method = fields.String(validate=validate.OneOf(["GET", "POST", "PUT", "DELETE"]))
    headers = fields.String()
    body = fields.String()
    concurrency = fields.Integer(validate=validate.Range(min=1, max=10000))
    total = fields.Integer(validate=validate.Range(min=1, max=100000))
    ramp_steps = fields.Integer(validate=validate.Range(min=1, max=50))
    steady_duration = fields.Integer(validate=validate.Range(min=0, max=3600))


# ========== Auth 模块 ==========

class LoginSchema(Schema):
    username = fields.String(required=True, validate=validate.Length(min=1, max=50))
    password = fields.String(required=True, validate=validate.Length(min=1, max=128))


class RegisterSchema(Schema):
    username = fields.String(required=True, validate=validate.Length(min=1, max=50))
    password = fields.String(required=True, validate=_validate_password)
    confirm_password = fields.String(required=True)

    @validates_schema
    def validate_passwords_match(self, data, **kwargs):
        if data.get("password") != data.get("confirm_password"):
            raise ValidationError("两次输入的密码不一致", field_name="confirm_password")


class ChangePasswordSchema(Schema):
    old_password = fields.String(required=True, validate=validate.Length(min=1, max=128))
    new_password = fields.String(required=True, validate=_validate_password)


class ChangeRoleSchema(Schema):
    id = fields.Integer(required=True, strict=True, validate=validate.Range(min=1))
    role = fields.String(required=True, validate=validate.OneOf(["admin", "tester"]))


# ========== AI 模块 ==========

class AIGenerateSchema(Schema):
    scene = fields.String(required=True, validate=validate.Length(min=1, max=1000))


class AIAnalyzeSchema(Schema):
    log = fields.String(required=True, validate=validate.Length(min=1, max=10000))


class AISaveApiSchema(Schema):
    name = fields.String(required=True, validate=validate.Length(min=1, max=100))
    method = fields.String(required=True, validate=validate.OneOf(["GET", "POST", "PUT", "DELETE"]))
    url = fields.String(required=True, validate=validate.Length(max=500))
    headers = fields.String(load_default="{}")
    body = fields.String(load_default="{}")
    expect = fields.String()
    extract_var = fields.String()


class AISaveUiSchema(Schema):
    name = fields.String(required=True, validate=validate.Length(min=1, max=100))
    url = fields.String(required=True, validate=validate.Length(max=500))
    steps = fields.String(load_default="")


# ========== 批量执行 ==========

class BatchRunSchema(Schema):
    ids = fields.List(fields.Integer(strict=True), required=True, validate=validate.Length(min=1))


# ========== UI 结构化创建 ==========

class AddUIStructSchema(Schema):
    name = fields.String(required=True, validate=validate.Length(min=1, max=100))
    url = fields.String(required=True, validate=validate.Length(max=500))
    steps = fields.String(load_default="")
    loc_type = fields.String(validate=validate.OneOf(["xpath", "id", "css"]), load_default="xpath")
    loc_value = fields.String(load_default="")
    screenshot_path = fields.String(load_default="")
