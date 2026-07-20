def postprocess_plantuml(content):
    """Normalize an LLM response into a clean @startuml/@enduml PlantUML block."""
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


def call_llm(client, model, messages, postprocess=postprocess_plantuml):
    if "qwen3" in model:
        response = client.chat.completions.create(model=model, messages=messages, extra_body={"enable_thinking": False})
    else:
        response = client.chat.completions.create(model=model, messages=messages)

    return postprocess(response.choices[0].message.content)
