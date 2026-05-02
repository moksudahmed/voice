from obsws_python import ReqClient

OBS_HOST = "127.0.0.1"
OBS_PORT = 4455
OBS_PASSWORD = "jbuDLaKfxUZc6c7m"

obs = ReqClient(
    host=OBS_HOST,
    port=OBS_PORT,
    password=OBS_PASSWORD
)

def switch_scene(scene_name: str):
    try:
        obs.set_current_program_scene(scene_name)
        print(f"✅ SWITCHED SCENE: {scene_name}")
    except Exception as e:
        print(f"❌ OBS SWITCH ERROR: {e}")
        
switch_scene("LIVE")
switch_scene("REPLAY")
switch_scene("CROWD")