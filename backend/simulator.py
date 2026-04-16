from __future__ import annotations
import asyncio
import random
import time
import uuid
from collections import deque
from typing import Callable, Awaitable

from backend.models import AGV, AGVStatus, MapConfig, Order, OrderStatus, SimState
from backend import config


def _bfs_route(
    start: tuple[int, int],
    goal: tuple[int, int],
    width: int,
    height: int,
) -> list[tuple[int, int]]:
    """BFSで経路探索（障害物なし）。startを含まない座標リストを返す。"""
    if start == goal:
        return []
    queue: deque[tuple[tuple[int, int], list[tuple[int, int]]]] = deque()
    queue.append((start, []))
    visited = {start}
    while queue:
        pos, path = queue.popleft()
        x, y = pos
        for dx, dy in [(1, 0), (-1, 0), (0, 1), (0, -1)]:
            nx, ny = x + dx, y + dy
            if not (0 <= nx < width and 0 <= ny < height):
                continue
            npos = (nx, ny)
            if npos in visited:
                continue
            new_path = path + [npos]
            if npos == goal:
                return new_path
            visited.add(npos)
            queue.append((npos, new_path))
    return []


def _make_initial_state() -> SimState:
    map_cfg = MapConfig(
        width=config.MAP_WIDTH,
        height=config.MAP_HEIGHT,
        store_pos=(5, 5),
        warehouse_pos=(45, 45),
        customer_positions=[
            (
                random.randint(5, config.MAP_WIDTH - 5),
                random.randint(5, config.MAP_HEIGHT - 5),
            )
            for _ in range(config.NUM_CUSTOMERS)
        ],
    )

    agvs: dict[str, AGV] = {}
    for i in range(config.NUM_AGVS):
        agv_id = f"agv-{i + 1:03d}"
        # 商店付近に初期配置
        pos = (map_cfg.store_pos[0] + i, map_cfg.store_pos[1])
        agvs[agv_id] = AGV(
            id=agv_id,
            pos=pos,
            speed=config.AGV_SPEED,
            battery=1.0,
        )

    state = SimState(map=map_cfg, agvs=agvs)
    state.stats = {"delivered": 0, "pending": 0, "failed": 0}
    return state


class Simulator:
    def __init__(self) -> None:
        self.state: SimState = _make_initial_state()
        self._task: asyncio.Task | None = None
        self._broadcast_cb: Callable[[dict], Awaitable[None]] | None = None
        self._order_counter = 0

    def set_broadcast(self, cb: Callable[[dict], Awaitable[None]]) -> None:
        self._broadcast_cb = cb

    # ---- 公開コントロール ----

    def start(self) -> None:
        if self.state.running:
            return
        self.state.running = True
        self._task = asyncio.create_task(self._loop())

    def stop(self) -> None:
        self.state.running = False
        if self._task:
            self._task.cancel()
            self._task = None

    def reset(self) -> None:
        self.stop()
        self.state = _make_initial_state()
        self._order_counter = 0  # order IDをリセット (#3)

    def add_order(self, customer_pos: tuple[int, int] | None = None, item: str | None = None) -> Order:
        self._order_counter += 1
        if customer_pos is None:
            customer_pos = random.choice(self.state.map.customer_positions)
        if item is None:
            items = ["食料品A", "日用品B", "電化製品C", "衣類D", "書籍E"]
            item = random.choice(items)
        order = Order(
            id=f"order-{self._order_counter:04d}",
            customer_pos=customer_pos,
            item=item,
        )
        self.state.orders[order.id] = order
        self._log(f"注文発生: {order.id} ({order.item}) → {order.customer_pos}")
        return order

    def get_config(self) -> dict:
        return {
            "map_width": self.state.map.width,
            "map_height": self.state.map.height,
            "num_agvs": len(self.state.agvs),
            "num_customers": len(self.state.map.customer_positions),
            "tick_interval": config.TICK_INTERVAL,
            "order_spawn_interval": config.ORDER_SPAWN_INTERVAL,
            "agv_speed": config.AGV_SPEED,
            "agv_battery_drain": config.AGV_BATTERY_DRAIN,
        }

    def update_config(self, data: dict) -> None:
        if "tick_interval" in data:
            config.TICK_INTERVAL = float(data["tick_interval"])
        if "order_spawn_interval" in data:
            config.ORDER_SPAWN_INTERVAL = int(data["order_spawn_interval"])
        if "agv_speed" in data:
            config.AGV_SPEED = float(data["agv_speed"])
            for agv in self.state.agvs.values():
                agv.speed = config.AGV_SPEED

    # ---- シミュレーションループ ----

    async def _loop(self) -> None:
        while self.state.running:
            await asyncio.sleep(config.TICK_INTERVAL)
            self._tick()
            if self._broadcast_cb:
                await self._broadcast_cb(self.state.to_dict())

    def _tick(self) -> None:
        state = self.state
        state.tick += 1

        # 注文発生
        if state.tick % config.ORDER_SPAWN_INTERVAL == 0:
            self.add_order()

        # AGV移動
        self._move_agvs()

        # エージェント処理（同期簡易版）
        self._run_feasibility()
        self._run_debugger()

        # 統計更新
        state.stats["delivered"] = sum(
            1 for o in state.orders.values() if o.status == OrderStatus.delivered
        )
        state.stats["pending"] = sum(
            1 for o in state.orders.values() if o.status == OrderStatus.pending
        )
        state.stats["failed"] = sum(
            1 for o in state.orders.values() if o.status == OrderStatus.failed
        )

    def _needs_charge(self, agv: AGV) -> bool:
        return agv.battery <= config.CHARGE_THRESHOLD

    def _send_to_charge(self, agv: AGV) -> None:
        """倉庫へ充電に向かわせる。"""
        warehouse = self.state.map.warehouse_pos
        if agv.pos == warehouse:
            agv.status = AGVStatus.charging
            agv.route = []
        else:
            agv.route = _bfs_route(agv.pos, warehouse, self.state.map.width, self.state.map.height)
            agv.status = AGVStatus.charging

    def _send_to_store(self, agv: AGV) -> None:
        """商店へ帰還させる。"""
        store = self.state.map.store_pos
        agv.route = _bfs_route(agv.pos, store, self.state.map.width, self.state.map.height)
        agv.status = AGVStatus.moving if agv.route else AGVStatus.idle

    def _move_agvs(self) -> None:
        for agv in self.state.agvs.values():

            # --- 充電中 ---
            if agv.status == AGVStatus.charging:
                if agv.pos == self.state.map.warehouse_pos and not agv.route:
                    # 倉庫に滞在中: バッテリー充電
                    agv.battery = min(1.0, agv.battery + config.CHARGE_RATE)
                    if agv.battery >= config.CHARGE_FULL:
                        self._log(f"AGV {agv.id} 充電完了 ({agv.battery:.0%}) → 商店へ帰還")
                        self._send_to_store(agv)
                    continue
                # 倉庫へ移動中（充電ステータスのまま走行）
                agv.battery = max(0.0, agv.battery - config.AGV_BATTERY_DRAIN)
                if agv.battery <= 0:
                    agv.route = []
                    self._log(f"AGV {agv.id} 充電移動中にバッテリー切れ → その場で停止")
                    continue
                if agv.route:
                    agv.pos = agv.route.pop(0)
                continue

            # --- バッテリー消費（moving / delivering） ---
            if agv.status != AGVStatus.idle:
                agv.battery = max(0.0, agv.battery - config.AGV_BATTERY_DRAIN)
                if agv.battery <= 0:
                    agv.status = AGVStatus.idle
                    agv.route = []
                    if agv.cargo:
                        order = self.state.orders.get(agv.cargo)
                        if order:
                            order.status = OrderStatus.failed
                            self._log(f"AGV {agv.id} バッテリー切れ: {agv.cargo} 配送失敗")
                    agv.cargo = None
                    continue
                # 危険域に入ったら配送・移動を中断して充電へ (#6)
                if agv.battery <= config.CHARGE_ABORT_THRESHOLD:
                    if agv.cargo:
                        order = self.state.orders.get(agv.cargo)
                        if order:
                            order.status = OrderStatus.pending  # 再度 pending に戻す
                            order.assigned_agv = None
                            self._log(f"AGV {agv.id} 危険バッテリー ({agv.battery:.0%})、{agv.cargo} を差し戻し → 充電へ")
                    agv.cargo = None
                    self._send_to_charge(agv)
                    continue

            # --- idle で低バッテリー → 充電へ ---
            if agv.status == AGVStatus.idle and self._needs_charge(agv):
                self._log(f"AGV {agv.id} 低バッテリー ({agv.battery:.0%}) → 充電へ")
                self._send_to_charge(agv)
                continue

            if not agv.route:
                if agv.status in (AGVStatus.moving, AGVStatus.delivering):
                    agv.status = AGVStatus.idle
                continue

            # --- 次の座標へ移動 ---
            next_pos = agv.route.pop(0)
            agv.pos = next_pos

            # 目的地到着チェック（routeが空になった）
            if not agv.route:
                if agv.status == AGVStatus.moving:
                    # 商店へ帰還完了
                    if self._needs_charge(agv):
                        self._log(f"AGV {agv.id} 帰還完了、低バッテリー ({agv.battery:.0%}) → 充電へ")
                        self._send_to_charge(agv)
                    else:
                        agv.status = AGVStatus.idle

                elif agv.status == AGVStatus.delivering and agv.cargo:
                    order = self.state.orders.get(agv.cargo)
                    if order and agv.pos == order.customer_pos:
                        order.status = OrderStatus.delivered
                        self._log(f"AGV {agv.id} 配送完了: {agv.cargo} → {agv.pos}")
                        agv.cargo = None
                        if self._needs_charge(agv):
                            self._log(f"AGV {agv.id} 低バッテリー ({agv.battery:.0%}) → 充電へ")
                            self._send_to_charge(agv)
                        else:
                            self._send_to_store(agv)

    # ---- エージェント（同期版スケルトン） ----

    def _run_feasibility(self) -> None:
        """Feasibility Agent: pending注文を確認し、idle AGVがあれば Builder を呼ぶ。"""
        for order in list(self.state.orders.values()):
            if order.status != OrderStatus.pending:
                continue
            idle_agvs = [
                agv for agv in self.state.agvs.values()
                if agv.status == AGVStatus.idle and agv.cargo is None
                   and agv.battery > config.CHARGE_REFUSE_THRESHOLD
            ]
            if not idle_agvs:
                continue
            # 最近傍AGVを選択
            agv = min(
                idle_agvs,
                key=lambda a: abs(a.pos[0] - order.customer_pos[0]) + abs(a.pos[1] - order.customer_pos[1]),
            )
            self._log(f"[Feasibility] {order.id} → AGV {agv.id} に割り当て")
            self._build_route(order, agv)

    def _build_route(self, order: Order, agv: AGV) -> None:
        """Builder Agent: ルート生成してAGVに指示。"""
        route = _bfs_route(
            agv.pos, order.customer_pos,
            self.state.map.width, self.state.map.height
        )
        agv.route = route
        agv.cargo = order.id
        agv.status = AGVStatus.delivering
        order.status = OrderStatus.in_transit
        order.assigned_agv = agv.id
        self._log(f"[Builder] {order.id} ルート生成: {len(route)}ステップ")

    def _run_debugger(self) -> None:
        """Debugger Agent: in_transit注文でAGVがスタックしていないか確認。"""
        for order in self.state.orders.values():
            if order.status != OrderStatus.in_transit:
                continue
            if not order.assigned_agv:
                continue
            agv = self.state.agvs.get(order.assigned_agv)
            if agv is None:
                continue
            # AGVがidle状態かつcargoがない場合、注文が孤立している → failedにする
            if agv.status == AGVStatus.idle and agv.cargo != order.id:
                self._log(f"[Debugger] 異常検知: {order.id} → failed に変更")
                order.status = OrderStatus.failed

    def _log(self, message: str) -> None:
        event = {"tick": self.state.tick, "message": message, "ts": time.time()}
        self.state.events.append(event)
        print(f"[tick {self.state.tick}] {message}")
