import sys
import os
import asyncio
import time

# ---必要なライブラリをインポート---
from fastapi import FastAPI, APIRouter, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import uvicorn

# ---Hakoniwaシミュレータ連携部分---
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import libs.hakosim as hakosim
import libs.hakosim_types as hakosim_types
from hakoniwa_pdu.pdu_msgs.hako_msgs.pdu_pytype_GameControllerOperation import GameControllerOperation

# ---グローバル変数---
hako: hakosim.MultirotorClient = None
drone_controller = None

# ---Pydanticモデル定義---
class DroneStatus(BaseModel):
    armed: bool
    is_flying: bool = Field(..., alias="flying")
    class Config:
        # Pydantic V2では `validate_by_name = True` が推奨
        validate_by_name = True
        # allow_population_by_field_name は古い書き方ですが、互換性のために残してもOK
        allow_population_by_field_name = True


class JoystickInput(BaseModel):
    dx: float = Field(..., ge=-1.0, le=1.0)
    dy: float = Field(..., ge=-1.0, le=1.0)
    dz: float = Field(..., ge=-1.0, le=1.0)
    yaw: float = Field(..., ge=-1.0, le=1.0)

# ---ドローン制御ロジックのクラス---
class DroneController:
    def __init__(self, hako_instance):
        self.hako = hako_instance
        self.status = DroneStatus(armed=False, flying=False)
        self.control_input = JoystickInput(dx=0.0, dy=0.0, dz=0.0, yaw=0.0)
        self._is_running = False
        self._sync_task = None
        self.pdu_game_controller = GameControllerOperation()
        
        # 正しいプロパティ `axis` を初期化
        if hasattr(self.pdu_game_controller, 'axis'):
            self.pdu_game_controller.axis = [0.0] * 8
        else:
             print("CRITICAL ERROR: 'axis' attribute not found in GameControllerOperation. Check pdu library.")


    def start_sync_loop(self):
        if self._is_running: return
        self._is_running = True
        self._sync_task = asyncio.create_task(self._synchronize())
        print("INFO: Drone control loop started.")

    def stop_sync_loop(self):
        self._is_running = False
        if self._sync_task:
            self._sync_task.cancel()
        print("INFO: Drone control loop stopped.")
        
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
                    # 【最終修正】.axes_data を正しいプロパティ `axis` に修正
                    self.pdu_game_controller.axis[1] = -self.control_input.dz 
                    self.pdu_game_controller.axis[0] = self.control_input.yaw
                    self.pdu_game_controller.axis[4] = -self.control_input.dy
                    self.pdu_game_controller.axis[3] = self.control_input.dx
                    self.hako.putGameJoystickData(self.pdu_game_controller)

            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"ERROR in sync loop: {e}")
                await asyncio.sleep(0.1)

            loop_duration = time.time() - loop_start_time
            wait_time = TARGET_INTERVAL - loop_duration
            if wait_time > 0:
                await asyncio.sleep(wait_time)
            else:
                print(f"WARNING: Sync loop took {loop_duration:.4f}s, longer than the target interval.")

    def arm(self):
        self.hako.armDisarm(True)
        return {"message": "Drone armed command sent"}

    def disarm(self):
        self.hako.armDisarm(False)
        return {"message": "Drone disarmed command sent"}

    def _takeoff_task(self):
        print("ACTION: Takeoff initiated in background...")
        success = self.hako.takeoff(5)
        if success: print("INFO: Takeoff successful")
        else: print("ERROR: Takeoff command failed in simulator.")
            
    def _land_task(self):
        print("ACTION: Landing initiated in background...")
        success = self.hako.land()
        if success: print("INFO: Land successful")
        else: print("ERROR: Land command failed in simulator.")

    def takeoff(self, background_tasks: BackgroundTasks):
        if self.status.armed and not self.status.is_flying:
            background_tasks.add_task(self._takeoff_task)
            return {"message": "Takeoff command received."}
        raise HTTPException(status_code=400, detail="Cannot takeoff. Drone must be armed and on the ground.")

    def land(self, background_tasks: BackgroundTasks):
        if self.status.is_flying:
            background_tasks.add_task(self._land_task)
            return {"message": "Land command received."}
        raise HTTPException(status_code=400, detail="Cannot land. Drone is not flying.")
        
    def update_control(self, new_input: JoystickInput):
        self.control_input = new_input
        return {"message": "Control input updated"}

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
    if drone_controller is None: raise HTTPException(status_code=503, detail="Controller not ready")
    return drone_controller.status

@router.post("/arm")
async def arm_drone(): return drone_controller.arm()

@router.post("/disarm")
async def disarm_drone(): return drone_controller.disarm()

@router.post("/takeoff")
async def takeoff_drone(background_tasks: BackgroundTasks): return drone_controller.takeoff(background_tasks)

@router.post("/land")
async def land_drone(background_tasks: BackgroundTasks): return drone_controller.land(background_tasks)

@router.post("/move")
async def move_drone(joystick_input: JoystickInput): return drone_controller.update_control(joystick_input)

app.include_router(router)

# ---サーバーのライフサイクルイベント---
@app.on_event("startup")
def startup_event():
    global drone_controller, hako
    pdu_config_path = os.getenv("HAKO_PDU_CONFIG_PATH")
    if pdu_config_path is None:
        print("ERROR: Environment variable HAKO_PDU_CONFIG_PATH is not set.")
        sys.exit(1)

    print(f"INFO: Using PDU config from: {pdu_config_path}")
    hako = hakosim.MultirotorClient(pdu_config_path)
    if not hako.confirmConnection():
        print("ERROR: Failed to connect to Hakoniwa.")
        sys.exit(1)

    hako.enableApiControl(True)
    drone_controller = DroneController(hako)
    drone_controller.start_sync_loop()
    print("INFO: FastAPI server has started successfully.")

@app.on_event("shutdown")
def shutdown_event():
    if drone_controller: drone_controller.stop_sync_loop()
    print("INFO: FastAPI server has been shut down.")

if __name__ == "__main__":
    print("ERROR: This script cannot be run directly. Please use uvicorn command.")
    print("Example: uvicorn drone_api.rc.server:app --reload")
    sys.exit(1)