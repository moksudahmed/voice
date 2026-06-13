// =========================================================
// WEB AUDIO API - AUTOMATIC PLAYBACK (NO BUTTON REQUIRED)
// =========================================================

let audioContext = null;
let audioUnlocked = false;
let pendingSounds = [];
let unlockAttempts = 0;

// Play cheer sound
function playCheerSound() {
    if (!audioContext || !audioUnlocked) return false;
    
    try {
        const now = audioContext.currentTime;
        
        // Main cheer chord (C, E, G)
        const frequencies = [523.25, 659.25, 783.99];
        frequencies.forEach(freq => {
            const osc = audioContext.createOscillator();
            const gain = audioContext.createGain();
            osc.connect(gain);
            gain.connect(audioContext.destination);
            osc.frequency.value = freq;
            gain.gain.value = 0.25;
            osc.start();
            gain.gain.exponentialRampToValueAtTime(0.00001, now + 1.2);
            osc.stop(now + 1.2);
        });
        
        // Crowd noise effect
        const bufferSize = 4096;
        const noiseNode = audioContext.createScriptProcessor(bufferSize, 1, 1);
        noiseNode.onaudioprocess = function(e) {
            const output = e.outputBuffer.getChannelData(0);
            for (let i = 0; i < bufferSize; i++) {
                output[i] = (Math.random() * 2 - 1) * 0.08;
            }
        };
        const noiseGain = audioContext.createGain();
        noiseNode.connect(noiseGain);
        noiseGain.connect(audioContext.destination);
        noiseGain.gain.setValueAtTime(0.15, now);
        noiseGain.gain.exponentialRampToValueAtTime(0.00001, now + 0.8);
        
        setTimeout(() => {
            if (noiseNode) noiseNode.disconnect();
        }, 800);
        
        console.log("🔊 Playing CHEER sound");
        return true;
    } catch(e) {
        console.log("Cheer sound error:", e);
        return false;
    }
}
// =========================================================
// PLAY SIX SOUND - TRIUMPHANT & FESTIVE
// =========================================================
function playSixSound() {
    if (!audioContext || !audioUnlocked) return false;
    
    try {
        const now = audioContext.currentTime;
        
        // 1. TRIUMPHANT FANFARE - Ascending melody
        const fanfareNotes = [
            { freq: 523.25, time: 0.00, duration: 0.4 },  // C5
            { freq: 659.25, time: 0.15, duration: 0.4 },  // E5
            { freq: 783.99, time: 0.30, duration: 0.5 },  // G5
            { freq: 1046.50, time: 0.50, duration: 0.6 }, // C6 (High)
            { freq: 1318.52, time: 0.70, duration: 0.7 }, // E6 (Higher)
            { freq: 1567.98, time: 0.95, duration: 1.0 }   // G6 (Highest)
        ];
        
        fanfareNotes.forEach(note => {
            const osc = audioContext.createOscillator();
            const gain = audioContext.createGain();
            osc.connect(gain);
            gain.connect(audioContext.destination);
            osc.frequency.value = note.freq;
            osc.type = 'sine';
            
            // Volume envelope
            gain.gain.setValueAtTime(0, now + note.time);
            gain.gain.linearRampToValueAtTime(0.35, now + note.time + 0.05);
            gain.gain.exponentialRampToValueAtTime(0.00001, now + note.time + note.duration);
            
            osc.start(now + note.time);
            osc.stop(now + note.time + note.duration);
        });
        
        // 2. HAPPY CHEER CHORD - Major chord celebration
        const cheerFreqs = [523.25, 659.25, 783.99, 1046.50];
        cheerFreqs.forEach(freq => {
            const osc = audioContext.createOscillator();
            const gain = audioContext.createGain();
            osc.connect(gain);
            gain.connect(audioContext.destination);
            osc.frequency.value = freq;
            osc.type = 'triangle';
            gain.gain.setValueAtTime(0, now + 0.8);
            gain.gain.linearRampToValueAtTime(0.3, now + 1.0);
            gain.gain.exponentialRampToValueAtTime(0.00001, now + 2.0);
            osc.start(now + 0.8);
            osc.stop(now + 2.0);
        });
        
        // 3. EXCITED CROWD - Rythmic clapping/cheering
        const crowdGain = audioContext.createGain();
        crowdGain.connect(audioContext.destination);
        crowdGain.gain.setValueAtTime(0, now);
        crowdGain.gain.linearRampToValueAtTime(0.25, now + 0.3);
        crowdGain.gain.exponentialRampToValueAtTime(0.00001, now + 2.5);
        
        // Create rhythmic clapping pattern
        const clapTimes = [0.1, 0.3, 0.5, 0.7, 0.9, 1.1, 1.3, 1.5, 1.7, 1.9, 2.1];
        clapTimes.forEach(clapTime => {
            const noiseBuffer = () => {
                const bufferSize = 2048;
                const buffer = audioContext.createBuffer(1, bufferSize, audioContext.sampleRate);
                const data = buffer.getChannelData(0);
                for (let i = 0; i < bufferSize; i++) {
                    data[i] = (Math.random() * 2 - 1) * 0.5;
                }
                return buffer;
            };
            
            const noise = audioContext.createBufferSource();
            noise.buffer = noiseBuffer();
            const noiseGain = audioContext.createGain();
            noise.connect(noiseGain);
            noiseGain.connect(crowdGain);
            noiseGain.gain.setValueAtTime(0.3, now + clapTime);
            noiseGain.gain.exponentialRampToValueAtTime(0.00001, now + clapTime + 0.15);
            noise.start(now + clapTime);
        });
        
        // 4. TRIUMPHANT DRUM ROLL
        const drumGain = audioContext.createGain();
        drumGain.connect(audioContext.destination);
        drumGain.gain.setValueAtTime(0.2, now);
        drumGain.gain.exponentialRampToValueAtTime(0.00001, now + 1.5);
        
        for (let i = 0; i < 12; i++) {
            const drumTime = now + (i * 0.08);
            const osc = audioContext.createOscillator();
            const gain = audioContext.createGain();
            osc.connect(gain);
            gain.connect(drumGain);
            osc.frequency.value = 120 + (i * 15);
            osc.type = 'sine';
            gain.gain.setValueAtTime(0.15, drumTime);
            gain.gain.exponentialRampToValueAtTime(0.00001, drumTime + 0.1);
            osc.start(drumTime);
            osc.stop(drumTime + 0.1);
        }
        
        console.log("🔊 Playing SIX sound - TRIUMPHANT!");
        return true;
    } catch(e) {
        console.log("Six sound error:", e);
        return false;
    }
}
// Play shock sound
function playShockSound() {
    if (!audioContext || !audioUnlocked) return false;
    
    try {
        const now = audioContext.currentTime;
        
        // Dramatic descending sound
        const osc = audioContext.createOscillator();
        const gain = audioContext.createGain();
        osc.connect(gain);
        gain.connect(audioContext.destination);
        
        osc.frequency.setValueAtTime(440, now);
        osc.frequency.exponentialRampToValueAtTime(110, now + 0.4);
        gain.gain.setValueAtTime(0.35, now);
        gain.gain.exponentialRampToValueAtTime(0.00001, now + 0.6);
        osc.start();
        osc.stop(now + 0.6);
        
        // Thud effect
        const thudOsc = audioContext.createOscillator();
        const thudGain = audioContext.createGain();
        thudOsc.connect(thudGain);
        thudGain.connect(audioContext.destination);
        thudOsc.frequency.value = 80;
        thudGain.gain.setValueAtTime(0.25, now + 0.1);
        thudGain.gain.exponentialRampToValueAtTime(0.00001, now + 0.4);
        thudOsc.start(now + 0.1);
        thudOsc.stop(now + 0.4);
        
        console.log("🔊 Playing SHOCK sound");
        return true;
    } catch(e) {
        console.log("Shock sound error:", e);
        return false;
    }
}

// Main play sound function
function playSound(type) {
    if (!audioContext) {
        console.log("🔇 Audio context not initialized");
        return;
    }
    
    if (!audioUnlocked) {
        console.log(`🔇 Audio locked, queueing: ${type}`);
        pendingSounds.push(type);
        // Try to unlock again
        if (unlockAttempts < 5) {
            setTimeout(() => unlockAudio(), 500);
        }
        return;
    }
    
    if (type === "crowdCheer") {
        playCheerSound();
    } else if (type === "crowdSixCheer") {
        playSixSound();
    } else if (type === "crowdShock") {
        playShockSound();
    }
}

// Initialize and unlock audio automatically
function unlockAudio() {
    if (audioUnlocked) return true;
    
    unlockAttempts++;
    console.log(`🎵 Attempt ${unlockAttempts} to initialize audio...`);
    
    try {
        if (!audioContext) {
            audioContext = new (window.AudioContext || window.webkitAudioContext)();
        }
        
        // Create and play silent buffer to unlock
        const buffer = audioContext.createBuffer(1, 1, 22050);
        const source = audioContext.createBufferSource();
        source.buffer = buffer;
        source.connect(audioContext.destination);
        source.start();
        
        audioContext.resume().then(() => {
            audioUnlocked = true;
            console.log("✅ Audio unlocked successfully!");
            
            // Play any pending sounds
            pendingSounds.forEach(sound => {
                playSound(sound);
            });
            pendingSounds = [];
        }).catch(e => {
            console.log("Audio resume error:", e);
            if (unlockAttempts < 5) {
                setTimeout(() => unlockAudio(), 1000);
            }
        });
        
        return true;
    } catch(e) {
        console.log("Audio init error:", e);
        if (unlockAttempts < 5) {
            setTimeout(() => unlockAudio(), 1000);
        }
        return false;
    }
}

// Auto unlock on page load
document.addEventListener('DOMContentLoaded', () => {
    console.log("🎬 Page loaded, initializing audio...");
    // Slight delay to ensure page is ready
    setTimeout(() => unlockAudio(), 100);
});

// Also try on user interaction as fallback (any click/tap)
document.body.addEventListener('click', function onClick() {
    if (!audioUnlocked) {
        console.log("🖱️ User interaction detected, unlocking audio...");
        unlockAudio();
    }
});

console.log("🎬 Cricket Broadcast Ready - Audio will initialize automatically");

// PARTICLES SYSTEM
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

// RAIN ANIMATION SYSTEM
let rainInterval = null;
let isRaining = false;
let currentRainIntensity = null;
let rainTimeout = null;

function createRainDrop(intensity = "medium") {
    const rainContainer = document.querySelector(".rain-container");
    if (!rainContainer) return;
    
    const drop = document.createElement("div");
    drop.className = "rain-drop";
    drop.style.left = Math.random() * 100 + "%";
    
    const height = 10 + Math.random() * 15;
    const width = 1 + Math.random() * 2;
    drop.style.height = height + "px";
    drop.style.width = width + "px";
    
    let duration;
    switch(intensity) {
        case "light": duration = 1.0 + Math.random() * 0.5; break;
        case "heavy": duration = 0.4 + Math.random() * 0.3; break;
        default: duration = 0.6 + Math.random() * 0.4;
    }
    drop.style.animationDuration = duration + "s";
    drop.style.animationDelay = Math.random() * 0.5 + "s";
    
    rainContainer.appendChild(drop);
    
    setTimeout(() => {
        if (drop && drop.remove) drop.remove();
    }, duration * 1000);
}

function startRain(intensity = "medium", duration = 30000) {
    if (isRaining) return;
    
    console.log(`🌧️ Starting rain animation with intensity: ${intensity}`);
    
    const rainContainer = document.querySelector(".rain-container");
    const rainOverlay = document.querySelector(".rain-overlay");
    if (!rainContainer) return;
    
    isRaining = true;
    currentRainIntensity = intensity;
    rainContainer.classList.add(`rain-${intensity}`);
    
    let overlayOpacity = intensity === "light" ? 0.08 : (intensity === "heavy" ? 0.25 : 0.15);
    rainOverlay.style.background = `linear-gradient(180deg, 
        rgba(100, 150, 200, ${overlayOpacity}) 0%,
        rgba(100, 150, 200, ${overlayOpacity * 0.5}) 50%,
        rgba(100, 150, 200, ${overlayOpacity * 1.5}) 100%)`;
    
    let dropCount = 0;
    const maxDrops = intensity === "light" ? 80 : (intensity === "heavy" ? 250 : 150);
    const dropsPerFrame = intensity === "light" ? 2 : (intensity === "heavy" ? 8 : 5);
    
    rainInterval = setInterval(() => {
        if (!isRaining) return;
        for (let i = 0; i < dropsPerFrame; i++) {
            if (dropCount < maxDrops) {
                createRainDrop(intensity);
                dropCount++;
            }
        }
        if (dropCount >= maxDrops) dropCount = Math.floor(maxDrops * 0.7);
    }, 50);
    
    showRainMessage(intensity);
    
    if (rainTimeout) clearTimeout(rainTimeout);
    rainTimeout = setTimeout(() => stopRain(), duration);
}

function stopRain() {
    if (!isRaining) return;
    
    console.log("☀️ Stopping rain animation");
    
    if (rainInterval) clearInterval(rainInterval);
    if (rainTimeout) clearTimeout(rainTimeout);
    
    isRaining = false;
    
    const rainContainer = document.querySelector(".rain-container");
    if (rainContainer) {
        while (rainContainer.firstChild) rainContainer.removeChild(rainContainer.firstChild);
        rainContainer.classList.remove("rain-light", "rain-medium", "rain-heavy");
    }
    
    hideRainMessage();
}

function showRainMessage(intensity) {
    hideRainMessage();
    const message = document.createElement("div");
    message.className = "rain-message";
    let intensityText = "", description = "";
    switch(intensity) {
        case "light": intensityText = "LIGHT RAIN"; description = "Play continues..."; break;
        case "heavy": intensityText = "HEAVY RAIN"; description = "Players heading off the field"; break;
        default: intensityText = "RAIN INTERRUPTION"; description = "Covers coming on";
    }
    message.innerHTML = `<h2>🌧️ ${intensityText}</h2><p>${description}</p>`;
    document.body.appendChild(message);
    setTimeout(() => {
        if (message) {
            message.classList.add("hide");
            setTimeout(() => message.remove(), 500);
        }
    }, 5000);
}

function hideRainMessage() {
    const msg = document.querySelector(".rain-message");
    if (msg) { 
        msg.classList.add("hide"); 
        setTimeout(() => msg.remove(), 500); 
    }
}

// RAIN WORD DETECTION
function detectAndStartRain(text) {
    if (!text || typeof text !== 'string') return false;
    
    const rainKeywords = [
        'rain', 'raining', 'rainfall', 'rainy', 'downpour',
        'shower', 'showering', 'wet weather', 'rain delay',
        'drizzle', 'storm', 'thunderstorm', 'match stopped due to rain'
    ];
    
    const lowerText = text.toLowerCase();
    const hasRain = rainKeywords.some(keyword => lowerText.includes(keyword));
    
    if (hasRain) {
        console.log(`🌧️ RAIN DETECTED: "${text}"`);
        let intensity = "medium";
        if (lowerText.includes('heavy') || lowerText.includes('downpour')) intensity = "heavy";
        else if (lowerText.includes('light') || lowerText.includes('drizzle')) intensity = "light";
        startRain(intensity, 30000);
        return true;
    }
    
    const stopKeywords = ['rain stopped', 'rain has stopped', 'cleared up'];
    const hasStop = stopKeywords.some(keyword => lowerText.includes(keyword));
    if (hasStop && isRaining) {
        console.log(`☀️ RAIN STOPPING: "${text}"`);
        stopRain();
        return true;
    }
    
    return false;
}

// WEBSOCKET CONNECTION
const ws = new WebSocket("ws://127.0.0.1:8000/ws");
let lastEventTime = 0;
let lastRainDetectionTime = 0;

// HELPER FUNCTIONS
function setText(selector, value) {
    const el = document.querySelector(selector);
    if (el) el.innerText = value ?? "-";
}

function setImage(selector, src, fallback = "/static/player.png") {
    const el = document.querySelector(selector);
    if (el) el.src = src || fallback;
}

function updateStrikerStats(player) {
    if (player) {
        setText("#strikerSr", player.strike_rate || player.sr || "0");
        setText("#strikerFours", player.fours || "0");
        setText("#strikerSixes", player.sixes || "0");
    }
}

function updateNonStrikerStats(player) {
    if (player) {
        setText("#nonStrikerSr", player.strike_rate || player.sr || "0");
        setText("#nonStrikerFours", player.fours || "0");
        setText("#nonStrikerSixes", player.sixes || "0");
    }
}

function updateBowlerStats(bowler) {
    if (bowler) {
        setText("#bowlerEco", bowler.economy || bowler.eco || "0.00");
        setText("#bowlerWickets", bowler.wickets || "0");
    }
}

// EVENT ENGINE
let isEventRunning = false;

function hideScoreboard() {
    document.querySelector(".broadcast")?.classList.add("hide-ui");
}

function showScoreboard() {
    document.querySelector(".broadcast")?.classList.remove("hide-ui");
}

function clearEvent() {
    const screen = document.querySelector(".event-screen");
    if (!screen) return;
    screen.innerHTML = "";
    screen.classList.remove("active");
    document.querySelectorAll('.four-flash, .six-flash, .wicket-flash').forEach(flash => flash.remove());
    document.body.classList.remove("shake");
    showScoreboard();
    isEventRunning = false;
}

function runEvent(type) {
    if (isEventRunning) return;
    isEventRunning = true;
    const screen = document.querySelector(".event-screen");
    if (!screen) return;
    
    screen.innerHTML = "";
    screen.classList.add("active");

    let className = "", sound = "", flashClass = "";

    switch(type) {
        case "FOUR": className = "four"; sound = "crowdCheer"; flashClass = "four-flash"; break;
        case "SIX": className = "six"; sound = "crowdSixCheer"; flashClass = "six-flash"; break;
        case "WICKET": className = "wicket"; sound = "crowdShock"; flashClass = "wicket-flash"; document.body.classList.add("shake"); break;
        default: isEventRunning = false; return;
    }

    const flash = document.createElement("div");
    flash.className = flashClass;
    document.body.appendChild(flash);
    setTimeout(() => flash.remove(), 700);
    if (type === "WICKET") setTimeout(() => document.body.classList.remove("shake"), 700);

    const eventPopup = document.createElement("div");
    eventPopup.className = `event-popup ${className}`;
    eventPopup.innerText = type;
    screen.appendChild(eventPopup);

    requestAnimationFrame(() => { requestAnimationFrame(() => hideScoreboard()); });
    playSound(sound);
    setTimeout(() => clearEvent(), 2500);
}

function speak(text = "") {
    if (!text) {
        console.log("No text provided for speech");
        return;
    }
    speechSynthesis.cancel();
    const msg = new SpeechSynthesisUtterance(text);
    msg.lang = "bn-BD";
    msg.rate = 1.05;
    msg.pitch = 1.1;
    msg.volume = 1;
    speechSynthesis.speak(msg);
}
function showEvent(type) { if (type) runEvent(type); }

// TIMELINE RENDERER
function renderTimeline(overs = []) {
    const timeline = document.querySelector(".timeline");
    if (!timeline) return;
    timeline.innerHTML = "";
    overs.slice(-5).forEach(over => {
        let ballsHTML = "";
        (over.balls || []).forEach(ball => {
            let bg = "#374151", textColor = "#fff";
            if (ball == 4) { bg = "#00ff88"; textColor = "#000"; }
            else if (ball == 6) { bg = "#ffd84d"; textColor = "#000"; }
            else if (ball === "W") { bg = "#ff1744"; textColor = "#fff"; }
            ballsHTML += `<div class="ball" style="background: ${bg}; color: ${textColor}">${ball}</div>`;
        });
        timeline.innerHTML += `<div class="timeline-card"><div class="timeline-head"><div class="timeline-over">${over.over || ""}</div><div class="timeline-total">${over.total || ""}</div></div><div class="timeline-balls">${ballsHTML}</div></div>`;
    });
}

// WEBSOCKET MESSAGE HANDLER
ws.onmessage = (msg) => {
    try {
        const d = JSON.parse(msg.data);
        const flags = d.flags || {};
        const livePlayers = d.live_players || {};
        const batsmen = livePlayers.batsmen || [];
        const bowler = livePlayers.bowler || null;
        
       
        console.log("📡 Received:", d);
        
        // Rain detection
        if (d.commentary) {
            const currentTime = Date.now();
            if (currentTime - lastRainDetectionTime > 5000) {
                if (detectAndStartRain(d.commentary)) {
                    lastRainDetectionTime = currentTime;
                }
            }
        }
        
        // Update UI
        setText("#teams", `${flags.team_a_name || ""} vs ${flags.team_b_name || ""}`);
        setText("#matchInfo", flags.match_info || "LIVE MATCH");
        setText("#overs", `${d.overs || "0.0"} Overs`);
        setText("#score", d.score || "0/0");
        setText("#crr", d.crr || "0.00");
        setText("#targetScore", d.target || "0/0");
        setText("#partnership", d.partnership || "0(0)");
        setText("#teamA", flags.team_a_name || "");
        setText("#teamB", flags.team_b_name || "");
        setImage("#teamAFlag", flags.team_a_flag);
        setImage("#teamBFlag", flags.team_b_flag);
        setText("#commentary", d.result_boxes || "LIVE MATCH");
        
        const teamName = d.batting.split(" ")[0];
       /* if (teamName != flags.team_a_name){                    
            fielding=flags.team_a_name                  
            setText("#teamA", flags.team_b_name || "TEAM B");
            setText("#teamB", flags.team_a_name || "TEAM A");
            setImage("#teamAFlag", flags.team_a_flag, "/static/teamA.png");
            setImage("#teamBFlag", flags.team_b_flag, "/static/teamB.png");
            
        }*/

        if (batsmen[0]) {
            setText("#strikerName", batsmen[0].name);
            setText("#strikerScore", `${batsmen[0].runs || 0} (${batsmen[0].balls || 0})`);
            setImage("#strikerImg", batsmen[0].image);
            updateStrikerStats(batsmen[0]);
        }
        
        if (batsmen[1]) {
            setText("#nonStrikerName", batsmen[1].name);
            setText("#nonStrikerScore", `${batsmen[1].runs || 0} (${batsmen[1].balls || 0})`);
            setImage("#nonStrikerImg", batsmen[1].image);
            updateNonStrikerStats(batsmen[1]);
        }
        
        if (bowler) {
            setText("#bowlerName", bowler.name);
            setText("#bowlerScore", bowler.figures || `${bowler.runs_conceded || 0}/${bowler.wickets || 0}`);
            setImage("#bowlerImg", bowler.image);
            updateBowlerStats(bowler);
        }

        renderTimeline(d.overs_timeline || []);
        // Event detection
        let eventType = d.event || null;
        
        if (d.result_boxes && !eventType) {
            const boxValue = String(d.result_boxes).toUpperCase();
            
            if (boxValue === "4" || boxValue === "FOUR") {
                eventType = "FOUR";
                console.log("🎯 DETECTED: FOUR");
            } else if (boxValue === "6" || boxValue === "SIX") {
                eventType = "SIX";
                console.log("🎯 DETECTED: SIX");
            } else if (boxValue === "W" || boxValue === "WICKET" || boxValue === "OUT" || boxValue === "BOWLED" || boxValue === "CAUGHT" || boxValue === "RUN OUT" || boxValue ==="STUMPED OUT") {
                eventType = "WICKET";
                console.log("🎯 DETECTED: WICKET");
            }
        }
        
        const eventTime = d.event_time || Date.now();
        
        if (eventType && eventTime !== lastEventTime) {
            lastEventTime = eventTime;
            console.log("🚀 TRIGGERING EVENT:", eventType);
            showEvent(eventType);
        }
        
    } catch (err) {
        console.error("WS ERROR:", err);
    }
};

ws.onopen = () => console.log("✅ WEBSOCKET CONNECTED");
ws.onclose = () => console.log("❌ WEBSOCKET DISCONNECTED");
ws.onerror = (e) => console.log("⚠️ SOCKET ERROR:", e);