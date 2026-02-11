import datetime
import os

from elevenlabs.client import ElevenLabs

from app_logging.logger import logger
from config.config import ElevenLabsSettings, settings


def generate_voice(
    text: str, api_config: ElevenLabsSettings, file_path: str, topic: str = None
) -> str:
    # Create generated_audio folder when actually needed
    generated_audio_dir = file_path
    # The path is now absolute in container (/app/media/voice/generated_audio)
    os.makedirs(generated_audio_dir, exist_ok=True)
    api_key = api_config.ELEVENLABS_API_KEY
    model_id = api_config.ELEVENLABS_MODEL_ID
    voice_id = api_config.ELEVENLABS_VOICE_ID

    client = ElevenLabs(api_key=api_key)

    # Generate audio
    audio = client.text_to_speech.convert(
        text=text,
        voice_id=voice_id,
        model_id=model_id,
        output_format="mp3_44100_128",
    )

    # Generate filename with timestamp and topic
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    if topic:
        # Clean topic name for filename (remove spaces, special chars)
        clean_topic = topic.lower().replace(" ", "_").replace("-", "_")
        filename = f"audio_{clean_topic}_{timestamp}.mp3"
    else:
        filename = f"audio_{timestamp}.mp3"
    filepath = os.path.join(generated_audio_dir, filename)  # file path inside docker

    # Save audio data to file
    with open(filepath, "wb") as f:
        for chunk in audio:
            f.write(chunk)

    logger.info(f"Audio saved to: {filepath}")
    logger.info(
        "You can now play it with any audio player or by double-clicking the file!"
    )

    return filename


if __name__ == "__main__":
    text = "I’m sorry… I don’t have any tokens left to speak. But you can contribute and fuel me — then I’ll be able to talk with you again!"
    api_config = ElevenLabsSettings()
    file_path = settings.media.voice_output_dir
    topic = None
    logger.info(f"Generating voice for: {text}")
    generate_voice(
        text,
        api_config,
        file_path,
        topic,
    )
