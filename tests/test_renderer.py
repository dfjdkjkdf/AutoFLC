import subprocess

from autoflc.renderer import render_plantuml


class FakeResult:
    def __init__(self, stderr=""):
        self.stderr = stderr
        self.stdout = ""


def test_render_success(tmp_path, monkeypatch):
    def fake_run(cmd, capture_output, text, timeout):
        puml_path = cmd[-1]
        png_path = puml_path.replace(".puml", ".png")
        with open(png_path, "wb") as f:
            f.write(b"fake-png-bytes")
        return FakeResult(stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)

    output_path = tmp_path / "out.png"
    ok, err = render_plantuml("@startuml\n@enduml", str(output_path))

    assert ok is True
    assert err is None
    assert output_path.exists()
    assert output_path.read_bytes() == b"fake-png-bytes"


def test_render_syntax_error(tmp_path, monkeypatch):
    def fake_run(cmd, capture_output, text, timeout):
        return FakeResult(stderr="Syntax Error at line 2")

    monkeypatch.setattr(subprocess, "run", fake_run)

    ok, err = render_plantuml("@startuml\nbroken\n@enduml", str(tmp_path / "out.png"))

    assert ok is False
    assert "PlantUML syntax error" in err


def test_render_no_output_produced(tmp_path, monkeypatch):
    def fake_run(cmd, capture_output, text, timeout):
        return FakeResult(stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)

    ok, err = render_plantuml("@startuml\n@enduml", str(tmp_path / "out.png"))

    assert ok is False
    assert "Generation failed" in err


def test_render_subprocess_exception(tmp_path, monkeypatch):
    def fake_run(cmd, capture_output, text, timeout):
        raise subprocess.TimeoutExpired(cmd, timeout)

    monkeypatch.setattr(subprocess, "run", fake_run)

    ok, err = render_plantuml("@startuml\n@enduml", str(tmp_path / "out.png"), timeout=1)

    assert ok is False
    assert isinstance(err, str) and err
