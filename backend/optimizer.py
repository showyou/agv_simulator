"""
optimizer.py — ヘッドレスシミュレーション + 二分探索オプティマイザ

指定シードで 10000 tick シミュレーションを回し、
全tick通じて pending 注文数が MAX_PENDING を超えない
最小の AGV 台数を二分探索で求める。
"""
from __future__ import annotations
import time
from dataclasses import dataclass

from backend.models import AGV, AGVStatus, MapConfig, Order, OrderStatus, SimState
from backend.simulator import _bfs_route, _make_initial_state
from backend import config


MAX_TICKS = 10_000
MAX_PENDING = 100
AGV_SEARCH_MAX = 30  # 探索上限台数


@dataclass
class OptimizeResult:
    seed: int
    min_agvs: int | None  # None = 上限内でも解なし
    elapsed_sec: float
    iterations: int         # 二分探索の試行回数
    detail: list[dict]      # 各試行の記録


# ---- ヘッドレス Simulator ----

class HeadlessSim:
    """asyncio なし・WebSocket なしで tick を回す軽量版シミュレータ。"""

    def __init__(self, seed: int, num_agvs: int) -> None:
        original = config.NUM_AGVS
        config.NUM_AGVS = num_agvs
        self.state, self.seed = _make_initial_state(seed)
        config.NUM_AGVS = original
        self._order_counter = 0

    def run(self, ticks: int) -> int:
        """ticks 回実行し、最大 pending 数を返す。"""
        max_pending = 0
        for _ in range(ticks):
            self._tick()
            p = self.state.stats["pending"]
            if p > max_pending:
                max_pending = p
            # 早期打ち切り: 超えた時点で終了
            if max_pending > MAX_PENDING:
                return max_pending
        return max_pending

    def _tick(self) -> None:
        state = self.state
        state.tick += 1

        if state.tick % config.ORDER_SPAWN_INTERVAL == 0:
            self._add_order()

        self._move_agvs()
        self._run_feasibility()
        self._run_debugger()
        self._run_idle_charge()

        state.stats["pending"] = sum(
            1 for o in state.orders.values() if o.status == OrderStatus.pending
        )

    def _add_order(self) -> None:
        import random
        self._order_counter += 1
        rng = random.Random(self.seed + self.state.tick)  # tick依存シードで再現性を保つ
        customer_pos = rng.choice(self.state.map.customer_positions)
        items = ["食料品A", "日用品B", "電化製品C", "衣類D", "書籍E"]
        item = rng.choice(items)
        order = Order(
            id=f"order-{self._order_counter:05d}",
            customer_pos=customer_pos,
            item=item,
        )
        self.state.orders[order.id] = order

    def _needs_charge(self, agv: AGV) -> bool:
        return agv.battery <= config.CHARGE_THRESHOLD

    def _must_return_to_charge(self, agv: AGV) -> bool:
        wx, wy = self.state.map.warehouse_pos
        dist = abs(agv.pos[0] - wx) + abs(agv.pos[1] - wy)
        needed = dist * config.AGV_BATTERY_DRAIN * config.CHARGE_MARGIN
        return agv.battery <= needed

    def _send_to_charge(self, agv: AGV) -> None:
        warehouse = self.state.map.warehouse_pos
        agv.route = _bfs_route(agv.pos, warehouse, self.state.map.width, self.state.map.height)
        agv.status = AGVStatus.charging

    def _send_to_store(self, agv: AGV) -> None:
        store = self.state.map.store_pos
        agv.route = _bfs_route(agv.pos, store, self.state.map.width, self.state.map.height)
        agv.status = AGVStatus.moving if agv.route else AGVStatus.idle

    def _move_agvs(self) -> None:
        for agv in self.state.agvs.values():
            if agv.status == AGVStatus.charging:
                if agv.pos == self.state.map.warehouse_pos and not agv.route:
                    agv.battery = min(1.0, agv.battery + config.CHARGE_RATE)
                    if agv.battery >= config.CHARGE_FULL:
                        self._send_to_store(agv)
                    continue
                agv.battery = max(0.0, agv.battery - config.AGV_BATTERY_DRAIN)
                if agv.battery <= 0:
                    agv.route = []
                    self.state.stats["battery_dead"] = self.state.stats.get("battery_dead", 0) + 1
                    continue
                if agv.route:
                    agv.pos = agv.route.pop(0)
                continue

            if agv.status != AGVStatus.idle:
                agv.battery = max(0.0, agv.battery - config.AGV_BATTERY_DRAIN)
                if agv.battery <= 0:
                    agv.status = AGVStatus.idle
                    agv.route = []
                    if agv.cargo:
                        order = self.state.orders.get(agv.cargo)
                        if order:
                            order.status = OrderStatus.failed
                    agv.cargo = None
                    self.state.stats["battery_dead"] = self.state.stats.get("battery_dead", 0) + 1
                    continue
                if self._must_return_to_charge(agv) or agv.battery <= config.CHARGE_ABORT_THRESHOLD:
                    if agv.cargo:
                        order = self.state.orders.get(agv.cargo)
                        if order:
                            order.status = OrderStatus.pending
                            order.assigned_agv = None
                    agv.cargo = None
                    self._send_to_charge(agv)
                    continue

            if agv.status == AGVStatus.idle and self._needs_charge(agv):
                self._send_to_charge(agv)
                continue

            if not agv.route:
                if agv.status in (AGVStatus.moving, AGVStatus.delivering):
                    agv.status = AGVStatus.idle
                continue

            agv.pos = agv.route.pop(0)

            if not agv.route:
                if agv.status == AGVStatus.moving:
                    if self._needs_charge(agv):
                        self._send_to_charge(agv)
                    else:
                        agv.status = AGVStatus.idle
                elif agv.status == AGVStatus.delivering and agv.cargo:
                    order = self.state.orders.get(agv.cargo)
                    if order and agv.pos == order.customer_pos:
                        order.status = OrderStatus.delivered
                        agv.cargo = None
                        if self._needs_charge(agv):
                            self._send_to_charge(agv)
                        else:
                            self._send_to_store(agv)

    def _run_feasibility(self) -> None:
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
            agv = min(
                idle_agvs,
                key=lambda a: abs(a.pos[0] - order.customer_pos[0]) + abs(a.pos[1] - order.customer_pos[1]),
            )
            route = _bfs_route(agv.pos, order.customer_pos, self.state.map.width, self.state.map.height)
            agv.route = route
            agv.cargo = order.id
            agv.status = AGVStatus.delivering
            order.status = OrderStatus.in_transit
            order.assigned_agv = agv.id

    def _run_debugger(self) -> None:
        for order in self.state.orders.values():
            if order.status != OrderStatus.in_transit or not order.assigned_agv:
                continue
            agv = self.state.agvs.get(order.assigned_agv)
            if agv and agv.status == AGVStatus.idle and agv.cargo != order.id:
                order.status = OrderStatus.failed

    def _run_idle_charge(self) -> None:
        for agv in self.state.agvs.values():
            if agv.status != AGVStatus.idle or agv.cargo is not None:
                continue
            if agv.battery >= config.CHARGE_FULL:
                continue
            self._send_to_charge(agv)


# ---- 二分探索 ----

def can_handle(seed: int, num_agvs: int) -> tuple[bool, int]:
    """num_agvs 台で MAX_TICKS tick 間、pending <= MAX_PENDING を維持できるか。"""
    sim = HeadlessSim(seed=seed, num_agvs=num_agvs)
    max_pending = sim.run(MAX_TICKS)
    return max_pending <= MAX_PENDING, max_pending


def optimize(seed: int, progress_cb=None) -> OptimizeResult:
    """二分探索で最小 AGV 台数を求める。"""
    t0 = time.time()
    detail = []
    iterations = 0

    # まず上限で解けるか確認
    ok, mp = can_handle(seed, AGV_SEARCH_MAX)
    iterations += 1
    detail.append({"num_agvs": AGV_SEARCH_MAX, "max_pending": mp, "ok": ok})
    if progress_cb:
        progress_cb(detail[-1])

    if not ok:
        return OptimizeResult(
            seed=seed, min_agvs=None,
            elapsed_sec=time.time() - t0,
            iterations=iterations, detail=detail,
        )

    lo, hi = 1, AGV_SEARCH_MAX
    while lo < hi:
        mid = (lo + hi) // 2
        ok, mp = can_handle(seed, mid)
        iterations += 1
        detail.append({"num_agvs": mid, "max_pending": mp, "ok": ok})
        if progress_cb:
            progress_cb(detail[-1])
        if ok:
            hi = mid
        else:
            lo = mid + 1

    return OptimizeResult(
        seed=seed, min_agvs=lo,
        elapsed_sec=time.time() - t0,
        iterations=iterations, detail=detail,
    )
