"""
BaseHTTPClient — 自研 HTTP 接口测试客户端框架

封装 requests.Session + 拦截器 + 链式断言 + 超时重试
"""

import json
import logging
import re
import time

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

logger = logging.getLogger("http_client")


class HTTPResponse:
    """HTTP 响应封装，支持链式断言"""

    def __init__(self, resp: requests.Response):
        self.resp = resp
        self._passed = True
        self._errors = []

    @property
    def status_code(self):
        return self.resp.status_code

    @property
    def text(self):
        return self.resp.text

    @property
    def headers(self):
        return self.resp.headers

    def json(self):
        return self.resp.json()

    def elapsed_ms(self):
        return round(self.resp.elapsed.total_seconds() * 1000, 1) if self.resp.elapsed else 0

    # ---- 链式断言 ----

    def validate_status(self, expected: int):
        actual = self.resp.status_code
        if actual != expected:
            self._errors.append(f"状态码断言失败：期望 {expected}，实际 {actual}")
            self._passed = False
        return self

    def validate_json(self, path: str, expected):
        actual = self.resp.json()
        try:
            keys = path.replace("$.", "").split(".")
            for k in keys:
                if isinstance(actual, list):
                    actual = actual[int(k)]
                else:
                    actual = actual[k]
        except Exception:
            self._errors.append(f"JSON 路径断言失败：无法从响应中提取 {path}")
            self._passed = False
            return self

        if str(actual) != str(expected):
            self._errors.append(f"JSON 路径断言失败：{path} 期望 {expected}，实际 {actual}")
            self._passed = False
        return self

    def validate_header(self, key: str, expected: str):
        actual = self.resp.headers.get(key, "")
        if actual != expected:
            self._errors.append(f"Header 断言失败：{key} 期望 {expected}，实际 {actual}")
            self._passed = False
        return self

    def validate_regex(self, pattern: str):
        if not re.search(pattern, self.resp.text):
            self._errors.append(f"正则断言失败：未匹配 pattern={pattern}")
            self._passed = False
        return self

    def validate_time(self, max_ms: float):
        actual = self.elapsed_ms()
        if actual > max_ms:
            self._errors.append(f"响应时间断言失败：期望 <= {max_ms}ms，实际 {actual}ms")
            self._passed = False
        return self

    def done(self):
        if not self._passed:
            raise AssertionError("\n".join(self._errors))
        return self


class BaseHTTPClient:
    """HTTP 客户端基类

    封装 requests.Session，支持：
    - 连接复用与 Keep-Alive
    - 请求/响应拦截器（自动加 Token、自动记录日志）
    - 超时与重试策略
    - 链式断言
    """

    def __init__(
        self, base_url: str = None, headers: dict = None, timeout: int = 10, retry: int = 0, retry_delay: int = 1
    ):
        self.session = requests.Session()
        self.base_url = base_url
        self.timeout = timeout
        self.retry = retry
        self.retry_delay = retry_delay

        if headers:
            self.session.headers.update(headers)

        # 配置连接池重试
        retry_adapter = HTTPAdapter(
            max_retries=Retry(
                total=retry,
                backoff_factor=retry_delay,
                allowed_methods=["GET", "POST", "PUT", "DELETE", "PATCH"],
            )
        )
        self.session.mount("http://", retry_adapter)
        self.session.mount("https://", retry_adapter)

        self._request_interceptors = []
        self._response_interceptors = []

    def add_request_interceptor(self, fn):
        """请求拦截器 fn(method, url, kwargs)"""
        self._request_interceptors.append(fn)

    def add_response_interceptor(self, fn):
        """响应拦截器 fn(response)"""
        self._response_interceptors.append(fn)

    def request(self, method: str, url: str, **kwargs) -> HTTPResponse:
        kwargs.setdefault("timeout", self.timeout)
        full_url = url if url.startswith("http") else f"{self.base_url}{url}"

        req_body = kwargs.get("json") or kwargs.get("data") or ""
        req_body_str = json.dumps(req_body, ensure_ascii=False) if isinstance(req_body, (dict, list)) else str(req_body)
        req_body_str = req_body_str[:500] if len(req_body_str) > 500 else req_body_str

        for interceptor in self._request_interceptors:
            interceptor(method, full_url, kwargs)

        resp = self.session.request(method, full_url, **kwargs)
        elapsed = round(resp.elapsed.total_seconds() * 1000, 1) if resp.elapsed else 0

        resp_body = resp.text[:1000]
        logger.info(
            json.dumps(
                {
                    "event": "http_request",
                    "method": method,
                    "url": full_url,
                    "req_headers": dict(resp.request.headers) if resp.request else {},
                    "req_body": req_body_str,
                    "status": resp.status_code,
                    "resp_body": resp_body,
                    "elapsed_ms": elapsed,
                },
                ensure_ascii=False,
            )
        )

        for interceptor in self._response_interceptors:
            interceptor(resp)

        return HTTPResponse(resp)

    def get(self, url, **kwargs):
        return self.request("GET", url, **kwargs)

    def post(self, url, **kwargs):
        return self.request("POST", url, **kwargs)

    def put(self, url, **kwargs):
        return self.request("PUT", url, **kwargs)

    def delete(self, url, **kwargs):
        return self.request("DELETE", url, **kwargs)
