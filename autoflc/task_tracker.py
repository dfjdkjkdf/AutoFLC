import datetime
import json
import os
import threading
from zoneinfo import ZoneInfo


class TaskTracker:
    def __init__(self, tasks_file):
        self.tasks_file = tasks_file
        self.lock = threading.Lock()
        os.makedirs(os.path.dirname(tasks_file) or ".", exist_ok=True)
        if not os.path.exists(tasks_file):
            self._save({})

    def _load(self):
        try:
            with open(self.tasks_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}

    def _save(self, data):
        with open(self.tasks_file, "w", encoding="utf-8") as f:
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
                "total_success_lines": 0,
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
                self._save(data)
        self.add_log(task_id, "error", f"Task terminated: {error_msg}")

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
