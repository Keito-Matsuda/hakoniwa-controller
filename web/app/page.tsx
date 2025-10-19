"use client";

import { useEffect, useState, useRef } from "react";
import { 
  ping, 
  getState, 
  takeoff, 
  land, 
  move, 
  arm, 
  disarm
} from "../libs/api";
import DPad from "../components/DPad";

export default function Page() {
  const [pong, setPong] = useState<any>(null);
  const [state, setState] = useState<any>(null);
  const [camera, setCamera] = useState<string | null>(null);
  const [step, setStep] = useState(0.5);
  const [gain, setGain] = useState(0.6);

  const leftVec = useRef({ x: 0, y: 0});
  const rightVec = useRef({ x: 0, y: 0});

  useEffect(() => {
    ping().then(setPong);
    getState().then(setState);
  }, []);

  async function refreshState() {
    setState(await getState());
  } 

  useEffect(() => {
    const stateIntervalId = setInterval(refreshState, 500);
    return () => clearInterval(stateIntervalId);
  }, []);

  // 
  useEffect(() => {
    const id = setInterval(async () => {
      const lx = leftVec.current.x;
      const ly = leftVec.current.y;
      const rx = rightVec.current.x;
      const ry = rightVec.current.y;
      const dx = Math.abs(ry) > 0.2 ? Math.sign(ry) : 0;
      const dy = Math.abs(rx) > 0.2 ? Math.sign(rx) : 0;
      const dz = Math.abs(ly) > 0.2 ? Math.sign(ly) : 0;
      const yaw = Math.abs(lx) > 0.2 ? Math.sign(lx) : 0;
      if (dx || dy || dz || yaw) {
        await move(dx, dy, dz, yaw);
        await refreshState();
      }
    }, 200);
    return ()=> clearInterval(id);
  }, []);

  return (
    <main style={{ padding: 24, display: "grid", gap: 16}}>
      <h1>Hakoniwa Drone Controller</h1>

      {/*dummy camera*/}
      <div style={{ margin: "24px auto", placeItems: "center" }}>
        <img
          src={`${process.env.NEXT_PUBLIC_API_BASE}/api/control/stream.mjpg?fps=12`}
          style={{ maxWidth: 640, width: "100%", height: "auto", display: "block" }}
          alt="camera"
        />
      </div>

      {/* central button */}
      <div style= {{ display: "flex", gap: 16, justifyContent: "center", marginBottom: 12}}>
        <button onClick={async()=>{ await arm(); await refreshState(); }} disabled={state?.armed}>ARM</button>
        <button onClick={async()=>{ await takeoff(); await refreshState(); }} disabled={!state?.armed || state?.flying}>Takeoff</button>
        <button onClick={async()=>{ await land(); await refreshState(); }} disabled={!state?.flying}>Land</button>
        <button onClick={async()=>{ await disarm(); await refreshState(); }} disabled={!state?.armed}>Disarm</button>
      </div>

      {/* stick */}
      <div style={{
        display: "grid", gridTemplateColumns: "1fr 1fr", alignItems: "center",
        maxWidth: 900, margin: "0 auto", gap: 500
      }}>
        <div style={{ display: "grid", placeItems: "center"}}>
          <DPad
            onVector={(x, y) => { leftVec.current = {x, y}; }}
            onEnd={() => { leftVec.current = { x: 0, y: 0 }; }}
            />
          <div style={{ marginTop: 8, color: "#666" }}>Left: Z(Vertica) / Yaw(Horizontal)</div>
        </div>

        <div style={{ display: "grid", placeItems: "center" }}>
          <DPad
            onVector={(x, y) => { rightVec.current = { x, y }; }}
            onEnd={() => { rightVec.current = { x: 0, y: 0}; }}
          />
          <div style={{ marginTop: 8, color: "#666"}}>Right: X(Horizontal) / Y(Vertica)</div>
        </div>
      </div>

      
    </main>
  )
}

