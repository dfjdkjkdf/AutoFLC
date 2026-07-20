from autoflc.llm_client import postprocess_plantuml


def test_plantuml_fenced_block():
    content = "Here is the diagram:\n```plantuml\n@startuml\n:Begin;\n@enduml\n```\nThanks"
    assert postprocess_plantuml(content) == "@startuml\n:Begin;\n@enduml"


def test_generic_fenced_block():
    content = "```\n@startuml\n:A;\n@enduml\n```"
    assert postprocess_plantuml(content) == "@startuml\n:A;\n@enduml"


def test_unfenced_with_surrounding_prose_is_trimmed():
    content = "Sure! Here's the flowchart.\n@startuml\n:Step;\n@enduml\nLet me know if you need changes."
    assert postprocess_plantuml(content) == "@startuml\n:Step;\n@enduml"


def test_missing_startuml_is_prepended():
    content = ":Step;\n@enduml"
    assert postprocess_plantuml(content) == "@startuml\n:Step;\n@enduml"


def test_missing_both_markers_are_wrapped():
    content = ":Step;"
    assert postprocess_plantuml(content) == "@startuml\n:Step;\n@enduml"
