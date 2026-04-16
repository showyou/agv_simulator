"""
Agent 3: Debugger Agent
AGV が目的地に到着したとき（tickごとに監視）、完了確認・異常検知を行う。
Phase 1: スケルトン実装（実際のAI判断はPhase 2で追加）
"""
import logging
from backend.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(name="agents.verify_delivery")
def verify_delivery(order_id: str) -> dict:
    """
    配送完了を確認し、異常があれば再試行フラグを立てる。
    Phase 1ではシミュレータが直接ステータスを更新するため、
    このタスクは確認・ログ記録のみ行う。

    Returns:
        {"order_id": str, "verified": bool, "retry": bool, "reason": str}
    """
    logger.info(f"[Debugger] verifying delivery: {order_id}")
    # Phase 2でClaude APIを使った異常判断を実装
    result = {
        "order_id": order_id,
        "verified": True,
        "retry": False,
        "reason": "delivery confirmed (Phase 1 stub)",
    }
    logger.info(f"[Debugger] result: {result}")
    return result
