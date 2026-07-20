import datetime
import os
import re
import threading
import time
from zoneinfo import ZoneInfo

import streamlit as st

from autoflc.config import get_language_strings, load_config, resolve_api_key
from autoflc.github_source import GithubSourceError, fetch_github_zip, parse_github_url
from autoflc.task_tracker import TaskTracker
from autoflc.worker import background_worker

PLANTUML_JAR = os.environ.get("PLANTUML_JAR", "plantuml.jar")
HISTORY_DIR = "history"

os.makedirs(HISTORY_DIR, exist_ok=True)

CONFIG = load_config()
STRINGS = get_language_strings(CONFIG)
UI = STRINGS.ui

tracker = TaskTracker(os.path.join(HISTORY_DIR, "tasks.json"))

# --- UI main program ---
st.set_page_config(page_title=UI["app_title"], layout="wide")
st.title(UI["app_title"])

# --- Sidebar ---
with st.sidebar:
    st.header(UI["label_status"])

    model_list = CONFIG.get("models", [])
    if not model_list:
        st.error("No models configured in config.yaml!")
        st.stop()

    model_map = {m["name"]: m for m in model_list}
    selected_model_name = st.selectbox(UI["label_model"], list(model_map.keys()))
    selected_config = model_map[selected_model_name]

    st.divider()
    max_retries = st.slider(UI["label_retries"], 0, 10, CONFIG["processing"]["max_retries"])

    default_min_lines = CONFIG["processing"].get("min_func_lines", 5)
    min_lines = st.slider(
        UI["label_min_lines"],
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
        st.header(UI["tab_monitor"])
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
                        st.info(UI["msg_running"])
                    elif status == "aborted":
                        st.caption(UI["msg_aborted"])

            with col2:
                if status == "running":
                    if st.button(UI["btn_abort"], key=f"stop_{tid}", type="primary"):
                        tracker.cancel_task(tid)
                        st.rerun()

                if status == "completed" and info.get("output_zip"):
                    zip_path = os.path.join(HISTORY_DIR, info["output_zip"])
                    if os.path.exists(zip_path):
                        with open(zip_path, "rb") as f:
                            st.download_button(UI["btn_download"], f, file_name=info["output_zip"])

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
            st.markdown(f"**{UI['label_log']}**")

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
                st.caption(UI["msg_no_task"])


# --- Main tabs ---
manual_tab_label = "User Manual" if STRINGS.lang == "en" else "用户手册"
tab1, tab2, tab3 = st.tabs([UI["tab_new_task"], UI["tab_monitor"], manual_tab_label])

with tab1:
    input_source = st.radio(
        UI["label_input_source"],
        ["zip", "github"],
        format_func=lambda v: UI["option_upload_zip"] if v == "zip" else UI["option_github_link"],
        horizontal=True,
    )

    uploaded_file = None
    github_url = ""
    if input_source == "zip":
        uploaded_file = st.file_uploader(UI["label_upload"], type="zip")
    else:
        github_url = st.text_input(
            UI["label_github_url"],
            placeholder="https://github.com/owner/repo or https://github.com/owner/repo/tree/branch",
        )

    start_btn = st.button(UI["btn_start"])

    if start_btn:
        if input_source == "zip" and not uploaded_file:
            st.warning(UI["msg_uploading"])
        elif input_source == "github" and not github_url.strip():
            st.warning(UI["msg_enter_github_url"])
        else:
            api_key = resolve_api_key(selected_config)
            base_url = selected_config["base_url"]
            model_id = selected_config["model_id"]

            if not api_key:
                st.error("Configuration error: API key is missing for the selected model.")
            else:
                timestamp = datetime.datetime.now(tz=ZoneInfo("Asia/Shanghai")).strftime("%Y-%m-%d %H-%M-%S")
                temp_zip_path = None

                if input_source == "zip":
                    raw_name = uploaded_file.name
                    safe_name = re.sub(r"[^\w\.-]", "_", raw_name)
                    if safe_name.lower().endswith(".zip"):
                        safe_name = safe_name[:-4]

                    task_id = f"{timestamp} {safe_name}"
                    temp_zip_path = os.path.join(HISTORY_DIR, f"upload_{task_id}.zip")
                    with open(temp_zip_path, "wb") as f:
                        f.write(uploaded_file.getbuffer())
                    zip_name = uploaded_file.name
                else:
                    try:
                        with st.spinner(UI["msg_resolving_github"]):
                            ref = parse_github_url(github_url.strip())
                            safe_name = re.sub(r"[^\w.-]", "_", f"{ref.owner}_{ref.repo}_{ref.ref}")
                            task_id = f"{timestamp} {safe_name}"
                            temp_zip_path = fetch_github_zip(github_url.strip(), HISTORY_DIR)
                        zip_name = f"{ref.owner}/{ref.repo}@{ref.ref}"
                    except GithubSourceError as e:
                        st.error(f"{UI['msg_github_fetch_failed']}: {e}")

                if temp_zip_path:
                    tracker.create_task(task_id, 0, selected_model_name, zip_name)

                    thread = threading.Thread(
                        target=background_worker,
                        args=(task_id, temp_zip_path, api_key, base_url, model_id, max_retries, min_lines),
                        kwargs=dict(
                            tracker=tracker,
                            history_dir=HISTORY_DIR,
                            system_prompt=STRINGS.system_prompt,
                            plantuml_jar=PLANTUML_JAR,
                            render_timeout=CONFIG["processing"].get("render_timeout", 30),
                        ),
                    )
                    thread.start()

                    st.success(f"Task {task_id} submitted!")
                    time.sleep(1)
                    st.rerun()

with tab2:
    render_task_monitor()

with tab3:
    st.markdown(STRINGS.manual_text)
