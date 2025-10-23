import sys
import os
import asyncio
import time
import base64
import math
import threading

# ---必要なライブラリをインポート---
from fastapi import FastAPI, APIRouter, HTTPException, BackgroundTasks, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from fastapi.responses import JSONResponse, StreamingResponse
import uvicorn

# ---Hakoniwaシミュレータ連携部分---
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import libs.hakosim as hakosim
import libs.hakosim_types as hakosim_types
from hakoniwa_pdu.pdu_msgs.hako_msgs.pdu_pytype_GameControllerOperation import GameControllerOperation

# ---グローバル変数---
hako: hakosim.MultirotorClient = None
drone_controller = None
camera_hub: "CameraHub | None" = None

# ---Pydanticモデル定義---
class DroneStatus(BaseModel):
    armed: bool
    is_flying: bool = Field(..., alias="flying")
    class Config:
        validate_by_name = True
        allow_population_by_field_name = True

class JoystickInput(BaseModel):
    dx: float = Field(..., ge=-1.0, le=1.0)
    dy: float = Field(..., ge=-1.0, le=1.0)
    dz: float = Field(..., ge=-1.0, le=1.0)
    yaw: float = Field(..., ge=-1.0, le=1.0)

# ---ドローン制御ロジックのクラス---
class DroneController:
    def __init__(self, hako_instance: hakosim.MultirotorClient):
        self.hako = hako_instance
        self.status = DroneStatus(armed=False, flying=False)
        self.control_input = JoystickInput(dx=0.0, dy=0.0, dz=0.0, yaw=0.0)
        self._is_running = False
        self._sync_task = None
        self.pdu_game_controller = GameControllerOperation()
        if hasattr(self.pdu_game_controller, 'axis'):
            self.pdu_game_controller.axis = [0.0] * 8
        else:
             print("致命的エラー: GameControllerOperationに'axis'属性が見つかりません。PDUライブラリを確認してください。")

    def start_sync_loop(self):
        if self._is_running: 
            return
        self._is_running = True
        self._sync_task = asyncio.create_task(self._synchronize())
        print("情報: ドローン制御ループを開始しました。")

    def stop_sync_loop(self):
        self._is_running = False
        if self._sync_task:
            self._sync_task.cancel()
        print("情報: ドローン制御ループを停止しました。")
        
    async def _synchronize(self):
        TARGET_INTERVAL = 0.02
        while self._is_running:
            loop_start_time = time.time()
            try:
                self.hako.run_nowait()
                if self.hako.pdu_manager is None:
                    await asyncio.sleep(0.1)
                    continue

                drone_obj = self.hako.vehicles.get(self.hako.default_drone_name)
                if drone_obj:
                    self.status.armed = drone_obj.arm
                    pose: hakosim_types.Pose = self.hako.simGetVehiclePose()
                    if pose and hasattr(pose, 'position'):
                        self.status.is_flying = pose.position.z_val > 0.1

                if self.status.armed:
                    pass
                    # self.pdu_game_controller.axis[1] = -self.control_input.dz 
                    # self.pdu_game_controller.axis[0] = self.control_input.yaw
                    # self.pdu_game_controller.axis[4] = -self.control_input.dy
                    # self.pdu_game_controller.axis[3] = self.control_input.dx
                    # self.hako.putGameJoystickData(self.pdu_game_controller)

            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"同期ループでエラーが発生しました: {e}")
                await asyncio.sleep(0.1)

            loop_duration = time.time() - loop_start_time
            wait_time = TARGET_INTERVAL - loop_duration
            if wait_time > 0:
                await asyncio.sleep(wait_time)
            else:
                print(f"警告: 同期ループの実行時間が {loop_duration:.4f}秒で、目標間隔を超えています。")

    def arm(self):
        self.hako.armDisarm(True)
        return {"message": "ドローンのアーム指令を送信しました"}

    def disarm(self):
        self.hako.armDisarm(False)
        return {"message": "ドローンのディスアーム指令を送信しました"}

    def _takeoff_task(self):
        print("実行: バックグラウンドで離陸を開始しました...")
        success = self.hako.takeoff(5)
        if success: 
            print("情報: 離陸が成功しました")
        else: 
            print("エラー: シミュレータで離陸指令が失敗しました。")
            
    def _land_task(self):
        print("実行: バックグラウンドで着陸を開始しました...")
        success = self.hako.land()
        if success: 
            print("情報: 着陸が成功しました")
        else: 
            print("エラー: シミュレータで着陸指令が失敗しました。")

    def takeoff(self, background_tasks: BackgroundTasks):
        if self.status.armed and not self.status.is_flying:
            background_tasks.add_task(self._takeoff_task)
            return {"message": "離陸指令を受け付けました。"}
        raise HTTPException(status_code=400, detail="離陸できません。ドローンはアーム状態で地上にある必要があります。")

    def land(self, background_tasks: BackgroundTasks):
        if self.status.is_flying:
            background_tasks.add_task(self._land_task)
            return {"message": "着陸指令を受け付けました。"}
        raise HTTPException(status_code=400, detail="着陸できません。ドローンは飛行中ではありません。")

    def _quat_to_yaw_rad(self, q) -> float:
        w, x, y, z = q.w_val, q.x_val, q.y_val, q.z_val
        return math.atan2(2.0*(w*z + x*y), 1.0 - 2.0*(y*y + z*z))
        
    def move_to_position(self, new_input: JoystickInput):
        pose: hakosim_types.Pose = self.hako.simGetVehiclePose()
        if not pose or not hasattr(pose, 'position'):
            raise HTTPException(status_code=500, detail="現在の姿勢を取得できません。")

        print(f"情報: 入力 dx={new_input.dx:.2f}, dy={new_input.dy:.2f}, dz={new_input.dz:.2f}, yaw={new_input.yaw:.2f}")

        STEP_X = 3.0
        STEP_Y = 3.0
        STEP_Z = 3.0
        YAW_DEG = 90.0

        dx = float(new_input.dx) * STEP_X
        dy = float(new_input.dy) * STEP_Y
        dz = float(new_input.dz) * STEP_Z

        target_x = pose.position.x_val + dx
        target_y = pose.position.y_val - dy
        target_z = pose.position.z_val - dz
        yaw = float(new_input.yaw) * YAW_DEG
        try:
            self.hako.moveToPosition(target_x, target_y, target_z, 2.0, yaw)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"moveToPositionが失敗しました: {e}")
        return {"message": "moveToPositionを実行しました"}


class CameraHub:
    def __init__(self, hako, vehicle_name: str, cam_id: int = 0, fps: int = 15):
        self.hako = hako
        self.vehicle = vehicle_name or getattr(hako, "default_drone_name", None) or "Drone"
        self.cam_id = cam_id
        self.interval = max(1, int(1000 / max(1, fps))) / 1000.0  # 秒
        self._lock = threading.Lock()
        self._frame_jpeg: bytes | None = None
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self):
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        print(f"[情報] CameraHub: 起動 vehicle='{self.vehicle}', cam_id={self.cam_id}, fps≈{int(1/self.interval)}")

    def stop(self):
        self._stop.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.0)
        print("[情報] CameraHub: 停止")

    def _run(self):
        import time
        while not self._stop.is_set():
            t0 = time.time()
            try:
                # 直接 JPEG を取得（最軽量）
                img = self.hako.simGetImage(self.cam_id, "jpeg", self.vehicle)
                if img:
                    with self._lock:
                        self._frame_jpeg = img
                # たまに PDU が空を返すことがあるので、空なら前回のフレームを維持
            except Exception as e:
                # 連続エラーでも本体を止めない
                print(f"[警告] CameraHub: 取得中に例外: {e}")
            # FPS 調整
            elapsed = time.time() - t0
            delay = self.interval - elapsed
            if delay > 0:
                time.sleep(delay)

    def get_latest_jpeg(self) -> bytes | None:
        with self._lock:
            return self._frame_jpeg

# ---FastAPIアプリケーションのセットアップ---
app = FastAPI(
    title="Hakoniwa Drone Controller API",
    description="Hakoniwaシミュレータ内のドローンを制御するためのRESTful API",
)

@app.get("/ping")
async def ping():
    return {"message": "pong"}

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

router = APIRouter(prefix="/api/control", tags=["Drone Control"])

@router.get("/state", response_model=DroneStatus, response_model_by_alias=True)
async def get_drone_state():
    if drone_controller is None: 
        raise HTTPException(status_code=503, detail="コントローラーの準備ができていません")
    return drone_controller.status

@router.post("/arm")
async def arm_drone(): 
    return drone_controller.arm()

@router.post("/disarm")
async def disarm_drone(): 
    return drone_controller.disarm()

@router.post("/takeoff")
async def takeoff_drone(background_tasks: BackgroundTasks): 
    return drone_controller.takeoff(background_tasks)

@router.post("/land")
async def land_drone(background_tasks: BackgroundTasks): 
    return drone_controller.land(background_tasks)

@router.post("/move")
async def move_position(joystick_input: JoystickInput):
    return drone_controller.move_to_position(joystick_input)

@router.get("/stream.mjpg")
def stream_mjpeg(vehicle: str | None = None, cam_id: int = 0, fps: int = 15):
    """
    MJPEG ストリームを返す（CameraHubの最新フレームを配るだけ）
    """
    if hako is None:
        raise HTTPException(status_code=503, detail="シミュレータに接続されていません")

    # ここで hub を起動（vehicle/cam_id/fps 指定があれば優先）
    global camera_hub
    if camera_hub is None:
        v = vehicle or getattr(hako, "default_drone_name", None) or "Drone"
        camera_hub = CameraHub(hako, v, cam_id=cam_id, fps=fps)
        camera_hub.start()

    boundary = "frame"
    interval = max(1, int(1000 / max(1, fps))) / 1000.0  # 秒

    def frame_generator():
        import time
        print(f"[情報] /stream.mjpg: クライアント接続 (fps={fps})")
        try:
            while True:
                t0 = time.time()
                frame = camera_hub.get_latest_jpeg() if camera_hub else None
                if frame:
                    yield (
                        b"--" + boundary.encode() + b"\r\n"
                        b"Content-Type: image/jpeg\r\n"
                        + f"Content-Length: {len(frame)}\r\n\r\n".encode()
                        + frame
                        + b"\r\n"
                    )
                # 最新が None（起動直後など）は短く待って再試行
                elapsed = time.time() - t0
                delay = interval - elapsed
                if delay > 0:
                    time.sleep(delay)
        except Exception as e:
            print(f"[情報] /stream.mjpg: 切断/例外: {e}")

    return StreamingResponse(
        frame_generator(),
        media_type=f"multipart/x-mixed-replace; boundary={boundary}",
        headers={"Cache-Control": "no-store, no-cache, must-revalidate, max-age=0"}
    )

app.include_router(router)

# ---サーバーのライフサイクルイベント---
@app.on_event("startup")
def startup_event():
    global drone_controller, hako, camera_hub
    pdu_config_path = os.getenv("HAKO_PDU_CONFIG_PATH")
    if pdu_config_path is None:
        print("エラー: 環境変数HAKO_PDU_CONFIG_PATHが設定されていません。")
        sys.exit(1)

    print(f"情報: PDU設定ファイルを使用します: {pdu_config_path}")
    hako = hakosim.MultirotorClient(pdu_config_path)
    if not hako.confirmConnection():
        print("エラー: Hakoniwaへの接続に失敗しました。")
        sys.exit(1)

    hako.enableApiControl(True)
    drone_controller = DroneController(hako)
    drone_controller.start_sync_loop()
    camera_hub = CameraHub(hako, getattr(hako, "default_drone_name", None) or "Drone", cam_id=0, fps=12)
    camera_hub.start()
    print("情報: FastAPIサーバーが正常に起動しました。")

@app.on_event("shutdown")
def shutdown_event():
    global camera_hub
    if drone_controller: 
        drone_controller.stop_sync_loop()
    if camera_hub:
        camera_hub.stop()
    print("情報: FastAPIサーバーをシャットダウンしました。")

if __name__ == "__main__":
    print("エラー: このスクリプトは直接実行できません。uvicornコマンドを使用してください。")
    print("例: uvicorn drone_api.rc.server:app --reload")
    sys.exit(1)