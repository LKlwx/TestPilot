"""
示例 Page Class — 登录页、首页
演示 Page Object 模式：定位器与业务逻辑分离
"""

from core.base_page import BasePage


class LoginPage(BasePage):
    """登录页面对象"""

    USERNAME_INPUT = ("id", "username")
    PASSWORD_INPUT = ("id", "password")
    LOGIN_BTN = ("id", "loginBtn")
    ERROR_MSG = ("css", ".error-msg")
    REGISTER_LINK = ("linkText", "注册")

    def login(self, username: str, password: str):
        self.input_text(*self.USERNAME_INPUT, username)
        self.input_text(*self.PASSWORD_INPUT, password)
        self.click(*self.LOGIN_BTN)

    def get_error_message(self) -> str:
        return self.get_text(*self.ERROR_MSG)

    def go_to_register(self):
        self.click(*self.REGISTER_LINK)


class HomePage(BasePage):
    """首页 / 控制台页面对象"""

    WELCOME_TEXT = ("css", ".welcome-text")
    LOGOUT_BTN = ("id", "logoutBtn")
    NAV_TEST = ("linkText", "接口自动化测试")
    NAV_UI = ("linkText", "UI自动化测试")
    NAV_PERF = ("linkText", "性能测试")

    def get_welcome_text(self) -> str:
        return self.get_text(*self.WELCOME_TEXT)

    def logout(self):
        self.click(*self.LOGOUT_BTN)

    def go_to_api_test(self):
        self.click(*self.NAV_TEST)

    def go_to_ui_test(self):
        self.click(*self.NAV_UI)

    def go_to_perf_test(self):
        self.click(*self.NAV_PERF)
