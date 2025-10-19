"use client";
import React, { useRef } from "react";

type Props = {
  onVector: (x: number, y: number) => void; // -1〜1
  onEnd?: () => void;
  size?: number;        // 全体サイズ(px)
  invertY?: boolean;    // 上を+1にする場合は false(デフォルト)。逆なら true
  disabled?: boolean;
};


export default function DPadCross({
  onVector,
  onEnd,
  size = 200,
  invertY = false,
  disabled = false,
}: Props) {
  const rootRef = useRef<HTMLDivElement>(null);

  const press = (x: number, y: number) => (e: React.PointerEvent) => {
    if (disabled) return;
    e.preventDefault();
    (e.currentTarget as HTMLElement).setPointerCapture?.(e.pointerId);
    const yy = invertY ? -y : y;
    onVector(x, yy);
  };
  const release = (e?: React.PointerEvent) => {
    e?.preventDefault();
    onVector(0, 0);
    onEnd?.();
  };

  // キーボード(矢印)対応
  const onKey = (e: React.KeyboardEvent) => {
    if (disabled) return;
    const k = e.key;
    if (["ArrowUp", "ArrowDown", "ArrowLeft", "ArrowRight"].includes(k)) {
      e.preventDefault();
      const v =
        k === "ArrowUp" ? { x: 0, y: 1 } :
        k === "ArrowDown" ? { x: 0, y: -1 } :
        k === "ArrowLeft" ? { x: -1, y: 0 } :
                              { x: 1, y: 0 };
      onVector(v.x, invertY ? -v.y : v.y);
    }
    if (k === " " || k === "Enter") {
      release();
    }
  };
  const onKeyUp = (e: React.KeyboardEvent) => {
    if (["ArrowUp", "ArrowDown", "ArrowLeft", "ArrowRight"].includes(e.key)) {
      release();
    }
  };

  const crossSize = size * 0.9;
  const armSize = crossSize / 3;
  const borderRadius = armSize * 0.3; // 角丸の半径を調整
  const gap = armSize * 0.15; // ボタン間の隙間

  // 各アーム（ボタン）に共通のスタイル
  const armStyle: React.CSSProperties = {
    background: "linear-gradient(180deg, #2b3346 0%, #111721 100%)",
    border: "1px solid rgba(255,255,255,0.06)",
    boxShadow:
      "inset 0 6px 10px rgba(255,255,255,0.07), inset 0 -8px 12px rgba(0,0,0,0.7), 0 2px 4px rgba(0,0,0,0.45)",
    cursor: "pointer",
    userSelect: "none",
    touchAction: "none",
    display: "grid",
    placeItems: "center",
    color: "#cfd6e4",
    fontSize: Math.max(14, Math.round(armSize * 0.5)),
    textShadow: "0 1px 1px rgba(0,0,0,0.8)",
  };

  return (
    <div
      ref={rootRef}
      tabIndex={0}
      onKeyDown={onKey}
      onKeyUp={onKeyUp}
      onBlur={() => release()}
      style={{
        width: size, height: size, position: "relative",
        filter: disabled ? "grayscale(1) opacity(0.6)" : "none",
        outline: "none",
      }}
    >


      {/* CSS Grid で十字キーをレイアウト */}
      <div
        style={{
          position: "absolute",
          left: "50%", top: "50%",
          transform: "translate(-50%, -50%)",
          width: crossSize,
          height: crossSize,
          display: "grid",
          gridTemplateColumns: "1fr 1fr 1fr",
          gridTemplateRows: "1fr 1fr 1fr",
          gap: gap, // ★ 変更点: ボタン間に隙間を追加
          filter: "drop-shadow(0 4px 6px rgba(0,0,0,0.6))",
        }}
      >
        {/* ★ 変更点: 各ボタンのborderRadiusを外側だけ丸めるように調整 */}
        <button onPointerDown={press(0, 1)} onPointerUp={release} style={{ ...armStyle, gridColumn: "2", gridRow: "1", borderRadius: `${borderRadius}px ${borderRadius}px 0 0` }}>▲</button>
        <button onPointerDown={press(-1, 0)} onPointerUp={release} style={{ ...armStyle, gridColumn: "1", gridRow: "2", borderRadius: `${borderRadius}px 0 0 ${borderRadius}px` }}>◀</button>
        <button onPointerDown={press(1, 0)} onPointerUp={release} style={{ ...armStyle, gridColumn: "3", gridRow: "2", borderRadius: `0 ${borderRadius}px ${borderRadius}px 0` }}>▶</button>
        <button onPointerDown={press(0, -1)} onPointerUp={release} style={{ ...armStyle, gridColumn: "2", gridRow: "3", borderRadius: `0 0 ${borderRadius}px ${borderRadius}px` }}>▼</button>
        
        {/* ★ 変更点: 中央のディスクは不要なため削除 */}
      </div>
    </div>
  );
}