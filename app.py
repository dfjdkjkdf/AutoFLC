import streamlit as st
import os
import yaml
import zipfile
import shutil
import subprocess
import time
import datetime
from zoneinfo import ZoneInfo
import json
import threading
import re
from openai import OpenAI
from tree_sitter_languages import get_language, get_parser


# --- Config loading ---
def load_config():
    if os.path.exists("config.yaml"):
        with open("config.yaml", "r", encoding="utf-8") as f:
            return yaml.safe_load(f)
    return {"models": [], "processing": {}, "prompts": {}, "manual": ""}


CONFIG = load_config()
PLANTUML_JAR = "plantuml.jar"
HISTORY_DIR = "history"
TASKS_FILE = os.path.join(HISTORY_DIR, "tasks.json")

if not os.path.exists(HISTORY_DIR):
    os.makedirs(HISTORY_DIR)


# --- Task tracker ---
class TaskTracker:
    def __init__(self):
        self.lock = threading.Lock()
        if not os.path.exists(TASKS_FILE):
            self._save({})

    def _load(self):
        try:
            with open(TASKS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            return {}

    def _save(self, data):
        with open(TASKS_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def create_task(self, task_id, total_files, model_display_name, zip_name):
        with self.lock:
            data = self._load()
            data[task_id] = {
                "status": "running",
                "created_at": datetime.datetime.now(tz=ZoneInfo("Asia/Shanghai")).strftime("%Y-%m-%d %H:%M:%S"),
                "model_name": model_display_name,
                "zip_name": zip_name,
                "total_files": total_files,
                "processed_files": 0,
                "logs": [],
                "output_zip": "",
                "total_success_lines": 0,  # total lines of successfully converted functions
            }
            self._save(data)

    def set_total_files(self, task_id, total):
        with self.lock:
            data = self._load()
            if task_id in data:
                data[task_id]["total_files"] = total
                self._save(data)
    
    def set_total_success_lines(self, task_id, func):
        with self.lock:
            data = self._load()
            if task_id in data:
                if "total_success_lines" in data[task_id] and "line_count" in func:
                    data[task_id]["total_success_lines"] += func["line_count"]
                    self._save(data)

    def add_log(self, task_id, level, message, details=None):
        with self.lock:
            data = self._load()
            if task_id in data:
                timestamp = datetime.datetime.now(tz=ZoneInfo("Asia/Shanghai")).strftime("%Y-%m-%d %H:%M:%S")
                log_entry = {"ts": timestamp, "level": level, "msg": message, "details": details}
                data[task_id]["logs"].append(log_entry)
                self._save(data)

    def update_progress(self, task_id, processed_count):
        with self.lock:
            data = self._load()
            if task_id in data:
                data[task_id]["processed_files"] = processed_count
                self._save(data)

    def finish_task(self, task_id, zip_path):
        with self.lock:
            data = self._load()
            if task_id in data:
                if data[task_id]["status"] == "aborted":
                    return
                data[task_id]["status"] = "completed"
                data[task_id]["output_zip"] = zip_path
                data[task_id]["processed_files"] = data[task_id]["total_files"]
                self._save(data)

    def fail_task(self, task_id, error_msg):
        with self.lock:
            data = self._load()
            if task_id in data:
                if data[task_id]["status"] == "aborted":
                    return
                data[task_id]["status"] = "failed"
                self.add_log(task_id, "error", f"Task terminated: {error_msg}")
                self._save(data)

    def cancel_task(self, task_id):
        with self.lock:
            data = self._load()
            if task_id in data and data[task_id]["status"] == "running":
                data[task_id]["status"] = "aborted"
                timestamp = datetime.datetime.now(tz=ZoneInfo("Asia/Shanghai")).strftime("%Y-%m-%d %H:%M:%S")
                data[task_id]["logs"].append(
                    {"ts": timestamp, "level": "warning", "msg": "Task aborted by user", "details": None}
                )
                self._save(data)

    def get_status(self, task_id):
        data = self._load()
        return data.get(task_id, {}).get("status", "unknown")

    def get_all_tasks(self):
        return self._load()


tracker = TaskTracker()


# --- Background logger ---
class BackgroundLogger:
    def __init__(self, task_id, tracker):
        self.task_id = task_id
        self.tracker = tracker

    def info(self, message):
        self.tracker.add_log(self.task_id, "info", message)

    def success(self, message, image_path=None):
        details = {"image_path": image_path} if image_path else None
        self.tracker.add_log(self.task_id, "success", message, details)

    def warning(self, message, code=None, err_msg=None):
        details = {"code": code, "err_msg": err_msg} if code or err_msg else None
        self.tracker.add_log(self.task_id, "warning", message, details)

    def error(self, message, code=None, err_msg=None):
        details = {"code": code, "err_msg": err_msg} if code or err_msg else None
        self.tracker.add_log(self.task_id, "error", message, details)


# --- Core functions ---
def get_func_name_from_node(node, code_bytes):
    try:
        curr = node.child_by_field_name("declarator")
        while curr:
            if curr.type == "identifier":
                return code_bytes[curr.start_byte : curr.end_byte].decode("utf-8", errors="ignore")
            if curr.type == "pointer_declarator":
                curr = curr.child_by_field_name("declarator")
                continue
            if curr.type == "function_declarator":
                curr = curr.child_by_field_name("declarator")
                continue
            if curr.type == "parenthesized_declarator":
                curr = curr.child_by_field_name("declarator")
                continue
            break
        return None
    except:
        return None


def extract_functions_from_c(code_bytes, logger=None):
    try:
        language = get_language("c")
        parser = get_parser("c")
        tree = parser.parse(code_bytes)
        root_node = tree.root_node
        functions = []
        query = language.query("(function_definition) @func_def")
        captures = query.captures(root_node)
        for node, tag in captures:
            if tag == "func_def":
                func_name = get_func_name_from_node(node, code_bytes)
                if func_name:
                    func_code = code_bytes[node.start_byte : node.end_byte].decode("utf-8", errors="ignore")
                    line_count = len(func_code.split("\n"))
                    functions.append({"name": func_name, "code": func_code, "line_count": line_count})
        return functions
    except Exception as e:
        if logger:
            logger.error(f"Tree-sitter parse error: {str(e)}")
        return []


def call_llm(client, model, messages):
    if 'qwen3' in model:
        response = client.chat.completions.create(model=model, messages=messages, extra_body={"enable_thinking": False})
    else:
        response = client.chat.completions.create(model=model, messages=messages)
    

    content = response.choices[0].message.content

    if "```plantuml" in content:
        content = content.split("```plantuml")[1].split("```")[0].strip()
    elif "```" in content:
        content = content.split("```")[1].strip()

    if "@startuml" in content:
        content = content[content.index("@startuml") :]
    if "@enduml" in content:
        content = content[: content.index("@enduml") + len("@enduml")]

    if not content.strip().startswith("@startuml"):
        content = "@startuml\n" + content
    if not content.strip().endswith("@enduml"):
        content = content + "\n@enduml"

    return content


def render_plantuml(puml_content, output_path):
    abs_jar_path = os.path.abspath(PLANTUML_JAR)
    import tempfile

    with tempfile.NamedTemporaryFile(mode="w", suffix=".puml", delete=False, encoding="utf-8") as tmp:
        tmp.write(puml_content)
        tmp_path = tmp.name

    try:
        cmd = ["java", "-jar", abs_jar_path, "-charset", "UTF-8", "-tpng", tmp_path]
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=CONFIG["processing"].get("render_timeout", 30),
        )

        if result.stderr and ("Error" in result.stderr or "Syntax" in result.stderr):
            return False, f"PlantUML syntax error: {result.stderr}"

        expected_output = tmp_path.replace(".puml", ".png")
        if os.path.exists(expected_output) and os.path.getsize(expected_output) > 0:
            shutil.move(expected_output, output_path)
            return True, None
        else:
            return False, f"Generation failed (no output): {result.stderr}"
    except Exception as e:
        return False, str(e)
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


# --- Background worker thread ---
def background_worker(task_id, zip_path, api_key, base_url, model_id, max_retries, min_lines):
    logger = BackgroundLogger(task_id, tracker)
    task_dir = os.path.join(HISTORY_DIR, task_id)
    os.makedirs(task_dir, exist_ok=True)

    logger.info(f"Task ID: {task_id}")
    logger.info("Background processing started...")

    try:
        client = OpenAI(api_key=api_key, base_url=base_url)

        extract_path = os.path.join(task_dir, "src")

        # Extract ZIP with best-effort filename decoding
        with zipfile.ZipFile(zip_path, "r") as zip_ref:
            for member in zip_ref.infolist():
                encoded_name = member.filename.encode("cp437")  # default ZIP filename encoding
                decoded_name = None

                for enc in ["gbk", "utf-8", "gb2312", "latin1"]:
                    try:
                        decoded_name = encoded_name.decode(enc)
                        if any(ord(c) > 127 for c in decoded_name):
                            break
                    except:
                        continue
                decoded_name = decoded_name or encoded_name.decode("utf-8", errors="replace")

                target_path = os.path.join(extract_path, decoded_name)

                if member.is_dir():
                    os.makedirs(target_path, exist_ok=True)
                    continue

                os.makedirs(os.path.dirname(target_path), exist_ok=True)
                with zip_ref.open(member, "r") as source, open(target_path, "wb") as target:
                    shutil.copyfileobj(source, target)

        if tracker.get_status(task_id) == "aborted":
            return

        c_files = []
        for root, dirs, files in os.walk(extract_path):
            dirs[:] = [d for d in dirs if d != "__MACOSX"]
            for file in files:
                if file.endswith(".c") and not file.startswith("._"):
                    c_files.append(os.path.join(root, file))

        logger.info(f"Scan completed: found {len(c_files)} C files.")

        all_functions = []
        for c_file in c_files:
            relative_path = os.path.relpath(c_file, extract_path)
            file_name = os.path.splitext(relative_path)[0]  # without .c
            with open(c_file, "rb") as f:
                funcs = extract_functions_from_c(f.read(), logger)
                for func in funcs:
                    if len(func["code"].split("\n")) >= min_lines:
                        func["source_file"] = file_name
                        all_functions.append(func)

        total_funcs = len(all_functions)
        tracker.set_total_files(task_id, total_funcs)
        logger.info(
            f"Extracted {total_funcs} functions (skipped functions with <{min_lines} lines). Starting generation..."
        )

        output_images = []

        for idx, func in enumerate(all_functions):
            if tracker.get_status(task_id) == "aborted":
                logger.warning("Abort signal detected. Stopping.")
                return

            func_name = func["name"]
            line_count = func.get("line_count", "N/A")
            logger.info(
                f"Processing: {func_name} | Source: {func.get('source_file', 'N/A')} | Lines: {line_count}"
            )

            try:
                prompt = CONFIG["prompts"]["system"]
                puml_code = call_llm(
                    client,
                    model_id,
                    [
                        {"role": "system", "content": prompt},
                        {"role": "user", "content": f"Code:\n{func['code']}"},
                    ],
                )

                source_file = func["source_file"]
                source_dir = os.path.join(task_dir, source_file)
                os.makedirs(source_dir, exist_ok=True)
                out_path = os.path.join(source_dir, f"{func_name}.png")

                success = False
                err_msg = ""

                for attempt in range(max_retries + 1):
                    if tracker.get_status(task_id) == "aborted":
                        return

                    success, err_msg = render_plantuml(puml_code, out_path)
                    if success:
                        break

                    if attempt < max_retries:
                        logger.warning(
                            f"[Retry {attempt+1}] Syntax issue detected. Regenerating...",
                            code=puml_code,
                            err_msg=err_msg,
                        )
                        try:
                            puml_code = call_llm(
                                client,
                                model_id,
                                [
                                    {"role": "system", "content": prompt},
                                    {"role": "user", "content": f"Code:\n{func['code']}"},
                                ],
                            )
                        except:
                            break

                if success:
                    output_images.append(out_path)
                    logger.success(f"{func_name}.png", image_path=out_path)
                    tracker.set_total_success_lines(task_id, func)
                else:
                    logger.error(f"{func_name} failed", code=puml_code, err_msg=err_msg)

            except Exception as e:
                logger.error(f"{func_name} LLM error: {str(e)}")

            tracker.update_progress(task_id, idx + 1)

        if tracker.get_status(task_id) == "aborted":
            return

        if output_images:
            result_zip_name = f"flowcharts_{task_id}.zip"
            result_zip_path = os.path.join(HISTORY_DIR, result_zip_name)
            with zipfile.ZipFile(result_zip_path, "w") as zf:
                for img in output_images:
                    arcname = os.path.relpath(img, task_dir)  # keep folder structure
                    zf.write(img, arcname)

            logger.success("All done! Packaged into a zip.")
            tracker.finish_task(task_id, result_zip_name)
        else:
            logger.warning("No valid images were generated.")
            tracker.fail_task(task_id, "No output images")

    except Exception as e:
        tracker.fail_task(task_id, f"Global exception: {str(e)}")
    finally:
        try:
            if os.path.exists(zip_path):
                os.remove(zip_path)
        except:
            pass


# --- UI main program ---
st.set_page_config(page_title="Code to Flowchart Assistant", layout="wide")
st.title("C Code to Flowchart Assistant")

# --- Sidebar ---
with st.sidebar:
    st.header("Settings")

    model_list = CONFIG.get("models", [])
    if not model_list:
        st.error("No models configured in config.yaml!")
        st.stop()

    model_map = {m["name"]: m for m in model_list}
    selected_model_name = st.selectbox("Select AI model", list(model_map.keys()))
    selected_config = model_map[selected_model_name]

    st.divider()
    max_retries = st.slider("Max retries", 0, 10, CONFIG["processing"]["max_retries"])

    default_min_lines = CONFIG["processing"].get("min_func_lines", 5)
    min_lines = st.slider(
        "Skip short functions (lines < N)",
        0,
        100,
        default_min_lines,
        help="Functions with fewer lines than this threshold will be skipped.",
    )


# --- Task monitor (non-blocking auto refresh) ---
@st.fragment(run_every=5)
def render_task_monitor():
    col_head1, col_head2 = st.columns([8, 2])
    with col_head1:
        st.header("Task Status Monitor")
    with col_head2:
        st.caption("Live monitoring")

    tasks = tracker.get_all_tasks()
    sorted_ids = sorted(tasks.keys(), reverse=True)

    for tid in sorted_ids:
        info = tasks[tid]
        status = info["status"]

        icon = "[RUNNING]"
        if status == "completed":
            icon = "[COMPLETED]"
        elif status == "failed":
            icon = "[FAILED]"
        elif status == "aborted":
            icon = "[ABORTED]"

        model_used = info.get("model_name", "Unknown Model")
        zip_name = info.get("zip_name", "Unknown File")

        header_text = f"{icon} {model_used} | ID: {tid} | Input: {zip_name}"

        with st.expander(header_text, expanded=(status == "running")):
            col1, col2 = st.columns([3, 1])

            with col1:
                total = info.get("total_files", 0)
                current = info.get("processed_files", 0)
                total_success_lines = info.get("total_success_lines", "N/A")

                if total > 0:
                    progress = min(current / total, 1.0)
                    st.progress(progress)
                    st.caption(f"Progress: {current} / {total} functions")

                    success_count = 0
                    logs = info.get("logs", [])
                    for log in logs:
                        if log.get("level") == "success" and ".png" in log.get("msg", ""):
                            success_count += 1
                    success_rate = (success_count / total) * 100 if total > 0 else 0
                    st.caption(f"Success rate: {success_count}/{total} ({success_rate:.1f}%)")

                    success_avglines = (
                        int(total_success_lines / max(success_count, 1))
                        if isinstance(total_success_lines, int)
                        else "N/A"
                    )
                    st.caption(
                        f"Total lines (successful functions): {total_success_lines} | Avg lines: {success_avglines}"
                    )
                else:
                    if status == "running":
                        st.info("Initializing...")
                    elif status == "aborted":
                        st.caption("Task aborted")

            with col2:
                if status == "running":
                    if st.button("Abort task", key=f"stop_{tid}", type="primary"):
                        tracker.cancel_task(tid)
                        st.rerun()

                if status == "completed" and info.get("output_zip"):
                    zip_path = os.path.join(HISTORY_DIR, info["output_zip"])
                    if os.path.exists(zip_path):
                        with open(zip_path, "rb") as f:
                            st.download_button("Download results (Zip)", f, file_name=info["output_zip"])

                if status in ["completed", "failed", "aborted"]:
                    log_text = "\r\n".join(
                        [
                            f"[{log.get('ts', '')}] {log.get('level', 'info').upper()} {log.get('msg', '')}"
                            for log in info.get("logs", [])
                        ]
                    )
                    st.download_button(
                        label="Download logs (Txt)",
                        data=log_text,
                        file_name=f"task_{tid}_logs.txt",
                        mime="text/plain",
                        key=f"log_download_{tid}",
                    )

            st.divider()
            st.markdown("**Logs**")

            logs = info.get("logs", [])
            if logs:
                count = 0
                for log in logs:
                    if status in ["completed", "aborted"]:
                        count += 1
                        maxshow = CONFIG["processing"]["maxshow_of_completed_aborted"]
                        if count > maxshow:
                            st.caption(f"Completed/aborted tasks only show the first {maxshow} log entries.")
                            break

                    if isinstance(log, str):
                        st.text(log)
                        continue

                    ts = log.get("ts", "")
                    level = log.get("level", "info")
                    msg = log.get("msg", "")
                    details = log.get("details", None)

                    icon_map = {"info": "INFO", "success": "OK", "warning": "WARN", "error": "ERR"}
                    level_tag = icon_map.get(level, "INFO")

                    log_line = f"[{ts}] {level_tag} {msg}"

                    if level == "error":
                        st.error(log_line)
                    elif level == "warning":
                        st.warning(log_line)
                    elif level == "success":
                        st.success(log_line)
                    else:
                        st.text(log_line)

                    if details:
                        if details.get("image_path"):
                            img_path = details["image_path"]
                            with st.expander(f"View image: {msg}"):
                                if os.path.exists(img_path):
                                    st.image(img_path)
                                    with open(img_path, "rb") as f:
                                        st.download_button(
                                            label="Download this image",
                                            data=f,
                                            file_name=os.path.basename(img_path),
                                            mime="image/png",
                                            key=f"download_btn_{time.time()}_{img_path}",
                                        )
                                else:
                                    st.warning("File was cleaned up or does not exist.")

                        elif details.get("code") or details.get("err_msg"):
                            with st.expander("View error details"):
                                if details.get("err_msg"):
                                    st.error(details["err_msg"])
                                if details.get("code"):
                                    st.code(details["code"], language="plantuml")
            else:
                st.caption("No logs yet.")


# --- Main tabs ---
tab1, tab2, tab3 = st.tabs(["Launch New task", "Task Monitoring", "User Manual"])

with tab1:
    uploaded_file = st.file_uploader("Upload a project zip file", type="zip")
    start_btn = st.button("Start analysis in background")

    if uploaded_file and start_btn:
        api_key = selected_config["api_key"]
        base_url = selected_config["base_url"]
        model_id = selected_config["model_id"]

        if not api_key:
            st.error("Configuration error: API key is missing for the selected model.")
        else:
            timestamp = datetime.datetime.now(tz=ZoneInfo("Asia/Shanghai")).strftime("%Y-%m-%d %H-%M-%S")

            raw_name = uploaded_file.name
            safe_name = re.sub(r"[^\w\.-]", "_", raw_name)
            if safe_name.lower().endswith(".zip"):
                safe_name = safe_name[:-4]

            task_id = f"{timestamp} {safe_name}"

            temp_zip_path = os.path.join(HISTORY_DIR, f"upload_{task_id}.zip")
            with open(temp_zip_path, "wb") as f:
                f.write(uploaded_file.getbuffer())

            tracker.create_task(task_id, 0, selected_model_name, uploaded_file.name)

            thread = threading.Thread(
                target=background_worker,
                args=(task_id, temp_zip_path, api_key, base_url, model_id, max_retries, min_lines),
            )
            thread.start()

            st.success(f"Task {task_id} submitted!")
            time.sleep(1)
            st.rerun()

with tab2:
    render_task_monitor()

with tab3:
    manual_content = CONFIG.get("manual", "### No user manual\nPlease configure the `manual` field in config.yaml.")
    st.markdown(manual_content)