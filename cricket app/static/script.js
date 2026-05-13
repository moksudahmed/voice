/* =========================================================
PARTICLES GENERATION
========================================================= */

const particlesContainer = document.getElementById("particles");

function createParticles(count = 80) {
    if (!particlesContainer) return;

    for (let i = 0; i < count; i++) {
        const p = document.createElement("div");
        p.className = "particle";

        p.style.left = Math.random() * 100 + "%";
        p.style.animationDuration = (6 + Math.random() * 10) + "s";
        p.style.animationDelay = Math.random() * 5 + "s";

        particlesContainer.appendChild(p);
    }
}

createParticles();

/* =========================================================
WEBSOCKET
========================================================= */

const ws = new WebSocket("ws://127.0.0.1:8000/ws");

let lastEventTime = 0;

/* =========================================================
HELPERS
========================================================= */

function setText(selector, value) {
    const el = document.querySelector(selector);
    if (el) el.innerText = value ?? "-";
}

function setImage(selector, src, fallback = "/static/player.png") {
    const el = document.querySelector(selector);
    if (el) el.src = src || fallback;
}

function playSound(id) {
    const audio = document.getElementById(id);
    if (!audio) return;
    audio.currentTime = 0;
    audio.play().catch(() => {});
}

/* =========================================================
🔥 BONUS WICKET ANIMATION SYSTEM
========================================================= */

function triggerWicketAnimation() {

    const body = document.body;
    const screen = document.querySelector(".event-screen");

    // 1️⃣ Screen shake effect
    body.classList.add("shake");

    // 2️⃣ Red flash overlay
    const flash = document.createElement("div");
    flash.className = "wicket-flash";
    document.body.appendChild(flash);

    // 3️⃣ Big WICKET popup
    if (screen) {
        screen.innerHTML = `
            <div class="event-popup wicket-pop">
                WICKET!
            </div>
        `;
    }

    playSound("crowdShock");

    // cleanup
    setTimeout(() => {
        body.classList.remove("shake");
        flash.remove();
        if (screen) screen.innerHTML = "";
    }, 1500);
}

/* =========================================================
EVENT DISPLAY
========================================================= */

function showEvent(type) {

    if (type === "WICKET") {
        triggerWicketAnimation();
        return;
    }

    const screen = document.querySelector(".event-screen");
    if (!screen) return;

    let color = "#00e5ff";

    if (type === "SIX") color = "#ffd84d";
    if (type === "FOUR") color = "#00ff88";

    screen.innerHTML = `
        <div class="event-popup" style="color:${color}">
            ${type}
        </div>
    `;

    setTimeout(() => {
        screen.innerHTML = "";
    }, 2000);
}

/* =========================================================
TIMELINE
========================================================= */

function renderTimeline(overs = []) {

    const timeline = document.querySelector(".timeline");
    if (!timeline) return;

    timeline.innerHTML = "";

    const lastOvers = overs.slice(-5);

    lastOvers.forEach(over => {

        let ballsHTML = "";

        (over.balls || []).forEach(ball => {

            let bg = "#374151";

            if (ball == 4) bg = "#00c853";
            if (ball == 6) bg = "#ff9800";
            if (ball === "W") bg = "#ff1744";

            ballsHTML += `
                <div class="ball" style="background:${bg}">
                    ${ball}
                </div>
            `;
        });

        timeline.innerHTML += `
            <div class="timeline-card">
                <div class="timeline-head">
                    <div class="timeline-over">${over.over || ""}</div>
                    <div class="timeline-total">${over.total || ""}</div>
                </div>
                <div class="timeline-balls">${ballsHTML}</div>
            </div>
        `;
    });
}

/* =========================================================
EVENT DETECTOR
========================================================= */

function detectEvent(boxes) {

    if (!Array.isArray(boxes)) return null;

    const text = boxes.join(" ").toUpperCase();

    if (text.includes("WICKET") || text.includes("BOWLED")) return "WICKET";
    if (text.includes("SIX")) return "SIX";
    if (text.includes("FOUR")) return "FOUR";

    return null;
}

/* =========================================================
WEBSOCKET HANDLER
========================================================= */

ws.onmessage = (msg) => {

    try {

        const d = JSON.parse(msg.data);

        const flags = d.flags || {};
        const livePlayers = d.live_players || {};
        const batsmen = livePlayers.batsmen || [];
        const bowler = livePlayers.bowler || null;

        /* TOP */
        setText(".teams", `${flags.team_a_name || "TEAM A"} vs ${flags.team_b_name || "TEAM B"}`);
        setText(".match-info", flags.match_info || "LIVE MATCH");
        setText(".overs", `${d.overs || "0.0"} Overs`);
        setText(".score", d.score || "0/0");

        setText("#crr", d.crr || "0.00");
        setText("#partnership", d.partnership || "0(0)");

        /* FLAGS */
        setText("#teamA", flags.team_a_name || "TEAM A");
        setText("#teamB", flags.team_b_name || "TEAM B");

        setImage("#teamAFlag", flags.team_a_flag);
        setImage("#teamBFlag", flags.team_b_flag);

        /* COMMENTARY */
        setText("#commentary", d.commentary || "LIVE MATCH");

        /* PLAYERS */
        if (batsmen[0]) {
            setText("#strikerName", batsmen[0].name);
            setText("#strikerScore", `${batsmen[0].runs} (${batsmen[0].balls})`);
        }

        if (batsmen[1]) {
            setText("#nonStrikerName", batsmen[1].name);
            setText("#nonStrikerScore", `${batsmen[1].runs} (${batsmen[1].balls})`);
        }

        if (bowler) {
            setText("#bowlerName", bowler.name);
            setText("#bowlerScore", bowler.figures);
        }

        renderTimeline(d.overs_timeline || []);

        /* EVENT */
        let eventType = d.event || detectEvent(d.result_boxes || []);
        const eventTime = d.event_time || Date.now();

        if (eventType && eventTime !== lastEventTime) {
            lastEventTime = eventTime;
            showEvent(eventType);
        }

    } catch (err) {
        console.error("WS ERROR:", err);
    }
};

/* =========================================================
WEBSOCKET STATUS
========================================================= */

ws.onopen = () => console.log("WEBSOCKET CONNECTED");
ws.onclose = () => console.log("WEBSOCKET DISCONNECTED");
ws.onerror = (e) => console.log("SOCKET ERROR:", e);