from services.obs_stream_service.services.schedule_service import \
    ScheduleService


def update_scene_audio_path_in_schedule(scene_name: str, audio_path: str):
    """
    Updates the 'audio_path' for a specific scene within '_available_scenes'
    in the schedule.json file. This function does not change the 'current_scene'.

    Args:
        scene_name (str): The key of the scene to update.
        audio_path (str): The new audio file path to set.

    Returns:
        bool: True if the update was successful, False otherwise.
    """
    schedule_service = ScheduleService()
    schedule_data = schedule_service.load()

    if not schedule_data:
        print("Error: Could not load schedule data.")
        return False

    if "_available_scenes" not in schedule_data or scene_name not in schedule_data.get(
        "_available_scenes", {}
    ):
        print(f"Error: Scene '{scene_name}' not found in '_available_scenes'.")
        return False

    scene = schedule_data["_available_scenes"][scene_name]
    normalized_path = audio_path.replace("\\", "/")
    scene["audio_path"] = normalized_path
    scene["has_audio"] = True

    schedule_service.save(schedule_data)
    print(f"Successfully updated audio for scene '{scene_name}'.")
    return True
