from pathlib import Path
import sys
import types

import pytest


def _install_stub(module_name: str, module: types.ModuleType) -> None:
    sys.modules.setdefault(module_name, module)


if "auto_summarization.services.config" not in sys.modules:
    config_module = types.ModuleType("auto_summarization.services.config")

    class _StubSettings:
        AUTO_SUMMARIZATION_PRETRAINED_MODEL_PATH = "/nonexistent/model"
        AUTO_SUMMARIZATION_PRETRAINED_MODEL_NAME = "joeddav/xlm-roberta-large-xnli"
        OPENAI_API_HOST = "http://localhost"
        OPENAI_API_KEY = "dummy"
        OPENAI_MODEL_NAME = "gpt-4o-mini"

    config_module.settings = _StubSettings()
    config_module.authorization = "Authorization"
    _install_stub("auto_summarization.services.config", config_module)


if "openai" not in sys.modules:
    openai_module = types.ModuleType("openai")

    class OpenAI:  # pragma: no cover - helper for import compatibility
        def __init__(self, *args, **kwargs):
            pass

    openai_module.OpenAI = OpenAI
    _install_stub("openai", openai_module)


if "transformers" not in sys.modules:
    transformers_module = types.ModuleType("transformers")

    def pipeline(*args, **kwargs):  # pragma: no cover - replaced in tests
        raise RuntimeError("pipeline stub should be patched in tests")

    transformers_module.pipeline = pipeline
    _install_stub("transformers", transformers_module)


from auto_summarization.services import models


@pytest.fixture(autouse=True)
def clear_pipeline_cache():
    models._get_zero_shot_pipeline.cache_clear()
    yield
    models._get_zero_shot_pipeline.cache_clear()


def test_pretrained_pipeline_uses_fallback_model_name(monkeypatch, tmp_path):
    missing_path = tmp_path / "missing"
    monkeypatch.setattr(
        models.settings,
        "AUTO_SUMMARIZATION_PRETRAINED_MODEL_PATH",
        str(missing_path),
        raising=False,
    )
    monkeypatch.setattr(
        models.settings,
        "AUTO_SUMMARIZATION_PRETRAINED_MODEL_NAME",
        "joeddav/xlm-roberta-large-xnli",
        raising=False,
    )

    captured = {}

    def fake_pipeline(task, model, tokenizer, device):
        captured["args"] = (task, model, tokenizer, device)

        def _fake_classifier(text, candidate_labels, multi_label):
            return {"labels": [candidate_labels[0]], "scores": [0.9]}

        return _fake_classifier

    monkeypatch.setattr(models, "pipeline", fake_pipeline)

    output = models.run_pretrained_classification("text", ["label"])

    assert output.startswith("label")
    assert captured["args"][1] == "joeddav/xlm-roberta-large-xnli"
    assert captured["args"][2] == "joeddav/xlm-roberta-large-xnli"


def test_pretrained_pipeline_uses_local_path(monkeypatch, tmp_path):
    model_dir = tmp_path / "model"
    model_dir.mkdir()
    monkeypatch.setattr(
        models.settings,
        "AUTO_SUMMARIZATION_PRETRAINED_MODEL_PATH",
        str(model_dir),
        raising=False,
    )

    captured = {}

    def fake_pipeline(task, model, tokenizer, device):
        captured["args"] = (task, model, tokenizer, device)

        def _fake_classifier(text, candidate_labels, multi_label):
            return {"labels": [candidate_labels[0]], "scores": [0.5]}

        return _fake_classifier

    monkeypatch.setattr(models, "pipeline", fake_pipeline)

    models.run_pretrained_classification("text", ["local"])

    assert Path(captured["args"][1]) == model_dir
    assert Path(captured["args"][2]) == model_dir
