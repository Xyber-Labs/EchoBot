from time import sleep

from services.obs_stream_service.services.obs_service import OBSService

DURATION = 3
SCENES = ["Scene-Talking", "Scene-Working", "Scene-Music"]


def switch_scenes(obs: OBSService):
    while True:
        for scene in SCENES:
            scene_name = scene
            obs.switch_scene_smooth(scene_name)
            sleep(DURATION)
