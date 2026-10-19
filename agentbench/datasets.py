import hashlib
import json
from pathlib import Path

import yaml

from .models import Dataset


def load_dataset(path: Path) -> Dataset:
    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() == ".json":
        data = json.loads(text)
    elif path.suffix.lower() in {".yaml", ".yml"}:
        data = yaml.safe_load(text)
    else:
        raise ValueError("dataset must be YAML or JSON")
    return Dataset.model_validate(data)


def dataset_hash(dataset: Dataset) -> str:
    canonical = json.dumps(dataset.model_dump(mode="json"), sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(canonical.encode()).hexdigest()
