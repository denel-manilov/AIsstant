import json
import logging
import os
from pathlib import Path

log = logging.getLogger("config")

SAMPLE_RATE = 24000
CHANNELS = 1
CHUNK_DURATION_MS = 60
CHUNK_SAMPLES = int(SAMPLE_RATE * CHUNK_DURATION_MS / 1000)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SETTINGS_FILE = PROJECT_ROOT / "settings.json"

DEFAULT_INSTRUCTIONS = (
    "You are a helpful assistant. "
    "Respond concisely in the same language the user speaks."
)

DEFAULT_AGENT_MODEL = "gpt-4.1-nano"
AVAILABLE_AGENT_MODELS = [
    "gpt-4.1-nano",
    "gpt-4.1-mini",
    "gpt-4.1",
    "gpt-4o-mini",
    "gpt-4o",
]

DEFAULT_EXPANSION_ENABLED = True
DEFAULT_EXPANSION_MODEL = "gpt-4o-mini"
DEFAULT_EXPANSION_PROMPT = (
    "# Detailed answer expansion\n"
    "- The user received a brief answer from an AI assistant.\n"
    "- Provide a detailed, in-depth expansion of the topic covered in the answer.\n"
    "- Include examples, nuances, and practical details.\n"
    "- Use markdown formatting.\n"
    "- Respond in the same language as the answer."
)
DEFAULT_EXPANSION_USER_PROMPT = "Expand on this answer in detail:\n\n{text}"

DEFAULT_VAD_TYPE = "server_vad"
AVAILABLE_VAD_TYPES = ["server_vad", "semantic_vad"]
DEFAULT_VAD_THRESHOLD = 0.5
DEFAULT_SILENCE_DURATION_MS = 400
DEFAULT_VAD_EAGERNESS = "auto"
AVAILABLE_VAD_EAGERNESS = ["auto", "low", "medium", "high"]


def load_agent_model() -> str:
    return _load_settings().get("agent_model", DEFAULT_AGENT_MODEL)


def save_agent_model(model: str) -> None:
    settings = _load_settings()
    settings["agent_model"] = model
    _save_settings(settings)


def load_custom_prompt() -> str:
    return _load_settings().get("custom_prompt", "")


def save_custom_prompt(text: str) -> None:
    settings = _load_settings()
    settings["custom_prompt"] = text
    _save_settings(settings)


def build_agent_instructions() -> str:
    custom = load_custom_prompt()
    if not custom:
        return DEFAULT_INSTRUCTIONS
    return f"{DEFAULT_INSTRUCTIONS}\n\n{custom}"


def _load_settings() -> dict:
    try:
        return json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _save_settings(data: dict) -> None:
    SETTINGS_FILE.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def load_few_shot_examples() -> list[dict]:
    data = _load_settings().get("few_shot_examples", [])
    return [e for e in data if e.get("question") and e.get("answer")]


def save_few_shot_examples(examples: list[dict]) -> None:
    clean = [
        {"question": e["question"], "answer": e["answer"]}
        for e in examples
        if e.get("question") and e.get("answer")
    ]
    settings = _load_settings()
    settings["few_shot_examples"] = clean
    _save_settings(settings)


def load_expansion_settings() -> dict:
    expansion = _load_settings().get("expansion", {})
    return {
        "enabled": expansion.get("enabled", DEFAULT_EXPANSION_ENABLED),
        "model": expansion.get("model", DEFAULT_EXPANSION_MODEL),
        "prompt": expansion.get("prompt", DEFAULT_EXPANSION_PROMPT),
        "user_prompt": expansion.get("user_prompt", DEFAULT_EXPANSION_USER_PROMPT),
    }


def save_expansion_settings(
    *, enabled: bool, model: str, prompt: str, user_prompt: str,
) -> None:
    settings = _load_settings()
    settings["expansion"] = {
        "enabled": enabled,
        "model": model,
        "prompt": prompt,
        "user_prompt": user_prompt,
    }
    _save_settings(settings)


def build_initial_history(examples: list[dict]) -> list[dict]:
    history = []
    for ex in examples:
        history.append({"role": "user", "content": ex["question"]})
        history.append({"role": "assistant", "content": ex["answer"]})
    return history


def load_vad_type() -> str:
    return _load_settings().get("vad_type", DEFAULT_VAD_TYPE)


def save_vad_type(vad_type: str) -> None:
    settings = _load_settings()
    settings["vad_type"] = vad_type
    _save_settings(settings)


def load_vad_threshold() -> float:
    return _load_settings().get("vad_threshold", DEFAULT_VAD_THRESHOLD)


def save_vad_threshold(threshold: float) -> None:
    settings = _load_settings()
    settings["vad_threshold"] = threshold
    _save_settings(settings)


def load_silence_duration_ms() -> int:
    return _load_settings().get("silence_duration_ms", DEFAULT_SILENCE_DURATION_MS)


def save_silence_duration_ms(ms: int) -> None:
    settings = _load_settings()
    settings["silence_duration_ms"] = ms
    _save_settings(settings)


def load_vad_eagerness() -> str:
    return _load_settings().get("vad_eagerness", DEFAULT_VAD_EAGERNESS)


def save_vad_eagerness(eagerness: str) -> None:
    settings = _load_settings()
    settings["vad_eagerness"] = eagerness
    _save_settings(settings)


def load_api_key() -> str:
    return _load_settings().get("api_key", "")


def save_api_key(key: str) -> None:
    settings = _load_settings()
    settings["api_key"] = key
    _save_settings(settings)


def get_api_key() -> str:
    api_key = load_api_key()
    if not api_key:
        raise RuntimeError(
            "API key is not configured. "
            "Set it in Settings."
        )
    os.environ["OPENAI_API_KEY"] = api_key
    return api_key
