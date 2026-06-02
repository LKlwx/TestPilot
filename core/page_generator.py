"""Page Object 代码自动生成器"""
import re


def _sanitize_class_name(name: str) -> str:
    """将用例名转换为合法的 Python 类名"""
    name = re.sub(r"[^a-zA-Z0-9\u4e00-\u9fa5_]", "_", name)
    if name and name[0].isdigit():
        name = "Page_" + name
    return name or "UnnamedPage"


def generate_page_class(case_name: str, steps: list) -> str:
    """从 UI 用例的步骤列表自动生成 Page Class 代码

    steps: [{"action": "click", "locator_type": "id", "params": "su"}, ...]
    """
    class_name = _sanitize_class_name(case_name) + "Page"
    seen = set()
    locators = []
    methods = []

    for i, step in enumerate(steps, 1):
        action = step["action"]
        loc_type = step.get("locator_type", "xpath")
        params = step.get("params", "")

        # 生成定位器常量名
        if loc_type and params:
            base = params.split("=")[0].strip().replace(" ", "_").replace(".", "_")
            const_name = base.upper() if base.isidentifier() else f"LOC{i}"
            if const_name not in seen:
                seen.add(const_name)
                locators.append(f"    {const_name} = (\"{loc_type}\", \"{params}\")")

            if action == "click":
                methods.append(f"""    def click_loc{i}(self):
        self.click(*self.{const_name})""")
            elif action == "input":
                methods.append(f"""    def input_loc{i}(self, text):
        self.input_text(*self.{const_name}, text)""")
            elif action == "enter":
                methods.append(f"""    def press_enter_loc{i}(self):
        self.press_enter(*self.{const_name})""")

    code = f"""from core.base_page import BasePage


class {class_name}(BasePage):
    \"\"\"由 UI 用例「{case_name}」自动生成\"\"\"
"""

    if locators:
        code += "\n".join(locators) + "\n\n"
    else:
        code += "    pass\n\n"

    if methods:
        code += "\n".join(methods) + "\n"

    return code
