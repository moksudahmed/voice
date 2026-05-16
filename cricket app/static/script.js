/* =========================================================
PARTICLES
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
    if (el) {
        el.innerText = value ?? "-";
    }
}

function setImage(selector, src, fallback = "/static/player.png") {
    const el = document.querySelector(selector);
    if (el) {
        el.src = src || fallback;
    }
}

function playSound(id) {
    const audio = document.getElementById(id);
    if (!audio) return;
    audio.currentTime = 0;
    audio.play().catch(() => {});
}

/* =========================================================
EVENT ENGINE
========================================================= */

let isEventRunning = false;

function hideScoreboard() {
    const board = document.querySelector(".broadcast");
    if (board) {
        board.classList.add("hide-ui");
    }
}

function showScoreboard() {
    const board = document.querySelector(".broadcast");
    if (board) {
        board.classList.remove("hide-ui");
    }
}

function clearEvent() {
    const screen = document.querySelector(".event-screen");
    if (!screen) return;
    
    // Clear inner HTML and remove active class
    screen.innerHTML = "";
    screen.classList.remove("active");
    
    // Remove any remaining flash elements
    const existingFlashes = document.querySelectorAll('.four-flash, .six-flash, .wicket-flash');
    existingFlashes.forEach(flash => flash.remove());
    
    // Remove shake effect if present
    document.body.classList.remove("shake");
    
    showScoreboard();
    isEventRunning = false;
}

function runEvent(type) {
    if (isEventRunning) return;
    isEventRunning = true;

    const screen = document.querySelector(".event-screen");
    if (!screen) return;
    
    // Clear previous content
    screen.innerHTML = "";
    screen.classList.add("active");

    let className = "";
    let sound = "";
    let flashClass = "";

    // Handle different event types
    switch(type) {
        case "FOUR":
            className = "four";
            sound = "crowdCheer";
            flashClass = "four-flash";
            break;
        
        case "SIX":
            className = "six";
            sound = "crowdCheer";
            flashClass = "six-flash";
            break;
        
        case "WICKET":
            className = "wicket";
            sound = "crowdShock";
            flashClass = "wicket-flash";
            document.body.classList.add("shake");
            break;
        
        default:
            isEventRunning = false;
            return;
    }

    // Create and add flash effect
    const flash = document.createElement("div");
    flash.className = flashClass;
    document.body.appendChild(flash);
    
    // Remove flash after animation
    setTimeout(() => {
        if (flash && flash.remove) {
            flash.remove();
        }
    }, 700);
    
    // Remove shake effect for wicket after animation
    if (type === "WICKET") {
        setTimeout(() => {
            document.body.classList.remove("shake");
        }, 700);
    }

    // Create event popup
    const eventPopup = document.createElement("div");
    eventPopup.className = `event-popup ${className}`;
    eventPopup.innerText = type;
    screen.appendChild(eventPopup);

    // Hide scoreboard with animation
    requestAnimationFrame(() => {
        requestAnimationFrame(() => {
            hideScoreboard();
        });
    });

    // Play sound
    playSound(sound);

    // Clear event after duration
    setTimeout(() => {
        clearEvent();
    }, 2500);
}

function showEvent(type) {
    if (!type) return;
    runEvent(type);
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
            let textColor = "#fff";
            
            if (ball == 4) {
                bg = "#00ff88";
                textColor = "#000";
            } else if (ball == 6) {
                bg = "#ffd84d";
                textColor = "#000";
            } else if (ball === "W") {
                bg = "#ff1744";
                textColor = "#fff";
            }
            
            ballsHTML += `
                <div class="ball" style="background: ${bg}; color: ${textColor}">
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
    
    // Check for WICKET first (priority)
    if (text.includes("WICKET") || text.includes("BOWLED") || text.includes("OUT")) {
        return "WICKET";
    }
    
    // Check for SIX
    if (text.includes("SIX")) {
        return "SIX";
    }
    
    // Check for FOUR
    if (text.includes("FOUR")) {
        return "FOUR";
    }
    
    return null;
}

/* =========================================================
WEBSOCKET MESSAGE
========================================================= */

ws.onmessage = (msg) => {
    try {
        const d = JSON.parse(msg.data);
        const flags = d.flags || {};
        const livePlayers = d.live_players || {};
        const batsmen = livePlayers.batsmen || [];
        const bowler = livePlayers.bowler || null;
		console.log(d);
        /* TOP BAR */
        setText(".teams", `${flags.team_a_name || "TEAM A"} vs ${flags.team_b_name || "TEAM B"}`);
        setText(".match-info", flags.match_info || "LIVE MATCH");
        setText(".overs", `${d.overs || "0.0"} Overs`);
        setText(".score", d.score || "0/0");
        setText("#crr", d.crr || "0.00");
        setText("#targetScore", d.target || "0/0");
        setText("#partnership", d.partnership || "0(0)");

        /* TEAM FLAGS */
        setText("#teamA", flags.team_a_name || "TEAM A");
        setText("#teamB", flags.team_b_name || "TEAM B");
        setImage("#teamAFlag", flags.team_a_flag);
        setImage("#teamBFlag", flags.team_b_flag);

        /* COMMENTARY */
        setText("#commentary", d.commentary || "LIVE MATCH");

        /* PLAYERS - STRIKER */
        if (batsmen[0]) {
            setText("#strikerName", batsmen[0].name);
            setText("#strikerScore", `${batsmen[0].runs} (${batsmen[0].balls})`);
            setImage("#strikerImg", batsmen[0].image);
        }

        /* PLAYERS - NON-STRIKER */
        if (batsmen[1]) {
            setText("#nonStrikerName", batsmen[1].name);
            setText("#nonStrikerScore", `${batsmen[1].runs} (${batsmen[1].balls})`);
            setImage("#nonStrikerImg", batsmen[1].image);
        }

        /* PLAYERS - BOWLER */
        if (bowler) {
            setText("#bowlerName", bowler.name);
            setText("#bowlerScore", bowler.figures);
            setImage("#bowlerImg", bowler.image);
        }

        /* TIMELINE */
        renderTimeline(d.overs_timeline || []);

        /* EVENT DETECTION & TRIGGER */
        const eventType = d.event || detectEvent(d.result_boxes || []);
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

ws.onopen = () => {
    console.log("WEBSOCKET CONNECTED");
};

ws.onclose = () => {
    console.log("WEBSOCKET DISCONNECTED");
};

ws.onerror = (e) => {
    console.log("SOCKET ERROR:", e);
};