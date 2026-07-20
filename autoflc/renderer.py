import os
import shutil
import subprocess
import tempfile


def render_plantuml(puml_content, output_path, jar_path="plantuml.jar", timeout=30):
    abs_jar_path = os.path.abspath(jar_path)

    with tempfile.NamedTemporaryFile(mode="w", suffix=".puml", delete=False, encoding="utf-8") as tmp:
        tmp.write(puml_content)
        tmp_path = tmp.name

    try:
        cmd = ["java", "-jar", abs_jar_path, "-charset", "UTF-8", "-tpng", tmp_path]
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
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
