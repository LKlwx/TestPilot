"""生成 Allure 报告（含历史趋势）"""

import os
import shutil
import subprocess
import sys

ALLURE_RESULTS = "allure-results"
ALLURE_REPORT = "allure-report"
HISTORY = "history"


def main():
    # 保留上一份报告的历史数据
    history_src = os.path.join(ALLURE_RESULTS, HISTORY)
    history_dst = os.path.join(ALLURE_REPORT, HISTORY)
    if os.path.exists(history_dst):
        if os.path.exists(history_src):
            shutil.rmtree(history_src)
        shutil.copytree(history_dst, history_src)

    # 生成报告
    ret = subprocess.run(["allure", "generate", ALLURE_RESULTS, "-o", ALLURE_REPORT, "--clean"], check=False)
    sys.exit(ret.returncode)


if __name__ == "__main__":
    main()
