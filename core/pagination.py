from flask import request


def paginate(query, page=None, page_size=None, max_page_size=100, order_by=None):
    """统一分页查询工具
    用法:
        query = TestCase.query
        result = paginate(query, order_by=TestCase.id.desc())
        # result.page, result.page_size, result.total, result.items
    """
    if page is None:
        page = request.args.get("page", 1, type=int)
    if page_size is None:
        page_size = request.args.get("page_size", 10, type=int)
    page_size = min(page_size, max_page_size)

    total = query.count()
    if order_by is not None:
        query = query.order_by(order_by)
    items = query.offset((page - 1) * page_size).limit(page_size).all()

    return PaginationResult(page, page_size, total, items)


class PaginationResult:
    def __init__(self, page, page_size, total, items):
        self.page = page
        self.page_size = page_size
        self.total = total
        self.total_pages = (total + page_size - 1) // page_size
        self.items = items
