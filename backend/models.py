from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional
import time


class AGVStatus(str, Enum):
    idle = "idle"
    moving = "moving"
    delivering = "delivering"
    charging = "charging"


class OrderStatus(str, Enum):
    pending = "pending"
    assigned = "assigned"
    in_transit = "in_transit"
    delivered = "delivered"
    failed = "failed"


@dataclass
class MapConfig:
    width: int = 50
    height: int = 50
    store_pos: tuple[int, int] = (5, 5)
    warehouse_pos: tuple[int, int] = (45, 45)
    customer_positions: list[tuple[int, int]] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "width": self.width,
            "height": self.height,
            "store_pos": list(self.store_pos),
            "warehouse_pos": list(self.warehouse_pos),
            "customer_positions": [list(p) for p in self.customer_positions],
        }


@dataclass
class Order:
    id: str
    customer_pos: tuple[int, int]
    item: str
    status: OrderStatus = OrderStatus.pending
    created_at: float = field(default_factory=time.time)
    assigned_agv: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "customer_pos": list(self.customer_pos),
            "item": self.item,
            "status": self.status.value,
            "created_at": self.created_at,
            "assigned_agv": self.assigned_agv,
        }


@dataclass
class AGV:
    id: str
    pos: tuple[int, int]
    status: AGVStatus = AGVStatus.idle
    cargo: Optional[str] = None  # Order ID
    route: list[tuple[int, int]] = field(default_factory=list)
    speed: float = 1.0
    battery: float = 1.0

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "pos": list(self.pos),
            "status": self.status.value,
            "cargo": self.cargo,
            "route": [list(p) for p in self.route],
            "speed": self.speed,
            "battery": self.battery,
        }


@dataclass
class SimState:
    tick: int = 0
    agvs: dict[str, AGV] = field(default_factory=dict)
    orders: dict[str, Order] = field(default_factory=dict)
    map: MapConfig = field(default_factory=MapConfig)
    stats: dict = field(default_factory=lambda: {"delivered": 0, "pending": 0, "failed": 0})
    running: bool = False
    events: list[dict] = field(default_factory=list)  # 最新イベントログ

    def to_dict(self) -> dict:
        return {
            "tick": self.tick,
            "agvs": {k: v.to_dict() for k, v in self.agvs.items()},
            "orders": {k: v.to_dict() for k, v in self.orders.items()},
            "map": self.map.to_dict(),
            "stats": self.stats,
            "running": self.running,
            "events": self.events[-20:],  # 最新20件
        }
