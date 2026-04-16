"""
Agent 2: Builder Agent
Feasibility Agent から配送可能通知を受け、ルートを生成して AGV に指示する。
Phase 1: スケルトン実装（実際のAI判断はPhase 2で追加）
"""
import logging
from backend.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(name="agents.build_route")
def build_route(order_id: str, agv_id: str) -> dict:
    """
    指定されたAGVに対して配送ルートを生成・指示する。
    Phase 1ではシミュレータが直接BFSでルートを設定するため、
    このタスクは確認・ログ記録のみ行う。

    Returns:
        {"order_id": str, "agv_id": str, "status": str, "steps": int}
    """
    logger.info(f"[Builder] building route: order={order_id}, agv={agv_id}")
    # Phase 2でClaude APIを使った最適ルート計算を実装
    result = {
        "order_id": order_id,
        "agv_id": agv_id,
        "status": "route_assigned",
        "steps": -1,  # Phase 1: シミュレータが算出
    }
    logger.info(f"[Builder] result: {result}")
    return result
