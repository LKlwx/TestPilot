import os
import time
from extensions import db
from models import UIReport
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


def parse_steps(steps_text):
    """
    解析结构化步骤，格式如：[action] [locator_type] value
    例如：[click] [xpath] //button[@id='login']
          [input] [name] username=admin
    """
    parsed = []
    if not steps_text:
        return parsed

    for line in steps_text.strip().split("\n"):
        line = line.strip()
        if not line or not line.startswith("["):
            continue

        parts = line.split("]", 2)
        if len(parts) < 3:
            continue

        action = parts[0].replace("[", "").strip()
        locator_type = parts[1].replace("[", "").strip()
        params = parts[2].strip()

        parsed.append({
            "action": action,
            "locator_type": locator_type,
            "params": params
        })

    return parsed


def find_element(driver, locator_type, value):
    """统一查找元素"""
    by_map = {
        "id": By.ID,
        "name": By.NAME,
        "xpath": By.XPATH,
        "css": By.CSS_SELECTOR,
        "linkText": By.LINK_TEXT,
        "className": By.CLASS_NAME
    }
    by = by_map.get(locator_type, By.XPATH)
    return driver.find_element(by, value)


def run_ui_case(case):
    start_time = time.time()
    step_log = []
    title = ""

    # 定义定位方式映射
    by_map = {
        "id": By.ID,
        "name": By.NAME,
        "xpath": By.XPATH,
        "css": By.CSS_SELECTOR,
        "linkText": By.LINK_TEXT,
        "className": By.CLASS_NAME
    }
    try:
        chrome_options = Options()
        chrome_options.add_argument("--headless=new")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--window-size=1920,1080")

        driver = webdriver.Chrome(options=chrome_options)
        driver.set_page_load_timeout(10)
        driver.get(case.url)
        step_log.append("打开页面：" + case.url)

        # 显式等待页面加载
        WebDriverWait(driver, 5).until(
            lambda d: d.execute_script('return document.readyState') == 'complete'
        )
        title = driver.title
        step_log.append(f" 页面标题：{title}")

        # 解析并执行步骤
        if case.steps:
            steps = parse_steps(case.steps)
            for i, step in enumerate(steps, 1):
                action = step["action"]
                locator_type = step["locator_type"]
                params = step["params"]

                try:
                    if action == "click":
                        elem = WebDriverWait(driver, 10).until(
                            EC.element_to_be_clickable((by_map.get(locator_type, By.XPATH), params))
                        )
                        elem.click()
                        step_log.append(f"步骤{i}：点击 [{locator_type}] {params}")

                    elif action == "input":
                        # 格式：username=admin
                        if "=" in params:
                            key, value = params.split("=", 1)
                            elem = WebDriverWait(driver, 10).until(
                                EC.visibility_of_element_located((by_map.get(locator_type, By.XPATH), key))
                            )
                            elem.clear()
                            elem.send_keys(value)
                            step_log.append(f"步骤{i}：输入 {key}={value}")


                    elif action == "enter":
                        # 新增：模拟按回车键
                        from selenium.webdriver.common.keys import Keys
                        elem = find_element(driver, locator_type, params)
                        elem.send_keys(Keys.ENTER)
                        step_log.append(f"步骤{i}：按回车键")

                    elif action == "wait":
                        # 格式：.loading 5
                        parts = params.split()
                        selector = parts[0]
                        timeout = int(parts[1]) if len(parts) > 1 else 5
                        WebDriverWait(driver, timeout).until(
                            EC.presence_of_element_located((By.CSS_SELECTOR, selector))
                        )
                        step_log.append(f"步骤{i}：等待元素 {selector}")

                    elif action == "assert_title":
                        if params not in title:
                            raise Exception(f"标题断言失败：期望包含 '{params}'")
                        step_log.append(f"步骤{i}：断言标题包含 '{params}'")

                    elif action == "assert_text":
                        # 格式：[assert_text] [xpath] //div[contains(text(),'成功')]
                        # 或者简单点：[assert_text] [] 成功 (在全页面找)
                        if params:
                            try:
                                # 尝试在 body 里查找包含该文本的元素
                                WebDriverWait(driver, 5).until(
                                    EC.text_to_be_present_in_element((By.TAG_NAME, "body"), params)
                                )
                                step_log.append(f"步骤{i}：断言页面包含文本 '{params}'")
                            except:
                                raise Exception(f"文本断言失败：页面未找到 '{params}'")
                    time.sleep(0.3)

                except Exception as e:
                    step_log.append(f"步骤{i}失败 [{action}] [{locator_type}] {params} -> {str(e)}")
                    raise

        driver.quit()
        status = "PASS"
        error_msg = "\n".join(step_log)

    except Exception as e:
        status = "FAIL"
        screenshot_path = ""
        error_msg = f"异常：{str(e)}\n\n详细步骤：\n" + "\n".join(step_log)
        try:
            if not os.path.exists("static/screenshots"):
                os.makedirs("static/screenshots")

            filename = f"fail_{case.id}_{int(time.time())}.png"
            filepath = f"static/screenshots/{filename}"
            driver.save_screenshot(filepath)
            step_log.append(f"已保存失败截图: {filepath}")
        except Exception as se:
            step_log.append(f"截图失败: {str(se)}")

        error_msg = f"异常：{str(e)}\n\n详细步骤：\n" + "\n".join(step_log)

        try:
            driver.quit()
        except:
            pass

    cost_time = round(time.time() - start_time, 3)

    report = UIReport(
        case_id=case.id,
        case_name=case.name,
        status=status,
        cost_time=cost_time,
        error_msg=error_msg
    )
    db.session.add(report)
    db.session.commit()

    return {
        "status": status,
        "title": title,
        "msg": error_msg,
        "time": cost_time
    }
