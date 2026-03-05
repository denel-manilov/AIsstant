from aisstant.audio.capture import AudioCapture, AudioDevice, list_input_devices
from aisstant.platform import IS_MACOS

__all__ = [
    "AudioCapture",
    "AudioDevice",
    "list_input_devices",
]

if IS_MACOS:
    from aisstant.audio.system_capture import SystemAudioCapture

    __all__.append("SystemAudioCapture")
