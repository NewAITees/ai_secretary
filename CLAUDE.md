# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

AI Secretary is a local AI assistant system that integrates:
- **Ollama** for LLM inference (local, privacy-focused)
- **COEIROINK** for Japanese text-to-speech synthesis
- **FastAPI** backend with React/TypeScript frontend
- **PyAudio** for audio playback on WSL2

All processing happens locally - no external API calls for core functionality.

## Development Commands

### Setup and Installation

```bash
# Install Python dependencies (using uv package manager)
uv sync

# Install development dependencies
uv sync --all-extras

# Install frontend dependencies
npm install --prefix frontend
```

### Running the Application

```bash
# Development mode (launches both backend and frontend with hot reload)
uv run python scripts/dev_server.py
# Backend: http://localhost:8000
# Frontend: http://localhost:5173

# Production build
npm run build --prefix frontend
uv run python -m uvicorn src.server.app:app --host 0.0.0.0 --port 8000
```

### Testing

```bash
# Run all tests
uv run pytest tests/ -v

# Run specific test file
uv run pytest tests/test_ai_secretary_voice.py -v

# Run with coverage
uv run pytest tests/ -v --cov=src
```

### Code Quality

```bash
# Format code with black
uv run black src/ tests/ --line-length 100

# Lint with ruff
uv run ruff check src/ tests/

# Type checking with mypy
uv run mypy src/
```

### Ollama Management

```bash
# List available models
ollama list

# Pull a new model
ollama pull llama3.1:8b

# Test Ollama connection
curl http://localhost:11434/api/tags
```

## Architecture

### Core Components

**AISecretary** ([src/ai_secretary/secretary.py](src/ai_secretary/secretary.py))
- Main orchestrator class
- Manages conversation history
- Integrates OllamaClient, COEIROINKClient, and AudioPlayer
- Handles the full pipeline: user input → LLM → voice synthesis → audio playback

**OllamaClient** ([src/ai_secretary/ollama_client.py](src/ai_secretary/ollama_client.py))
- Communicates with Ollama API
- Default response format: JSON (configurable with `format="json"`)
- Two main methods: `chat()` for conversations, `generate()` for single-shot completions
- Supports streaming

**COEIROINKClient** ([src/coeiroink_client.py](src/coeiroink_client.py))
- Full-featured Japanese TTS client
- Speaker/style management with UUID-based selection
- Detailed voice parameter control: speed, volume, pitch, intonation
- Optional prosody control for fine-grained expression
- See extensive documentation in file header

**FastAPI Server** ([src/server/app.py](src/server/app.py))
- REST API endpoint: `POST /api/chat`
- Singleton AISecretary instance via `get_secretary()`
- CORS enabled for local development

**React Frontend** ([frontend/src/](frontend/src/))
- TypeScript/React UI
- API client in [frontend/src/api.ts](frontend/src/api.ts)
- Vite for bundling and dev server

### Data Flow

```
User Input (Frontend/API)
    ↓
AISecretary.chat()
    ↓
OllamaClient → Ollama LLM (localhost:11434)
    ↓
JSON Response (with COEIROINK voice plan)
    ↓
COEIROINKClient → COEIROINK API (localhost:50032)
    ↓
WAV Audio File
    ↓
AudioPlayer (PyAudio) → Audio Output
```

### JSON Response Design

The system uses structured JSON responses by default. Ollama is prompted to return COEIROINK-compatible JSON with these keys:
- `text`: Japanese response text
- `speakerUuid`, `styleId`: Voice selection
- `speedScale`, `volumeScale`, `pitchScale`, `intonationScale`: Voice parameters
- `prePhonemeLength`, `postPhonemeLength`: Silence padding
- `outputSamplingRate`: Audio quality (16000/24000/44100/48000)
- `prosodyDetail`: Fine-grained mora-level prosody control (usually `[]`)

The system prompt in `AISecretary._build_voice_instruction()` dynamically includes available speakers and styles.

## Configuration

Configuration is managed via environment variables and the `Config` class ([src/ai_secretary/config.py](src/ai_secretary/config.py)).

Key environment variables:
- `OLLAMA_HOST`: Ollama API URL (default: `http://localhost:11434`)
- `OLLAMA_MODEL`: Model name (default: `llama3.1:8b`)
- `COEIROINK_API_URL`: COEIROINK API URL (default: `http://localhost:50032`)
- `AUDIO_OUTPUT_DIR`: Where to save synthesized audio (default: `outputs/audio`)
- `LOG_LEVEL`: Logging verbosity (default: `INFO`)
- `SYSTEM_PROMPT`: Custom system prompt (optional)

Create a `.env` file from `.env.example` to customize settings.

## WSL2 Audio Setup

Audio playback on WSL2 requires PulseAudio configuration. See [doc/WSL2_AUDIO_SETUP.md](doc/WSL2_AUDIO_SETUP.md) for detailed setup instructions.

Quick test:
```bash
# Verify audio device
pactl info

# Test playback
uv run python test_play.py
```

## Project Structure Notes

- **doc/**: Architecture docs, changelogs, research notes
- **plan/**: Task planning and management files
- **logs/**: Auto-generated log files (gitignored)
- **outputs/audio/**: Generated WAV files (gitignored)
- **scripts/**: Development utilities (dev server launcher, etc.)
- **samples/**: Sample code and test data generators

## Development Workflow

1. **COEIROINK must be running** before starting the application (required for TTS)
2. **Ollama must be running** with required models pulled
3. Use `scripts/dev_server.py` for development - it manages both frontend and backend
4. Check `doc/design/architecture.md` for detailed design documentation
5. Add new features by extending `AISecretary` and relevant clients
6. All major classes have design doc references in their docstrings

## Testing Strategy

- **Unit tests**: Mock external services (Ollama, COEIROINK, PyAudio)
- **Integration tests**: Require running Ollama/COEIROINK instances
- Tests use dependency injection for easy mocking (see `AISecretary.__init__` parameters)
- Audio playback tests are environment-dependent and should gracefully handle missing PyAudio

## Python Requirements

- **Python 3.13+** (specified in pyproject.toml)
- **uv** as the package manager (not pip/poetry)
- Use `uv add <package>` to add dependencies (auto-updates pyproject.toml and uv.lock)
