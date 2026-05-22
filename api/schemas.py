from marshmallow import Schema, fields, validate


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


class UpdatePerformanceCaseSchema(Schema):
    name = fields.String(validate=validate.Length(min=1, max=100))
    url = fields.String(validate=validate.Length(max=500))
    method = fields.String(validate=validate.OneOf(["GET", "POST", "PUT", "DELETE"]))
    headers = fields.String()
    body = fields.String()
    concurrency = fields.Integer(validate=validate.Range(min=1, max=10000))
    total = fields.Integer(validate=validate.Range(min=1, max=100000))
