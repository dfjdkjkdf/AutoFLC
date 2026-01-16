# 🤖 C Code to Flowchart Agent (Dockerized)

https://github.com/user-attachments/assets/821491f9-1f97-4b1c-a1f0-415dcb58db82

This is a Docker-based, enterprise-grade tool that automatically converts C project source code into PlantUML flowcharts. It integrates a Streamlit frontend, a multi-model LLM backend (OpenAI/Ollama), and a PlantUML rendering engine.

## 📂 Directory Structure

Make sure your project directory contains the following core files:

````text
.
├── Dockerfile          # Build Docker image
├── requirements.txt    # Python dependencies
├── app.py              # Run script
├── config.yaml         # Hyperparameter config, prompts
└── history/            # Stores generated images and ZIP packages; folder name matches the task ID
````

## 🚀 Deployment and Usage Guide

### 1. Build the Image

````bash
docker build -t flowchart-agent .
````

### 2. Start the Container

````bash
docker run -d -p 8501:8501 \
  --name flowchart-dev \
  -v YOUR_PATH\config.yaml:/app/config.yaml \
  -v YOUR_PATH\app.py:/app/app.py \
  -v YOUR_PATH\history:/app/history \
  --add-host=host.docker.internal:host-gateway \
  flowchart-agent
````

## 📖 User Guide

1. **Prepare**: Compress your C project folder (e.g., the `usr` directory) into a `.zip` file.
2. **Configure**:
   - Select an **AI model** in the left sidebar.
   - Adjust the **Max retries** slider (recommended: 10).
   - Adjust the **Skip short functions** slider (recommended: 0–5 lines).
3. **Run**: In the **"Start a new task"** tab, upload the ZIP file and click **"Start analysis in background"**.
4. **Monitor**: Switch to the **"Task monitor"** tab to view live logs.
   - Click the `>` icon before a log entry to expand and view the detailed code.
   - Click the red **"Abort task"** button to stop the task at any time.
5. **Deliver**: After the task completes, click **"Download results (Zip)"** to download all PNG images.
