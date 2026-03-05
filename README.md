# AIsstant

A cross-platform desktop overlay that provides real-time AI voice assistance. Captures live audio (microphone or system audio), streams it through an AI agent pipeline (STT → Agent → text), and displays responses in a floating always-on-top translucent window.

The overlay is **stealth** — hidden from the Dock/taskbar, screenshots, and screen recordings.

## Features

- **Real-time voice-to-text AI** — speak and get instant AI responses via OpenAI's Agents SDK
- **Floating overlay** — frameless, translucent, always-on-top window that stays out of your way
- **Stealth mode** — invisible in screenshots, screen recordings, Zoom/Teams sharing, and task switcher
- **System audio capture** — listen to system audio output, not just the microphone
- **Expansion details** — click "?" on any response to get a detailed expansion in a separate window
- **Conversation history** — maintains context across turns within a session
- **Skip & Send controls** — skip a response mid-stream or manually commit audio to trigger processing
- **Configurable** — choose models, set system prompts, add few-shot examples, customize expansion behavior
- **Markdown rendering** — responses render as markdown once complete
- **Latency tracking** — per-turn latency metrics logged for diagnostics

### Controls

| Button | Action |
|--------|--------|
| **Start** | Begin recording and processing audio |
| **Stop** | End the session and reset the pipeline |
| **Send** | Manually commit buffered audio for processing |
| **Skip** | Cancel the current AI response mid-stream |
| **?** | Expand a completed response with more detail |
| **⚙** | Open settings |

### Settings

- **API Key** — your OpenAI API key
- **Agent Model** — `gpt-4.1-nano` (default), `gpt-4.1-mini`, `gpt-4.1`, `gpt-4o-mini`, `gpt-4o`
- **System Prompt** — custom instructions appended to the default prompt
- **Few-Shot Examples** — Q&A pairs injected as initial conversation history
- **Expansion** — enable/disable, choose model, customize prompts

## Architecture

```
Microphone / SystemAudioDump
    → AudioCapture / SystemAudioCapture
    → asyncio.Queue[np.ndarray]  (bounded, drop-on-full)
    → AgentPipeline
    → VoicePipeline (OpenAI Agents SDK: STT → Agent → no-op TTS)
    → text deltas
    → OverlayWindow (PyQt6)
```

The app uses **PyQt6 + qasync** to run Qt and asyncio on a single thread, avoiding cross-thread complexity.

### Key Design Decisions

- **TTS disabled** — a `_NoOpTTS` stub replaces text-to-speech, keeping the app text-only for lower latency
- **Bounded audio queue** — maxsize 200 (~12s of audio) with silent drops to prevent memory growth
- **Fresh pipeline per session** — `AgentPipeline` is created on Start and destroyed on Stop for clean resets
- **Single-thread async** — qasync bridges Qt and asyncio on one thread, so UI callbacks are safe without locks
- **Stealth via platform APIs** — uses native OS APIs to hide the overlay from screen capture

## System Audio

System audio capture uses platform-specific backends. Required binaries are **auto-downloaded** on first launch.

## Third-Party

- [SystemAudioDump](https://github.com/sohzm/systemAudioDump) by sohzm — MIT License. Used for system audio capture.

## License

GPL-3.0
