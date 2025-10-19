const API = process.env.NEXT_PUBLIC_API_BASE!;

export async function ping() {
    const r = await fetch(`${API}/ping`, { cache: "no-store" });
    return r.json();
}

export async function getState() {
    const r = await fetch(`${API}/api/control/state`, { cache: "no-store" });
    return r.json();
}

export async function arm() {
    await fetch(`${API}/api/control/arm`, { method: "POST" });
}

export async function takeoff() {
    await fetch(`${API}/api/control/takeoff`, { method : "POST" })
}

export async function land() {
    await fetch(`${API}/api/control/land`, { method : "POST" })
}

export async function disarm() {
    await fetch(`${API}/api/control/disarm`, { method: "POST"});
}

export async function move(dx: number, dy: number, dz: number, yaw: number){
    await fetch(`${API}/api/control/move`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },

        body: JSON.stringify({ dx, dy,dz, yaw })
    });
}