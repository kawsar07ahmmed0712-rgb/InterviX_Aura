# InterviX Aura

InterviX Aura is a FastAPI, WebSocket, and AutoGen AgentChat mock interview app. It runs a short interview loop with three roles:

- `Interviewer`: asks role-specific interview questions.
- `Candidate`: receives your answers from the web UI or terminal.
- `Evaluator`: gives brief feedback after each answer.

Supported LLM providers:

- Gemini API through the OpenAI-compatible Gemini endpoint.
- Ollama local or cloud OpenAI-compatible models.

## Project Structure

```text
.
+-- app.py                    # FastAPI web app and WebSocket endpoint
+-- agent_test.py             # Terminal interview runner
+-- interview_team.py         # AutoGen agents, team, and message formatting
+-- llm_clients.py            # Gemini and Ollama model client builders
+-- templates/index.html      # Web UI shell
+-- static/app.js             # Browser WebSocket client
+-- static/styles.css         # Web UI styles
+-- requirements.txt          # Python dependencies
+-- environment.yml           # Conda environment definition
+-- .env.example              # Environment variable template
```

## Environment Setup

Recommended environment name: `intervix_aura`

### Option 1: Create from `environment.yml`

```bash
conda env create -f environment.yml
conda activate intervix_aura
```

If the environment already exists and you want a clean rebuild:

```bash
conda env remove -n intervix_aura
conda env create -f environment.yml
conda activate intervix_aura
```

### Option 2: Create manually

```bash
conda create -n intervix_aura python=3.12 -y
conda activate intervix_aura
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

## Configure Environment Variables

Create your local `.env` file from the example:

```bash
copy .env.example .env
```

On macOS or Linux:

```bash
cp .env.example .env
```

Edit `.env` and set your real provider values.

### Gemini

```env
DEFAULT_PROVIDER=gemini
GEMINI_API_KEY=your_gemini_api_key_here
GEMINI_MODEL=gemini-2.5-flash
```

### Ollama

```env
DEFAULT_PROVIDER=ollama
OLLAMA_BASE_URL=http://localhost:11434/v1/
OLLAMA_LLAMA_MODEL=llama3:latest
```

For local Ollama, start the server and pull the model you want to use:

```bash
ollama serve
ollama pull llama3
```

## Run the Web App

```bash
conda activate intervix_aura
python -m uvicorn app:app --reload --host 127.0.0.1 --port 8000
```

Open:

```text
http://127.0.0.1:8000
```

Health check:

```text
http://127.0.0.1:8000/health
```

## Run the Terminal Interview

Gemini:

```bash
python agent_test.py --provider gemini --model gemini-2.5-flash --position "AI Engineer"
```

Ollama:

```bash
python agent_test.py --provider ollama --model llama3:latest --position "AI Engineer"
```

## Test and Validate

Run the unit tests:

```bash
python -m pytest
```

Compile the main Python files:

```bash
python -m compileall app.py interview_team.py llm_clients.py agent_test.py
```

## Troubleshooting

### `GEMINI_API_KEY is missing from .env`

Add a valid Gemini API key to `.env`, or switch the provider to `ollama`.

### Ollama connection errors

Make sure Ollama is running and the configured model exists:

```bash
ollama list
ollama pull llama3
```

If you use Ollama Cloud or another OpenAI-compatible endpoint, set `OLLAMA_BASE_URL` and the model variables in `.env`.

### Package warnings from an old global Python install

Use the clean conda environment above. If warnings remain, update the installed HTTP packages inside the active environment:

```bash
python -m pip install --upgrade requests urllib3 charset-normalizer
```

## License

This project is licensed under the MIT License. See [LICENSE](LICENSE).
