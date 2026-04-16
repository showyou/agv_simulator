from __future__ import annotations
import asyncio
import json
from contextlib import asynccontextmanager
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from backend.simulator import Simulator
from backend.optimizer import optimize as run_optimize, OptimizeResult

# ---- シミュレータのシングルトン ----
sim = Simulator()

# ---- WebSocket接続マネージャ ----
class ConnectionManager:
    def __init__(self) -> None:
        self.active: list[WebSocket] = []

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        self.active.append(ws)

    def disconnect(self, ws: WebSocket) -> None:
        self.active.remove(ws)

    async def broadcast(self, data: dict) -> None:
        msg = json.dumps(data, ensure_ascii=False)
        dead = []
        for ws in self.active:
            try:
                await ws.send_text(msg)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.active.remove(ws)


manager = ConnectionManager()

# ---- オプティマイザ状態 ----
_optimizer_executor = ThreadPoolExecutor(max_workers=1)
_optimize_state: dict = {"status": "idle", "result": None, "progress": []}

@asynccontextmanager
async def lifespan(app: FastAPI):
    sim.set_broadcast(manager.broadcast)
    yield
    _optimizer_executor.shutdown(wait=False)

app = FastAPI(title="Distribution Sim", lifespan=lifespan)

# フロントエンド静的ファイル配信
frontend_dir = Path(__file__).parent.parent / "frontend"
app.mount("/static", StaticFiles(directory=str(frontend_dir)), name="static")


# ---- REST API ----

@app.get("/")
async def root():
    return FileResponse(str(frontend_dir / "index.html"))

@app.get("/state")
async def get_state():
    data = sim.state.to_dict()
    data["seed"] = sim.current_seed
    return data

@app.post("/start")
async def start():
    sim.start()
    return {"status": "started"}

@app.post("/stop")
async def stop():
    sim.stop()
    return {"status": "stopped"}

@app.post("/reset")
async def reset(body: dict = {}):
    seed = body.get("seed")
    if seed is not None:
        seed = int(seed)
    sim.reset(seed=seed)
    sim.set_broadcast(manager.broadcast)
    return {"status": "reset", "seed": sim.current_seed}

@app.post("/order")
async def add_order(body: dict = {}):
    customer_pos = None
    item = None
    if "customer_pos" in body:
        cp = body["customer_pos"]
        customer_pos = (int(cp[0]), int(cp[1]))
    if "item" in body:
        item = body["item"]
    order = sim.add_order(customer_pos=customer_pos, item=item)
    return order.to_dict()

@app.get("/config")
async def get_config():
    return sim.get_config()

@app.post("/config")
async def update_config(body: dict):
    sim.update_config(body)
    return sim.get_config()


# ---- オプティマイザ ----

@app.post("/optimize")
async def start_optimize(body: dict):
    if _optimize_state["status"] == "running":
        return {"error": "already running"}
    seed = int(body.get("seed", 0))
    _optimize_state.update({"status": "running", "result": None, "progress": [], "seed": seed})

    def _run():
        def cb(d):
            _optimize_state["progress"].append(d)
        result = run_optimize(seed, progress_cb=cb)
        _optimize_state["status"] = "done"
        _optimize_state["result"] = {
            "seed": result.seed,
            "min_agvs": result.min_agvs,
            "elapsed_sec": round(result.elapsed_sec, 2),
            "iterations": result.iterations,
            "detail": result.detail,
        }

    loop = asyncio.get_event_loop()
    loop.run_in_executor(_optimizer_executor, _run)
    return {"status": "started", "seed": seed}

@app.get("/optimize/result")
async def get_optimize_result():
    return _optimize_state


# ---- WebSocket ----

@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await manager.connect(ws)
    # 接続直後に現在状態を送信
    await ws.send_text(json.dumps(sim.state.to_dict(), ensure_ascii=False))
    try:
        while True:
            # クライアントからのメッセージ（将来用、現在は捨てる）
            await ws.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(ws)
