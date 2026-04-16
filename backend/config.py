import os

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

MAP_WIDTH = 50
MAP_HEIGHT = 50
NUM_AGVS = 5
NUM_CUSTOMERS = 10
TICK_INTERVAL = 0.5
ORDER_SPAWN_INTERVAL = 10
AGV_SPEED = 1.0
AGV_BATTERY_DRAIN = 0.002
CHARGE_THRESHOLD = 0.20   # バッテリーがこの値以下で充電へ向かう（idle時）
CHARGE_REFUSE_THRESHOLD = 0.30  # この値以下のAGVは新規指示を受けない
CHARGE_ABORT_THRESHOLD = 0.10   # フォールバック: この値以下なら無条件で充電へ中断
CHARGE_MARGIN = 1.5             # 充電スポットまでの必要バッテリーに掛ける安全係数
CHARGE_RATE = 0.005       # 1tickあたりの充電量（0.5%）
CHARGE_FULL = 0.95        # この値以上で充電完了とする
