import os
import re
from dataclasses import dataclass

import yaml

DEFAULT_CONFIG = {"models": [], "processing": {}, "prompts": {}, "ui": {}}

GENERIC_API_KEY_ENV = "AUTOFLC_API_KEY"


def load_config(path="config.yaml"):
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)
    return dict(DEFAULT_CONFIG)


def _model_env_var(model_name):
    slug = re.sub(r"[^A-Za-z0-9]+", "_", model_name.strip()).strip("_").upper()
    return f"{GENERIC_API_KEY_ENV}_{slug}" if slug else GENERIC_API_KEY_ENV


def resolve_api_key(model_config):
    """API key for a model config; an environment variable always overrides config.yaml.

    Checked in order: AUTOFLC_API_KEY_<MODEL_NAME>, AUTOFLC_API_KEY, then the
    config.yaml value. This lets config.yaml be committed without a real secret.
    """
    model_name = model_config.get("name", "")
    per_model_env = os.environ.get(_model_env_var(model_name)) if model_name else None
    if per_model_env:
        return per_model_env
    generic_env = os.environ.get(GENERIC_API_KEY_ENV)
    if generic_env:
        return generic_env
    return model_config.get("api_key", "")


@dataclass
class LanguageStrings:
    lang: str
    system_prompt: str
    fix_syntax_prompt: str
    manual_text: str
    ui: dict


def get_language_strings(config):
    lang = config.get("language", "en")
    prompts = config.get("prompts", {})
    return LanguageStrings(
        lang=lang,
        system_prompt=prompts.get(f"system_{lang}", ""),
        fix_syntax_prompt=prompts.get(f"fix_syntax_{lang}", ""),
        manual_text=config.get(f"manual_{lang}", config.get("manual_en", "")),
        ui=config.get("ui", {}).get(lang, {}),
    )
