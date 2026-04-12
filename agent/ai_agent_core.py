# -*- coding: utf-8 -*-
class AITestAgent:
    def __init__(self):
        self.api_prompt = """
            你是资深测试开发，根据业务场景生成标准接口测试用例，返回严格JSON：
            name, method, url, headers, body, expect
            场景：{}
        """
        self.ui_prompt = """
            你是UI自动化专家，生成标准UI用例，返回JSON：
            name, url, steps
            场景：{}
            """
        self.analyze_prompt = """
            你是测试故障诊断专家，分析日志给出原因+解决方案。
            日志：{}
            """

    def generate_api_case(self, scene: str):
        # 规则引擎模拟，根据业务场景生成接口测试用例
        prompt = self.api_prompt.format(scene)
        return {
            "name": f"AI_API_{scene[:8]}",
            "method": "POST",
            "url": "/api/business/action",
            "headers": '{"Content-Type":"application/json"}',
            "body": '{"scene":"%s"}' % scene,
            "expect": "code=200 执行成功"
        }

    def generate_ui_case(self, scene: str):
        prompt = self.ui_prompt.format(scene)
        steps = f"""打开页面
            输入用户名
            输入密码
            点击登录
            断言登录成功
            场景：{scene}"""
        return {
            "name": f"AI_UI_{scene[:8]}",
            "url": "http://localhost:5000",
            "steps": steps
        }

    def analyze_failure_log(self, log: str):
        # 分析测试失败日志，基于关键词返回诊断建议
        log = log.lower()
        if "timeout" in log:
            return "【AI诊断】请求超时\n原因：服务未启动/网络波动\n方案：检查服务与连通性"
        elif "404" in log:
            return "【AI诊断】接口不存在\n原因：URL错误\n方案：核对接口地址"
        elif "500" in log:
            return "【AI诊断】服务内部异常\n原因：代码报错\n方案：查看后台日志"
        elif "assert" in log or "expect" in log:
            return "【AI诊断】断言失败\n原因：预期与实际不匹配\n方案：核对返回值"
        else:
            return "【AI诊断】未知异常\n方案：提供完整日志"


ai_agent = AITestAgent()
