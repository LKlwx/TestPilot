import time
from extensions import db
from models import UIReport
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager


def run_ui_case(case):
    start_time = time.time()
    title = ""
    step_log = []

    try:
        chrome_options = Options()
        chrome_options.add_argument("--headless=new")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")

        driver = webdriver.Chrome(options=chrome_options)
        driver.get(case.url)
        step_log.append("打开页面：" + case.url)
        time.sleep(0.5)

        title = driver.title
        step_log.append("页面标题：" + title)

        steps = case.steps or ""
        if steps:
            lines = steps.strip().split("\n")
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                step_log.append("执行步骤：" + line)
                if line.startswith("输入"):
                    parts = line.split()
                    if len(parts) >= 3:
                        key = parts[1]
                        value = parts[2]
                        try:
                            inp = driver.find_element(By.NAME, key)
                            inp.clear()
                            inp.send_keys(value)
                            step_log.append(f"输入成功：{key} = {value}")
                        except:
                            step_log.append("输入元素未找到：" + key)
                elif line.startswith("点击"):
                    parts = line.split()
                    if len(parts) >= 2:
                        btn_text = parts[1]
                        try:
                            btn = driver.find_element(By.XPATH, f"//*[text()='{btn_text}']")
                            btn.click()
                            step_log.append("点击成功：" + btn_text)
                        except:
                            try:
                                btn = driver.find_element(By.XPATH, f"//*[@value='{btn_text}']")
                                btn.click()
                                step_log.append("点击成功：" + btn_text)
                            except:
                                step_log.append("点击失败：" + btn_text)
                time.sleep(0.3)

        driver.quit()
        status = "PASS"
        error_msg = "\n".join(step_log)

    except Exception as e:
        status = "FAIL"
        error_msg = f"异常：{str(e)}"

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
