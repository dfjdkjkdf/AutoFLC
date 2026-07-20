# 🤖 AutoFLC

Language: **English** | [中文](README.zh-CN.md)

[![CI](https://github.com/dfjdkjkdf/AutoFLC/actions/workflows/ci.yml/badge.svg)](https://github.com/dfjdkjkdf/AutoFLC/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue)

https://github.com/user-attachments/assets/26ba76af-d3f8-46e5-b9cc-9fdef28b29a0

> 🎥 The demo video above only shows the **ZIP upload** flow. The **GitHub link** input described below was added afterwards and isn't shown in the video, but works the same way once a task is submitted.

AutoFLC is a Docker-based tool that automatically converts C source code — uploaded as a ZIP, or pulled directly from a **GitHub repository/branch link** — into PlantUML flowcharts. It integrates a Streamlit frontend, an OpenAI-compatible multi-model LLM backend (OpenAI, OpenRouter, Ollama, ...), and a PlantUML rendering engine.

## 📂 Directory Structure

````text
.
├── Dockerfile              # Build Docker image
├── requirements.txt        # Runtime Python dependencies
├── requirements-dev.txt    # Test/lint dependencies (pytest, ruff) — not installed in the image
├── pyproject.toml          # pytest + ruff configuration
├── app.py                  # Streamlit entrypoint (UI only)
├── config.yaml             # Model config, prompts, and language settings
├── autoflc/                # Core library, split by responsibility
│   ├── config.py           #   config.yaml loading + env-var API key override
│   ├── task_tracker.py     #   task state store + background logger
│   ├── c_parser.py         #   tree-sitter based C function extraction
│   ├── llm_client.py       #   LLM call + PlantUML response post-processing
│   ├── renderer.py         #   PlantUML -> PNG rendering
│   ├── archive.py          #   zip extraction (incl. mojibake filename handling)
│   ├── github_source.py    #   GitHub repo/branch link -> local zip
│   └── worker.py           #   background pipeline orchestration
├── tests/                  # pytest unit tests (no Java/PlantUML/network required)
├── .github/workflows/ci.yml
└── history/                # Stores generated images and ZIP packages; folder name matches the task ID
````

## 🌐 Language Support

AutoFLC supports **Chinese (`zh`)** and **English (`en`)** for both UI labels and flowchart annotations.

To switch the language, edit **one line** in `config.yaml` and restart the container:

````yaml
# config.yaml
language: "en"   # "en" = English flowchart annotations + English UI
                 # "zh" = 中文流程图注释 + 中文界面
````

> **Note**: Changing the language affects the AI-generated flowchart node labels, the web UI text, and the user manual simultaneously.

## 🚀 Deployment and Usage Guide

### 1. Build the Image

````bash
docker build -t flowchart-agent .
````

### 2. Start the Container

Mount the whole project directory so any file — `config.yaml`, `app.py`, or anything under `autoflc/` — can be live-edited without rebuilding the image:

````bash
docker run -d -p 8501:8501 \
  --name flowchart-dev \
  -v YOUR_PATH\AutoFLC:/app \
  -e AUTOFLC_API_KEY=your-real-api-key-here \
  --add-host=host.docker.internal:host-gateway \
  flowchart-agent
````

> 💡 The whole project is mounted as one volume, so you can switch languages, update prompts, or tweak any `autoflc/*.py` module **without rebuilding the image** — just edit the file and restart the container.

> 🔑 **API keys are never stored in `config.yaml`.** Leave `api_key: ""` in `config.yaml` and pass the real key via the `AUTOFLC_API_KEY` environment variable (or `AUTOFLC_API_KEY_<MODEL_NAME>` to target one specific model when several are configured), so it never ends up committed to git.
>
> 📦 `plantuml.jar` lives at `/opt/plantuml/plantuml.jar` inside the image (outside `/app`), pointed to by the `PLANTUML_JAR` env var baked into the image — so mounting the whole project over `/app` never hides it.

### 3. Restart After Config Change

````bash
docker restart flowchart-dev
````

## 🧪 Development

The core logic under `autoflc/` is unit-tested with `pytest` and does not require Java, PlantUML, or network access to run:

````bash
pip install -r requirements.txt -r requirements-dev.txt
ruff check .
pytest -q
````

CI runs the same two commands on every push/PR (see `.github/workflows/ci.yml`).

## 📖 User Guide

1. **Prepare** a C source input, either:
   - Compress your C project folder (e.g., the `usr` directory) into a `.zip` file, **or**
   - Have a public GitHub repository URL ready — either the repo root (`https://github.com/owner/repo`) or a specific branch (`https://github.com/owner/repo/tree/branch`).
2. **Configure**:
   - Select an **AI model** in the left sidebar.
   - Adjust the **Max retries** slider (recommended: 10).
   - Adjust the **Skip short functions** slider (recommended: 0–5 lines).
3. **Run**: In the **"Start a new task"** tab, pick **"Upload ZIP"** or **"GitHub link"** as the input source, provide the ZIP file or URL, and click **"Start analysis in background"**.
4. **Monitor**: Switch to the **"Task monitor"** tab to view live logs.
   - Click the `>` icon before a log entry to expand and view the detailed code.
   - Click the red **"Abort task"** button to stop the task at any time.
5. **Deliver**: After the task completes, click **"Download results (Zip)"** to download all PNG images.

## 🔎 Example: C → Flowchart (CS_HousekeepingCmd)

**Input (C):**
````c
CFE_Status_t CS_ReportBaselineAppCmd(const CS_ReportBaselineAppCmd_t *CmdPtr)
{
    /* command verification variables */
    CS_Res_App_Table_Entry_t *ResultsEntry;
    uint32                    Baseline;
    char                      Name[OS_MAX_API_NAME];

    strncpy(Name, CmdPtr->Payload.Name, sizeof(Name) - 1);
    Name[sizeof(Name) - 1] = '\0';

    if (CS_GetAppResTblEntryByName(&ResultsEntry, Name))
    {
        if (ResultsEntry->ComputedYet == true)
        {
            Baseline = ResultsEntry->ComparisonValue;
            CFE_EVS_SendEvent(CS_BASELINE_APP_INF_EID, CFE_EVS_EventType_INFORMATION,
                              "Report baseline of app %s is 0x%08X", Name, (unsigned int)Baseline);
        }
        else
        {
            CFE_EVS_SendEvent(CS_NO_BASELINE_APP_INF_EID, CFE_EVS_EventType_INFORMATION,
                              "Report baseline of app %s has not been computed yet", Name);
        }
        CS_AppData.HkPacket.Payload.CmdCounter++;
    }
    else
    {
        CFE_EVS_SendEvent(CS_BASELINE_INVALID_NAME_APP_ERR_EID, CFE_EVS_EventType_ERROR,
                          "App report baseline failed, app %s not found", Name);
        CS_AppData.HkPacket.Payload.CmdErrCounter++;
    }

    return CFE_SUCCESS;
}
````

**Output (Flowchart):**

![CS_HousekeepingCmd Flowchart](./examples/CS_ReportBaselineAppCmd.png)

- Makes error-handling and telemetry path obvious at a glance
- Supports both **English** and **Chinese** annotation styles via `config.yaml`
- Helps with code structure comprehension and semantic understanding
