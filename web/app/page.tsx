"use client";

import { useEffect, useState, useRef } from "react";
import { ping, getState, takeoff, land, move, arm, disarm} from "../libs/api";
import Joystick from "../components/Joystick";

export default function Page() {
  const [pong, setPong] = useState<any>(null);
  const [state, setState] = useState<any>(null);
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
      const lx = leftVec.current.x * gain;
      const ly = leftVec.current.y * gain;
      const rx = rightVec.current.x * gain;
      const ry = rightVec.current.y * gain;

      if (Math.hypot(lx, ly, rx, ry) < 0.05) return; //

      // 
      const dx = rx * 0.20;
      const dy = ry * 0.20;
      const dz = ly * 0.15;
      const yaw = lx * 0.25;

      await move(dx, dy, dz, yaw);
      await refreshState();
    }, 100);
    return ()=> clearInterval(id);
  }, [gain]);

  return (
    <main style={{ padding: 24, display: "grid", gap: 16}}>
      <h1>Hakoniwa Drone Controller</h1>

      {/*dummy camera*/}
      <div style={{
        margin: "24px auto", width: 640, height: 320, background: "#111",
        border: "4px solid #2b77ff", borderRadius: 8, display: "grid", placeItems: "center"
      }}>
        <span style={{ color: "#bbb" }}>Camera (placeholder)</span>
      </div>

      {/* central button */}
      <div style= {{ display: "flex", gap: 16, justifyContent: "center", marginBottom: 12}}>
        <button onClick={async()=>{ await arm(); await refreshState(); }} disabled={state?.armed}>ARM</button>
        <button onClick={async()=>{ await takeoff(); await refreshState(); }} disabled={!state?.armed || state?.flying}>Takeoff</button>
        <button onClick={async()=>{ await land(); await refreshState(); }} disabled={!state?.flying}>Land</button>
        <button onClick={async()=>{ await disarm(); await refreshState(); }} disabled={!state?.armed}>Disarm</button>
      </div>

      {/* Joystick */}
      <div style={{
        display: "grid", gridTemplateColumns: "1fr 1fr", alignItems: "center",
        maxWidth: 900, margin: "0 auto", gap: 500
      }}>
        <div style={{ display: "grid", placeItems: "center"}}>
          <Joystick
            onVector={(x, y) => { leftVec.current = {x, y}; }}
            onEnd={() => { leftVec.current = { x: 0, y: 0 }; }}
            />
          <div style={{ marginTop: 8, color: "#666" }}>Left: Z / Yaw</div>
        </div>

        <div style={{ display: "grid", placeItems: "center" }}>
          <Joystick
            onVector={(x, y) => { rightVec.current = { x, y }; }}
            onEnd={() => { rightVec.current = { x: 0, y: 0}; }}
          />
          <div style={{ marginTop: 8, color: "#666"}}>Right: X / Y</div>
        </div>
      </div>

      
    </main>
  )
}

