import os

def play_action_sound(action_name):
    """
    Belirtilen aksiyona ait .wav dosyasını sounds klasöründe bulur ve çalar.
    Örn: action_name="save" -> sounds/save.wav dosyasını çalar.
    """
    try:
        import winsound
        sound_path = os.path.join("resources/system_sounds", f"{action_name}.wav")
        if os.path.exists(sound_path):
            winsound.PlaySound(sound_path, winsound.SND_FILENAME | winsound.SND_ASYNC)
    except Exception as e:
        pass