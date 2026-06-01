import os
import time
import json
from contextlib import contextmanager
from sqlalchemy.exc import SQLAlchemyError
from extensions import db
from models import UIReport
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from core.logger import get_logger

logger = get_logger(__name__)

# 项目根目录（用于截图路径等）
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# 元素定位方式映射表（模块级常量）
BY_MAP = {
    "id": By.ID,
    "name": By.NAME,
    "xpath": By.XPATH,
    "css": By.CSS_SELECTOR,
    "linkText": By.LINK_TEXT,
    "className": By.CLASS_NAME,
}


def parse_steps(steps_text):
    """
    解析结构化步骤，格式如：[action] [locator_type] value
    例如：[click] [xpath] //button[@id='login']
          [input] [name] username=admin
    返回：(是否成功, 成功列表, 错误信息列表)
    """
    SUPPORTED_ACTIONS = ["click", "input", "enter", "wait", "assert_title", "assert_text"]
    SUPPORTED_LOCATORS = ["id", "name", "xpath", "css", "linkText", "className"]

    parsed = []
    errors = []
    if not steps_text:
        return True, parsed, []

    lines = steps_text.strip().split("\n")
    for idx, line in enumerate(lines, 1):
        line = line.strip()
        if not line:
            continue
        if not line.startswith("["):
            errors.append(f"第{idx}行：格式错误，缺少动作标识 '['")
            continue

        parts = line.split("]", 2)
        if len(parts) < 3:
            errors.append(f"第{idx}行：格式错误，缺少定位方式或参数")
            continue

        action = parts[0].replace("[", "").strip()
        locator_type = parts[1].replace("[", "").strip()
        params = parts[2].strip()

        if not action:
            errors.append(f"第{idx}行：动作不能为空")
        elif action not in SUPPORTED_ACTIONS:
            errors.append(f"第{idx}行：动作 '{action}' 不支持，支持的动作：{', '.join(SUPPORTED_ACTIONS)}")

        if not locator_type:
            errors.append(f"第{idx}行：定位方式不能为空")
        elif locator_type not in SUPPORTED_LOCATORS:
            errors.append(f"第{idx}行：定位方式 '{locator_type}' 不支持，支持的定位方式：{', '.join(SUPPORTED_LOCATORS)}")

        if not params:
            errors.append(f"第{idx}行：参数不能为空")

        if not errors or errors[-1].startswith(f"第{idx}"):
            parsed.append({
                "action": action,
                "locator_type": locator_type,
                "params": params
            })

    is_valid = len(errors) == 0
    return is_valid, parsed, errors


def find_element(driver, locator_type, value):
    """统一查找元素"""
    by = BY_MAP.get(locator_type, By.XPATH)
    return driver.find_element(by, value)


@contextmanager
def create_driver(headless=True):
    """WebDriver 生命周期上下文管理器，确保任何路径下正确 quit"""
    chrome_options = Options()
    chrome_options.add_argument("--headless=new" if headless else "--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--window-size=1920,1080")
    driver = webdriver.Chrome(options=chrome_options)
    try:
        yield driver
    finally:
        try:
            driver.quit()
        except Exception:
            logger.warning("关闭浏览器失败", exc_info=True)


def run_ui_case(case):
    logger.info("UI 测试开始: case_id=%d, name=%s", case.id, case.name)
    start_time = time.time()
    step_log = []
    title = ""

    with create_driver(headless=True) as driver:
        try:
            driver.set_page_load_timeout(10)
            driver.get(case.url)
            step_log.append("打开页面：" + case.url)

            WebDriverWait(driver, 5).until(
                lambda d: d.execute_script('return document.readyState') == 'complete'
            )
            title = driver.title
            step_log.append(f" 页面标题：{title}")

            if case.steps:
                is_valid, steps, errors = parse_steps(case.steps)
                if not is_valid:
                    step_log.append(f"步骤解析失败：")
                    for err in errors:
                        step_log.append(f"  - {err}")
                    raise Exception("步骤格式或内容不符合规范，请检查后重试")

                for i, step in enumerate(steps, 1):
                    action = step["action"]
                    locator_type = step["locator_type"]
                    params = step["params"]

                    try:
                        if action == "click":
                            elem = WebDriverWait(driver, 10).until(
                                EC.element_to_be_clickable((BY_MAP.get(locator_type, By.XPATH), params))
                            )
                            elem.click()
                            step_log.append(f"步骤{i}：点击 [{locator_type}] {params}")

                        elif action == "input":
                            locator_val = params
                            input_content = ""
                            if "=" in params:
                                locator_val, input_content = params.split("=", 1)
                            elif " " in params:
                                parts = params.split(" ", 1)
                                locator_val = parts[0]
                                input_content = parts[1]
                            elem = WebDriverWait(driver, 10).until(
                                EC.visibility_of_element_located((BY_MAP.get(locator_type, By.XPATH), locator_val.strip()))
                            )
                            elem.clear()
                            elem.send_keys(input_content)
                            step_log.append(f"步骤{i}：输入 [{locator_type}] {locator_val} = {input_content}")

                        elif action == "enter":
                            from selenium.webdriver.common.keys import Keys
                            elem = WebDriverWait(driver, 10).until(
                                EC.element_to_be_clickable((BY_MAP.get(locator_type, By.XPATH), params))
                            )
                            elem.send_keys(Keys.ENTER)
                            step_log.append(f"步骤{i}：按回车键")

                        elif action == "wait":
                            parts = params.split()
                            selector = parts[0]
                            timeout = int(parts[1]) if len(parts) > 1 else 5
                            WebDriverWait(driver, timeout).until(
                                EC.presence_of_element_located((BY_MAP.get(locator_type, By.CSS_SELECTOR), selector))
                            )
                            step_log.append(f"步骤{i}：等待元素 {selector}")

                        elif action == "assert_title":
                            if params not in title:
                                raise Exception(f"标题断言失败：期望包含 '{params}'")
                            step_log.append(f"步骤{i}：断言标题包含 '{params}'")

                        elif action == "assert_text":
                            if params:
                                try:
                                    WebDriverWait(driver, 5).until(
                                        EC.text_to_be_present_in_element((By.TAG_NAME, "body"), params)
                                    )
                                    step_log.append(f"步骤{i}：断言页面包含文本 '{params}'")
                                except TimeoutException as e:
                                    raise Exception(f"文本断言失败：页面未找到 '{params}'") from e

                    except Exception as e:
                        step_log.append(f"步骤{i}失败 [{action}] [{locator_type}] {params} -> {str(e)}")
                        raise

            status = "PASS"
            error_msg = "\n".join(step_log)

        except Exception as e:
            logger.error("UI 测试失败: case_id=%d, error=%s", case.id, str(e), exc_info=True)
            status = "FAIL"
            error_msg = f"异常：{str(e)}\n\n详细步骤：\n" + "\n".join(step_log)
            # 保存失败截图
            try:
                screenshots_dir = os.path.join(BASE_DIR, "static", "screenshots")
                if not os.path.exists(screenshots_dir):
                    os.makedirs(screenshots_dir)

                filename = f"fail_{case.id}_{int(time.time())}.png"
                filepath = os.path.join(screenshots_dir, filename)
                driver.save_screenshot(filepath)
                step_log.append(f"已保存失败截图: {filepath}")
            except Exception as se:
                logger.warning("UI 截图失败: %s", str(se))
                step_log.append(f"截图失败: {str(se)}")

    cost_time = round(time.time() - start_time, 3)

    report = UIReport(
        case_id=case.id,
        case_name=case.name,
        status=status,
        cost_time=cost_time,
        error_msg=error_msg
    )
    db.session.add(report)
    try:
        db.session.commit()
    except SQLAlchemyError:
        db.session.rollback()
        raise

    logger.info(json.dumps({
        "event": "ui_test_completed", "case_id": case.id,
        "case_name": case.name, "status": status,
        "duration_ms": round(cost_time * 1000),
    }, ensure_ascii=False))

    return {
        "status": status,
        "title": title,
        "msg": error_msg,
        "time": cost_time
    }
