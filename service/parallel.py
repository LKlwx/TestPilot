"""分布式并行执行引擎

将用例集拆分为多个 chunk，分发到多个 Celery Worker 并行执行，最后合并结果。

用法：
    from service.parallel import dispatch_parallel

    task = dispatch_parallel.delay(
        ids=[1,2,3,4,5,6,7,8,9,10],
        user_id=1, worker_count=4,
    )
"""

import math
from datetime import datetime

from core.logger import get_logger
from extensions import db
from models import BatchResult, BatchTask

logger = get_logger(__name__)


def split_ids(ids, worker_count):
    """将用例 ID 列表等量拆分为 N 份

    Args:
        ids: 用例 ID 列表
        worker_count: 拆分份数

    Returns:
        子集列表，如 [[1,2,3], [4,5,6], [7,8,9], [10]]]
    """
    if worker_count <= 0:
        return [ids]
    k = min(worker_count, len(ids))
    if k == 0:
        return []
    chunk_size = math.ceil(len(ids) / k)
    return [ids[i : i + chunk_size] for i in range(0, len(ids), chunk_size)]


def save_chunk_results(chunk_id, chunk_results, batch_id):
    """保存单个 chunk 的执行结果到 BatchResult"""
    saved = 0
    for cr in chunk_results:
        try:
            r = BatchResult(
                batch_id=batch_id,
                case_id=cr.get("case_id", cr.get("id", 0)),
                case_name=cr.get("name", ""),
                status=cr.get("status", "ERROR"),
                cost_time=cr.get("time", 0),
                response_code=cr.get("code", 0),
                error_msg=cr.get("error") or cr.get("msg", ""),
            )
            db.session.add(r)
            saved += 1
        except Exception as e:
            logger.error("save_chunk_results chunk=%d: %s", chunk_id, str(e))
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise
    return saved


def merge_chunks(chunks_data, batch_id, user_id):
    """合并所有 chunk 结果，统计批次数据

    Args:
        chunks_data: 每个 chunk 的 (chunk_id, case_results) 列表
        batch_id: BatchTask ID
        user_id: 创建者用户 ID
    """
    batch = BatchTask.query.get(batch_id)
    if not batch:
        logger.error("merge_chunks: batch %s not found", batch_id)
        return

    total = 0
    for chunk_id, case_results in chunks_data:
        if not case_results:
            continue
        for cr in case_results:
            status = cr.get("status", "ERROR")
            total += 1
            if status == "PASS":
                batch.passed += 1
            else:
                batch.failed += 1

    batch.total = total
    batch.end_time = datetime.now()
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        logger.error("merge_chunks: commit batch %s failed", batch_id)
        return

    logger.info("merge_chunks: batch=%s, total=%d, pass=%d, fail=%d", batch_id, total, batch.passed, batch.failed)
    return {"batch_id": batch_id, "total": total, "passed": batch.passed, "failed": batch.failed}
