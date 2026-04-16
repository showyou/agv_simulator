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
CHARGE_THRESHOLD = 0.20   # バッテリーがこの値以下で充電へ向かう
CHARGE_RATE = 0.005       # 1tickあたりの充電量（0.5%）
CHARGE_FULL = 0.95        # この値以上で充電完了とする
