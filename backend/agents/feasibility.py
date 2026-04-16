"""
Agent 1: Feasibility Agent
新規注文が pending になったとき、idle AGV の存在を確認する。
Phase 1: スケルトン実装（実際のAI判断はPhase 2で追加）
"""
import logging
from backend.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(name="agents.check_feasibility")
def check_feasibility(order_id: str) -> dict:
    """
    注文の実現可能性を判断する。
    Phase 1では常に feasible=True を返す（シミュレータ内部で処理）。

    Returns:
        {"order_id": str, "feasible": bool, "reason": str}
    """
    logger.info(f"[Feasibility] checking order: {order_id}")
    # Phase 2でClaude APIを呼び出す
    result = {
        "order_id": order_id,
        "feasible": True,
        "reason": "idle AGV available (Phase 1 stub)",
    }
    logger.info(f"[Feasibility] result: {result}")
    return result
