"use client";
import { useEffect, useRef, useState } from "react";

type Props = {
    size?: number;
    knobSize?: number;
    onVector?: (vx: number, vy: number) => void;
    onEnd?: () => void;
};

export default function Joystick({
    size = 140,
    knobSize = 64,
    onVector,
    onEnd,
}: Props) {
    const areaRef = useRef<HTMLDivElement | null>(null);
    const [knob, setKnob] = useState({ x: 0, y: 0});

    useEffect(() => {
        const area = areaRef.current!;
        let dragging = false;
        let rect: DOMRect;
        const radius = size / 2;
        const maxR = radius -knobSize /2;

        const toVec =(clientX: number, clientY: number) => {
            const cx = rect.left + rect.width /2;
            const cy = rect.top + rect.height /2;
            let dx = clientX -cx;
            let dy = clientY -cy;
            //
            const r = Math.hypot(dx, dy);
            if (r > maxR) {
                const s = maxR / (r || 1);
                dx *= s; dy *= s;
            }
            setKnob({ x: dx, y: dy});
            //
            onVector?.(dx / maxR, -dy / maxR);
        };

        const onDown = (e: PointerEvent) => {
            dragging = true;
            rect = area.getBoundingClientRect();
            area.setPointerCapture(e.pointerId);
            toVec(e.clientX, e.clientY);
        };
        const onMove = (e: PointerEvent) => {
            if (!dragging) return;
            toVec(e.clientX, e.clientY);
        };
        const onUp = (e: PointerEvent) => {
            dragging = false;
            area.releasePointerCapture?.(e.pointerId);
            setKnob({ x: 0, y: 0});
            onEnd?.();
        }

        area.addEventListener("pointerdown", onDown);
        window.addEventListener("pointermove", onMove);
        window.addEventListener("pointerup", onUp);
        return () => {
            area.removeEventListener("pointerdown", onDown);
            window.removeEventListener("pointermove", onMove);
            window.removeEventListener("pointerup", onUp);
        };
    }, [size, knobSize, onVector, onEnd]);

    return (
        <div
            ref={areaRef}
            style={{
                width: size, height: size, borderRadius: "50%",
                background: "#e6e6e6", position: "relative", boxShadow: "inset 0 0 0 6px #ddd"
            }}
        >
            <div
                style={{
                    width: knobSize, height: knobSize, borderRadius: "50%",
                    background: "#111",
                    position: "absolute",
                    left: "50%", top: "50%",
                    transform: `translate(${knob.x - knobSize/2}px, ${knob.y - knobSize/2}px)`,
                    boxShadow: "0 6px 16px rgba(0,0,0,.25)"
                }}
            />
        </div>
    );
}