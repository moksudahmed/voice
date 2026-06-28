from obsws_python import ReqClient
import asyncio

# ==========================================================
# OBS CONFIGURATION
# ==========================================================

OBS_HOST = "127.0.0.1"
OBS_PORT = 4455
OBS_PASSWORD = "Wl1CueV8045rDXyV"

OBS_SCENES = {
    "WELCOME",
    "LIVE",
    "REPLAY",
    "CROWD",
    "DRONE",
    "SCOREBOARD",
    "PLAYERSXI",
    "MATCH_STATUS",
}

# ==========================================================
# GLOBALS
# ==========================================================

obs = None
last_scene = None
current_scene_task = None

# ==========================================================
# SCENE DEFINITIONS
# ==========================================================

SCENE_SEQUENCES = {

    "OVER_COMPLETE": [
        ("SCOREBOARD", 120),
        ("LIVE", 120),
    ],

    "INNINGS_BREAK": [
        ("DRONE", 20),
        ("LIVE", 0),
    ],

    "LUNCH_BREAK": [
        ("DRONE", 20),
        ("LIVE", 0),
    ],

    "TEA_BREAK": [
        ("DRONE", 20),
        ("LIVE", 0),
    ],

    "RAIN_BREAK": [
        ("DRONE", 20),
        ("LIVE", 0),
    ],

    "WICKET": [
        ("REPLAY", 12),
        ("SCOREBOARD", 15),
        ("LIVE", 0),
    ],

    "FOUR": [
        ("REPLAY", 8),
        ("LIVE", 0),
    ],

    "SIX": [
        ("REPLAY", 8),
        ("LIVE", 0),
    ],
}

# ==========================================================
# OBS CONNECTION
# ==========================================================

def init_obs():
    global obs

    try:
        obs = ReqClient(
            host=OBS_HOST,
            port=OBS_PORT,
            password=OBS_PASSWORD,
        )

        print("✅ OBS Connected")
        return True

    except Exception as e:
        obs = None
        print(e)
        return False


def reconnect_obs():

    global obs

    if obs is None:
        print("🔄 Reconnecting OBS...")
        init_obs()


# ==========================================================
# SCENE SWITCH
# ==========================================================

def switch_scene(scene):

    global obs
    global last_scene

    reconnect_obs()

    if obs is None:
        return False

    if scene not in OBS_SCENES:
        print(f"Unknown scene : {scene}")
        return False

    if scene == last_scene:
        return True

    try:

        obs.set_current_program_scene(scene)

        last_scene = scene

        print(f"🎬 {scene}")

        return True

    except Exception as e:

        print(e)

        obs = None

        return False


# ==========================================================
# PLAY SEQUENCE
# ==========================================================

async def play_scene_sequence(sequence):

    try:

        for scene, duration in sequence:

            if not switch_scene(scene):
                return

            if duration > 0:
                await asyncio.sleep(duration)

    except asyncio.CancelledError:

        print("🛑 Scene sequence cancelled")

        raise


# ==========================================================
# PUBLIC API
# ==========================================================

async def update_obs_scene(event_key):

    global current_scene_task

    sequence = SCENE_SEQUENCES.get(event_key)

    if sequence is None:

        print(f"No scene configured for {event_key}")

        return

    print(f"🎯 EVENT : {event_key}")

    # Cancel previous sequence

    if current_scene_task and not current_scene_task.done():

        current_scene_task.cancel()

        try:
            await current_scene_task
        except asyncio.CancelledError:
            pass

    # Start new sequence immediately

    current_scene_task = asyncio.create_task(
        play_scene_sequence(sequence)
    )