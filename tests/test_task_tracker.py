from autoflc.task_tracker import TaskTracker


def _tracker(tmp_path):
    return TaskTracker(str(tmp_path / "tasks.json"))


def test_create_task_sets_running_status(tmp_path):
    t = _tracker(tmp_path)
    t.create_task("task-1", total_files=3, model_display_name="Qwen3-32b", zip_name="src.zip")

    task = t.get_all_tasks()["task-1"]
    assert task["status"] == "running"
    assert task["total_files"] == 3
    assert task["zip_name"] == "src.zip"


def test_add_log_appends_entry(tmp_path):
    t = _tracker(tmp_path)
    t.create_task("task-1", 1, "model", "src.zip")
    t.add_log("task-1", "info", "hello")

    logs = t.get_all_tasks()["task-1"]["logs"]
    assert len(logs) == 1
    assert logs[0]["level"] == "info"
    assert logs[0]["msg"] == "hello"


def test_update_progress(tmp_path):
    t = _tracker(tmp_path)
    t.create_task("task-1", 5, "model", "src.zip")
    t.update_progress("task-1", 3)

    assert t.get_all_tasks()["task-1"]["processed_files"] == 3


def test_set_total_success_lines_accumulates(tmp_path):
    t = _tracker(tmp_path)
    t.create_task("task-1", 1, "model", "src.zip")
    t.set_total_success_lines("task-1", {"line_count": 10})
    t.set_total_success_lines("task-1", {"line_count": 5})

    assert t.get_all_tasks()["task-1"]["total_success_lines"] == 15


def test_set_total_success_lines_ignores_missing_line_count(tmp_path):
    t = _tracker(tmp_path)
    t.create_task("task-1", 1, "model", "src.zip")
    t.set_total_success_lines("task-1", {})

    assert t.get_all_tasks()["task-1"]["total_success_lines"] == 0


def test_finish_task_does_not_override_aborted(tmp_path):
    t = _tracker(tmp_path)
    t.create_task("task-1", 1, "model", "src.zip")
    t.cancel_task("task-1")
    t.finish_task("task-1", "out.zip")

    assert t.get_all_tasks()["task-1"]["status"] == "aborted"


def test_fail_task_does_not_override_aborted(tmp_path):
    t = _tracker(tmp_path)
    t.create_task("task-1", 1, "model", "src.zip")
    t.cancel_task("task-1")
    t.fail_task("task-1", "boom")

    assert t.get_all_tasks()["task-1"]["status"] == "aborted"


def test_fail_task_sets_failed_and_logs_without_deadlocking(tmp_path):
    # Regression test: fail_task used to call add_log() while still holding
    # its own (non-reentrant) lock, which would deadlock. This must return.
    t = _tracker(tmp_path)
    t.create_task("task-1", 1, "model", "src.zip")
    t.fail_task("task-1", "boom")

    task = t.get_all_tasks()["task-1"]
    assert task["status"] == "failed"
    assert any("boom" in log["msg"] for log in task["logs"])


def test_cancel_task_only_affects_running(tmp_path):
    t = _tracker(tmp_path)
    t.create_task("task-1", 1, "model", "src.zip")
    t.finish_task("task-1", "out.zip")
    t.cancel_task("task-1")

    assert t.get_all_tasks()["task-1"]["status"] == "completed"


def test_persistence_across_tracker_instances(tmp_path):
    tasks_file = tmp_path / "tasks.json"
    t1 = TaskTracker(str(tasks_file))
    t1.create_task("task-1", 1, "model", "src.zip")

    t2 = TaskTracker(str(tasks_file))
    assert "task-1" in t2.get_all_tasks()
