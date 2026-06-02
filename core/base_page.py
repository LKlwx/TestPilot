"""BasePage — Page Object 模式基类"""
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# 定位方式映射表
BY_MAP = {
    "id": By.ID,
    "name": By.NAME,
    "xpath": By.XPATH,
    "css": By.CSS_SELECTOR,
    "linkText": By.LINK_TEXT,
    "className": By.CLASS_NAME,
}


class BasePage:
    """Page Object 基类，封装通用页面操作

    用法：
        class LoginPage(BasePage):
            USERNAME = ("id", "username")
            PASSWORD = ("id", "password")
            LOGIN_BTN = ("id", "loginBtn")

            def login(self, username, password):
                self.input_text(*self.USERNAME, username)
                self.input_text(*self.PASSWORD, password)
                self.click(*self.LOGIN_BTN)
    """

    def __init__(self, driver, timeout=10):
        self.driver = driver
        self.wait = WebDriverWait(driver, timeout)

    def _by(self, locator_type: str):
        return BY_MAP.get(locator_type, By.XPATH)

    def find_element(self, locator_type: str, locator_value: str):
        by = self._by(locator_type)
        return self.wait.until(EC.visibility_of_element_located((by, locator_value)))

    def click(self, locator_type: str, locator_value: str):
        by = self._by(locator_type)
        elem = self.wait.until(EC.element_to_be_clickable((by, locator_value)))
        elem.click()

    def input_text(self, locator_type: str, locator_value: str, text: str):
        elem = self.find_element(locator_type, locator_value)
        elem.clear()
        elem.send_keys(text)

    def get_text(self, locator_type: str, locator_value: str) -> str:
        elem = self.find_element(locator_type, locator_value)
        return elem.text

    def wait_for_visible(self, locator_type: str, locator_value: str, timeout=10):
        by = self._by(locator_type)
        return WebDriverWait(self.driver, timeout).until(
            EC.visibility_of_element_located((by, locator_value))
        )

    def is_visible(self, locator_type: str, locator_value: str) -> bool:
        try:
            self.wait_for_visible(locator_type, locator_value, timeout=3)
            return True
        except Exception:
            return False

    def press_enter(self, locator_type: str, locator_value: str):
        elem = self.find_element(locator_type, locator_value)
        elem.send_keys(Keys.ENTER)

    def wait_for_text(self, text: str, timeout: int = 5):
        return WebDriverWait(self.driver, timeout).until(
            EC.text_to_be_present_in_element((By.TAG_NAME, "body"), text)
        )
