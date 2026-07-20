import os
import zipfile

from openai import OpenAI

from .archive import extract_zip
from .c_parser import extract_functions_from_c
from .llm_client import call_llm
from .renderer import render_plantuml
from .task_tracker import BackgroundLogger


def background_worker(
    task_id,
    zip_path,
    api_key,
    base_url,
    model_id,
    max_retries,
    min_lines,
    *,
    tracker,
    history_dir,
    system_prompt,
    plantuml_jar="plantuml.jar",
    render_timeout=30,
):
    logger = BackgroundLogger(task_id, tracker)
    task_dir = os.path.join(history_dir, task_id)
    os.makedirs(task_dir, exist_ok=True)

    logger.info(f"Task ID: {task_id}")
    logger.info("Background processing started...")

    try:
        client = OpenAI(api_key=api_key, base_url=base_url)

        extract_path = os.path.join(task_dir, "src")
        extract_zip(zip_path, extract_path)

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
            file_name = os.path.splitext(relative_path)[0]
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
                puml_code = call_llm(
                    client,
                    model_id,
                    [
                        {"role": "system", "content": system_prompt},
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

                    success, err_msg = render_plantuml(
                        puml_code, out_path, jar_path=plantuml_jar, timeout=render_timeout
                    )
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
                                    {"role": "system", "content": system_prompt},
                                    {"role": "user", "content": f"Code:\n{func['code']}"},
                                ],
                            )
                        except Exception:
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
            result_zip_path = os.path.join(history_dir, result_zip_name)
            with zipfile.ZipFile(result_zip_path, "w") as zf:
                for img in output_images:
                    arcname = os.path.relpath(img, task_dir)
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
        except Exception:
            pass
