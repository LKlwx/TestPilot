# -*- coding: utf-8 -*-
import requests
import json
from config import Config


class AITestAgent:
    """AI 测试助手：调用本地 LM Studio 模型生成用例或分析日志"""
    def __init__(self):
        # 接口用例生成提示词，示例中的 {{}} 用于转义，避免 format 报错
        self.api_prompt = """你是资深测试开发，请根据业务场景生成一个 JSON 对象。
要求：必须包含 name, method, url, headers, body, expect 这 6 个英文键。
示例：{{"name": "登录测试", "method": "POST", "url": "/api/login", "headers": {{}}, "body": {{}}, "expect": "成功"}}
场景：{}"""
        # UI 用例生成提示词
        self.ui_prompt = """你是 UI 自动化专家，请根据业务场景生成一个 JSON 对象。
要求：必须包含 name, url, steps 这 3 个英文键。
示例：{{"name": "登录流程", "url": "http://localhost/login", "steps": "步骤 1；步骤 2"}}
场景：{}"""
        # 日志诊断分析提示词
        self.analyze_prompt = """你是测试诊断专家，请分析日志生成一个 JSON 对象。
要求：必须包含 cause, solution 这 2 个英文键。
日志：{}"""
        # 从配置文件读取模型服务地址与名称
        self.api_base = Config.AI_API_BASE
        self.model = Config.AI_MODEL

    def _call_ai(self, prompt: str) -> str:
        """向本地 LM Studio 发起请求，获取模型返回内容"""
        url = f"{self.api_base}/v1/chat/completions"
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.7,
            "max_tokens": 1024
        }
        try:
            response = requests.post(url, json=payload, timeout=60)
            if response.status_code == 200:
                data = response.json()
                return data["choices"][0]["message"]["content"]
            else:
                raise Exception(f"AI 请求失败 [{response.status_code}]")
        except requests.exceptions.ConnectionError:
            raise Exception("无法连接到 LM Studio")
        except requests.exceptions.Timeout:
            raise Exception("AI 请求超时")

    def _parse_json_response(self, res: str, required_keys: list) -> dict:
        """清理模型返回内容并解析 JSON，自动映射中文键名"""
        cleaned = res.strip()
        # 兼容 Markdown 代码块格式
        if "```json" in cleaned:
            cleaned = cleaned.split("```json")[1].split("```")[0].strip()
        elif "```" in cleaned:
            cleaned = cleaned.split("```")[1].split("```")[0].strip()
        try:
            parsed = json.loads(cleaned)
        except:
            # 若直接解析失败，尝试提取 {} 包裹的内容
            start = cleaned.find("{")
            end = cleaned.rfind("}") + 1
            if start != -1 and end != 0:
                try:
                    parsed = json.loads(cleaned[start:end])
                except:
                    raise Exception("JSON 解析失败")
            else:
                raise Exception("JSON 解析失败")
        # 如果返回的是列表，取第一个元素
        if isinstance(parsed, list):
            if len(parsed) > 0:
                parsed = parsed[0]
            else:
                raise Exception("模型返回了空列表")
        # 将中文键映射为英文键，方便后续数据库存储
        key_map = {
            "用例名": "name", "用例名称": "name", "名称": "name",
            "请求方法": "method", "方法": "method",
            "接口路径": "url", "地址": "url", "路径": "url",
            "请求头": "headers", "头": "headers",
            "参数": "body", "请求体": "body", "体": "body",
            "预期结果": "expect", "期望结果": "expect", "预期": "expect",
            "失败原因": "cause", "原因": "cause",
            "解决方案": "solution", "解决": "solution", "方案": "solution",
            "步骤": "steps", "测试步骤": "steps"
        }
        keys_to_delete = []
        for k in parsed:
            if k in key_map:
                english_key = key_map[k]
                if english_key not in parsed:
                    parsed[english_key] = parsed[k]
                keys_to_delete.append(k)
        for k in keys_to_delete:
            del parsed[k]
        # 校验必要字段
        missing = [k for k in required_keys if k not in parsed]
        if missing:
            raise Exception(f"缺少必要键 {missing}。模型返回内容：{parsed}")
        return parsed

    def generate_api_case(self, scene: str):
        """生成接口测试用例"""
        res = self._call_ai(self.api_prompt.format(scene))
        return self._parse_json_response(res, ["name", "method", "url", "headers", "body", "expect"])

    def generate_ui_case(self, scene: str):
        """生成 UI 测试用例"""
        res = self._call_ai(self.ui_prompt.format(scene))
        return self._parse_json_response(res, ["name", "url", "steps"])

    def analyze_failure_log(self, log: str):
        """分析失败日志并返回诊断报告"""
        res = self._call_ai(self.analyze_prompt.format(log))
        analysis = self._parse_json_response(res, ["cause", "solution"])
        return f"【AI 诊断】原因：{analysis['cause']}\n方案：{analysis['solution']}"


ai_agent = AITestAgent()
