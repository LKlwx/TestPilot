"""测试数据工厂

以 Faker 为后端的随机测试数据生成器：

    from core.data_factory import DataFactory

    DataFactory.username()       # "williamsmichelle" 或 "user_a3f9x"
    DataFactory.phone()          # "13855239017"
    DataFactory.email()          # "b7k2@example.com"
    DataFactory.name()           # "张伟" 或 "李娜"
    DataFactory.password()       # "aB3dE7xY"
"""

import logging
import random
import uuid

logger = logging.getLogger(__name__)

try:
    from faker import Faker

    _fake = Faker("zh_CN")
    _HAS_FAKER = True
except ImportError:
    _HAS_FAKER = False
    logger.warning("Faker 未安装，DataFactory 降级为 uuid 模式")


def _fallback(prefix, length=5):
    return f"{prefix}{uuid.uuid4().hex[:length]}"


class DataFactory:
    """随机测试数据生成器，每次调用返回独立值"""

    @staticmethod
    def username():
        if _HAS_FAKER:
            return _fake.user_name()
        return _fallback("user_")

    @staticmethod
    def password(min_len=8, max_len=16):
        if _HAS_FAKER:
            return _fake.password(length=random.randint(min_len, max_len))
        length = min_len if min_len >= 8 else 8
        digits = random.choices("0123456789", k=min(length // 3, 1) or 1)
        letters = random.choices(uuid.uuid4().hex.replace("-", ""), k=length - len(digits))
        chars = letters + digits
        random.shuffle(chars)
        return "".join(chars)

    @staticmethod
    def phone():
        if _HAS_FAKER:
            return _fake.phone_number()
        prefixes = ["13", "15", "17", "18", "19"]
        return random.choice(prefixes) + "".join(random.choices("0123456789", k=9))

    @staticmethod
    def email():
        if _HAS_FAKER:
            return _fake.email()
        domains = ["example.com", "testmail.com", "demo.org"]
        name = uuid.uuid4().hex[:4]
        return f"{name}@{random.choice(domains)}"

    @staticmethod
    def url():
        paths = ["/api/user", "/api/order", "/api/auth", "/api/data", "/api/product"]
        return random.choice(paths)

    @staticmethod
    def name():
        if _HAS_FAKER:
            return _fake.name()
        surnames = "赵钱孙李周吴郑王冯陈褚卫"
        given = "志伟国强春建华志军洪波浩杰锋凯超"
        return random.choice(surnames) + "".join(random.choices(given, k=random.randint(1, 2)))
