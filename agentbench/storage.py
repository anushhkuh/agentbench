"""Redaction at the persistence boundary; evaluation uses original values."""
import json
import re
from pathlib import Path
from .reporting import markdown_report

SENSITIVE_KEYS = {"password", "passwd", "secret", "token", "api_key", "authorization",
                  "email", "phone", "address", "customer_name", "credit_card", "ssn"}


def sensitive(key):
    normalized = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", str(key)).lower().replace("-", "_")
    return any(normalized == name or normalized.endswith("_" + name) for name in SENSITIVE_KEYS)


def redact(value):
    secrets = set()

    def collect(item, protected=False):
        if isinstance(item, dict):
            for key, child in item.items():
                collect(child, protected or sensitive(key))
        elif isinstance(item, list):
            for child in item:
                collect(child, protected)
        elif protected and isinstance(item, str) and item:
            secrets.add(item)

    collect(value)

    def clean(item):
        if isinstance(item, dict):
            return {key: "[REDACTED]" if sensitive(key) else clean(child) for key, child in item.items()}
        if isinstance(item, list):
            return [clean(child) for child in item]
        if isinstance(item, str):
            for secret in sorted(secrets, key=len, reverse=True):
                item = item.replace(secret, "[REDACTED]")
            item = re.sub(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", "[REDACTED]", item)
            item = re.sub(r"(?i)Bearer\s+\S+", "Bearer [REDACTED]", item)
        return item

    return clean(value)


def save_report(report, destination: Path):
    destination = Path(destination)
    if destination.suffix.lower() != ".json":
        destination = destination / f"{report['experiment']['id']}.json"
    destination.parent.mkdir(parents=True, exist_ok=True)
    safe = redact(report)
    destination.write_text(json.dumps(safe, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    destination.with_suffix(".md").write_text(markdown_report(safe), encoding="utf-8")
    return destination, safe
