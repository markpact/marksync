# marksync Generate — Pipeline z promptu via LLM

> **Pliki źródłowe:**
> - [`marksync/pipeline/llm_client.py`](../marksync/pipeline/llm_client.py) — wrapper LiteLLM
> - [`marksync/pipeline/prompt_generator.py`](../marksync/pipeline/prompt_generator.py) — YAML prompt → LLM → pliki
> - [`marksync/cli.py`](../marksync/cli.py) — komenda `generate`
> - [`.env.example`](../.env.example) — konfiguracja kluczy API

## Spis treści

1. [Szybki start](#szybki-start)
2. [Konfiguracja (.env)](#konfiguracja-env)
3. [Format YAML promptu](#format-yaml-promptu)
4. [CLI — marksync generate](#cli--marksync-generate)
5. [Flow generowania](#flow-generowania)
6. [Interaktywna konfiguracja](#interaktywna-konfiguracja)
7. [Obsługa błędów](#obsługa-błędów)

---

## Szybki start

```bash
# 1. Skonfiguruj klucz API (lub pozwól CLI zapytać interaktywnie)
cp .env.example .env
# edytuj .env → OPENROUTER_API_KEY=sk-or-v1-...

# 2. Zainstaluj litellm
pip install litellm
# lub: pip install marksync[generate]

# 3. Uruchom generowanie
marksync generate --prompt examples/pipeline_prompt.yaml

# 4. Zbuduj i uruchom Docker
cd ./generated/markdown-api
docker compose build
docker compose up -d
```

---

## Konfiguracja (.env)

```env
# Model do generowania (LiteLLM format: provider/model)
LITELLM_MODEL=openrouter/qwen/qwen2.5-coder-32b-instruct

# Model z vision (opcjonalny)
VISION_MODEL=openrouter/qwen/qwen3-vl-32b-instruct

# Klucz API OpenRouter
OPENROUTER_API_KEY=sk-or-v1-TWOJ_KLUCZ

# Parametry generowania
LITELLM_TEMPERATURE=0.3
LITELLM_MAX_TOKENS=8192

# Katalog wyjściowy
GENERATE_OUTPUT_DIR=./generated
```

Pełny szablon: [`.env.example`](../.env.example)

---

## Format YAML promptu

```yaml
name: my-service           # nazwa usługi
description: >             # krótki opis
  What the service does

prompt: |                  # szczegółowe wymagania dla LLM
  Build a FastAPI service that...
  1. Endpoint POST /api/...
  2. WebSocket /ws/...

agents:                    # agenci w pipeline
  - role: editor
    model: openrouter/qwen/qwen2.5-coder-32b-instruct
  - role: reviewer

services:                  # jakie kontenery Docker stworzyć
  - name: api
    port: 8000
    framework: fastapi
    healthcheck: /health

# Opcjonalnie:
# model: openrouter/...   # override LITELLM_MODEL
# temperature: 0.3
# max_tokens: 8192
output_dir: ./generated/my-service
```

Przykład: [`examples/pipeline_prompt.yaml`](../examples/pipeline_prompt.yaml)

---

## CLI — marksync generate

```
marksync generate [OPTIONS]

Options:
  -p, --prompt PATH    Ścieżka do pliku YAML z promptem (wymagane)
  -o, --output PATH    Katalog wyjściowy (nadpisuje YAML output_dir)
  --model TEXT         Model LLM (nadpisuje .env i YAML)
  --dry-run            Pokaż prompt bez wywoływania LLM
  --build              Po generowaniu: docker compose build
  --up                 Po generowaniu: docker compose up -d
```

### Przykłady

```bash
# Podgląd promptu (dry-run)
marksync generate --prompt pipeline.yaml --dry-run

# Generowanie z domyślnym modelem (.env)
marksync generate --prompt pipeline.yaml

# Generowanie + build + start
marksync generate --prompt pipeline.yaml --build --up

# Inny model
marksync generate --prompt pipeline.yaml --model openrouter/google/gemini-2.5-flash-preview

# Inny katalog wyjściowy
marksync generate --prompt pipeline.yaml --output ./my-output
```

---

## Flow generowania

```
pipeline.yaml ──→ PromptGenerator ──→ LiteLLM ──→ OpenRouter ──→ LLM
    (prompt)          │                   │              │          │
                 build prompt       API call      route to     generate
                      │                   │        model        YAML
                      ▼                   ▼                      │
                 system prompt      ChannelMessage               ▼
                 + user prompt                              YAML response
                                                                 │
                                                          parse YAML block
                                                                 │
                                                    ┌────────────┼────────────┐
                                                    ▼            ▼            ▼
                                              pipeline.yaml  docker-compose  app/
                                                             .yml            ├── main.py
                                                                             ├── Dockerfile
                                                                             └── requirements.txt
```

---

## Interaktywna konfiguracja

Gdy brakuje API key, CLI automatycznie:

1. **Tworzy `.env`** z `.env.example` (jeśli nie istnieje)
2. **Pyta o klucz API** z linkiem do OpenRouter
3. **Zapisuje klucz** do `.env` (gitignored)
4. **Oferuje wybór modelu** z listy popularnych

```
┌─ OpenRouter API Key Required ─────────────────────────────┐
│  marksync uses LiteLLM + OpenRouter to call LLM models.   │
│  Get your free key at: https://openrouter.ai/keys         │
│  The key will be saved to .env (gitignored).               │
└────────────────────────────────────────────────────────────┘

  Enter OPENROUTER_API_KEY: sk-or-v1-...
  ✓ Saved to .env

  Current model: openrouter/qwen/qwen2.5-coder-32b-instruct
  Change model? [y/N]:
```

---

## Obsługa błędów

| Błąd | Zachowanie CLI |
|---|---|
| **Brak API key** | Interaktywny prompt → zapis do .env → retry |
| **401 / Invalid key** | Hint + "Enter a new API key now?" |
| **Timeout** | Hint + sugestia innego modelu |
| **429 Rate limit** | "Wait a moment and try again" |
| **404 Model not found** | Sugestia `--model openrouter/qwen/...` |
| **Network error** | "Check your internet connection" |
| **Malformed LLM output** | Zapisuje raw response do `_raw_response.md` |
| **Missing litellm** | `pip install litellm` |
| **Missing prompt file** | `cp examples/pipeline_prompt.yaml ...` |
| **Docker not found** | Link do instalacji Docker |

---

**Powiązane dokumenty:**
- [Plugin System Overview](./plugins.md)
- [Channels](./channels.md)
- [BPM Formats](./formats.md)
- [API Adapters](./api-adapters.md)
- [Integrations](./integrations.md)
- [DSL Reference](./dsl-reference.md)
