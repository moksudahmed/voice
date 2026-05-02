from obsws_python import ReqClient

OBS_SCENES = ["LIVE", "REPLAY", "CROWD", "DRONE"]

obs = None
last_scene = None

def init_obs():
    global obs
    try:
        obs = ReqClient(host="localhost", port=4455, password="jbuDLaKfxUZc6c7m")
        print("OBS CONNECTED")
    except Exception as e:
        print("OBS ERROR:", e)
        obs = None


def switch_scene(scene: str):
    global last_scene, obs

    if not obs or scene not in OBS_SCENES:
        return

    if scene == last_scene:
        return

    try:
        obs.set_current_program_scene(scene)
        last_scene = scene
    except Exception as e:
        print("OBS ERROR:", e)