import json
from pathlib import Path
import pytest
from agentbench.datasets import load_dataset, dataset_hash


def test_yaml_json_have_same_semantic_hash(tmp_path):
    data = load_dataset(Path(__file__).parents[1] / "datasets/refunds.yaml")
    path = tmp_path / "cases.json"
    path.write_text(json.dumps(data.model_dump()), encoding="utf-8")
    assert dataset_hash(data) == dataset_hash(load_dataset(path))
    changed = data.model_copy(deep=True)
    changed.scenarios[0].input["order_id"] = "other"
    assert dataset_hash(changed) != dataset_hash(data)


def test_invalid_dataset_rejected(tmp_path):
    path = tmp_path / "bad.yaml"
    path.write_text("version: '1'\nscenarios: []")
    with pytest.raises(ValueError):
        load_dataset(path)
