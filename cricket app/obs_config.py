from obsws_python import ReqClient

# =========================
# CONFIGURATION
# =========================
OBS_HOST = "127.0.0.1"
OBS_PORT = 4455
OBS_PASSWORD = "Wl1CueV8045rDXyV"

OBS_SCENES = {"WELCOME","LIVE", "REPLAY", "CROWD", "DRONE", "SCOREBOARD"}

# =========================
# GLOBAL STATE
# =========================
obs = None
last_scene = None


# =========================
# INIT OBS CONNECTION
# =========================
def init_obs() -> bool:
    """
    Initialize connection to OBS WebSocket.
    Returns True if connected successfully.
    """
    global obs

    try:
        obs = ReqClient(
            host=OBS_HOST,
            port=OBS_PORT,
            password=OBS_PASSWORD
        )
        print("✅ OBS CONNECTED SUCCESSFULLY")
        return True

    except Exception as e:
        print(f"❌ OBS CONNECTION FAILED: {e}")
        obs = None
        return False


# =========================
# SWITCH SCENE FUNCTION
# =========================
def switch_scene(scene_name: str) -> bool:
    """
    Switch OBS scene safely with validation and duplicate prevention.
    """

    global obs, last_scene

    # Validate OBS connection
    if obs is None:
        print("⚠ OBS is not connected")
        return False

    # Validate scene name
    if scene_name not in OBS_SCENES:
        print(f"⚠ Invalid scene: {scene_name}")
        return False

    # Prevent duplicate switching
    if scene_name == last_scene:
        return True

    try:
        obs.set_current_program_scene(scene_name)
        last_scene = scene_name
        print(f"🎬 SCENE SWITCHED → {scene_name}")
        return True

    except Exception as e:
        print(f"❌ OBS SWITCH ERROR: {e}")
        return False


# =========================
# QUICK TEST RUN
# =========================
"""if __name__ == "__main__":

    if init_obs():
        #switch_scene("LIVE")
        #switch_scene("REPLAY")
         switch_scene("CROWD")
        # switch_scene("DRONE")"""