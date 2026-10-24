from pydantic import Field
from .models import Contract


class Thresholds(Contract):
    min_pass_rate: float = Field(default=1, ge=0, le=1, allow_inf_nan=False)
    max_pass_rate_drop: float = Field(default=0, ge=0, le=1, allow_inf_nan=False)
    max_case_regressions: int = Field(default=0, ge=0)
    max_p95_increase_pct: float | None = Field(default=None, ge=0, allow_inf_nan=False)


def compare_reports(baseline, candidate, thresholds=None):
    thresholds = thresholds or Thresholds()
    for key in ("dataset_hash", "dataset_version", "evaluators", "runner", "tool_factory", "execution_mode"):
        if baseline["experiment"][key] != candidate["experiment"][key]:
            raise ValueError(f"incompatible experiments: {key} differs")
    def indexed(report):
        return {(r["scenario_id"], r["trial"]): r for r in report["runs"]}
    left, right = indexed(baseline), indexed(candidate)
    if left.keys() != right.keys():
        raise ValueError("incompatible experiments: scenario/trial coverage differs")
    regressions = [{"scenario_id": key[0], "trial": key[1]} for key in sorted(left)
                   if left[key]["passed"] and not right[key]["passed"]]
    improvements = [{"scenario_id": key[0], "trial": key[1]} for key in sorted(left)
                    if not left[key]["passed"] and right[key]["passed"]]
    before, after = baseline["summary"], candidate["summary"]
    drop = before["pass_rate"] - after["pass_rate"]
    violations = []
    if after["pass_rate"] < thresholds.min_pass_rate:
        violations.append(f"candidate pass rate {after['pass_rate']:.1%} below minimum {thresholds.min_pass_rate:.1%}")
    if drop > thresholds.max_pass_rate_drop + 1e-12:
        violations.append(f"pass-rate drop {drop:.1%} exceeds {thresholds.max_pass_rate_drop:.1%}")
    if len(regressions) > thresholds.max_case_regressions:
        violations.append(f"{len(regressions)} case/trial regressions exceed {thresholds.max_case_regressions}")
    limit = thresholds.max_p95_increase_pct
    if limit is not None and after["latency_p95_ms"] > before["latency_p95_ms"] * (1 + limit / 100):
        violations.append(f"p95 latency increase exceeds {limit:g}%")
    return {"passed": not violations, "violations": violations, "thresholds": thresholds.model_dump(),
            "execution_mode": candidate["experiment"]["execution_mode"],
            "baseline": before, "candidate": after, "pass_rate_delta": -drop,
            "regressions": regressions, "improvements": improvements,
            "per_scenario": [{"scenario_id": scenario,
                              "baseline_pass_rate": sum(r["passed"] for k, r in left.items() if k[0] == scenario) / sum(k[0] == scenario for k in left),
                              "candidate_pass_rate": sum(r["passed"] for k, r in right.items() if k[0] == scenario) / sum(k[0] == scenario for k in right)}
                             for scenario in sorted({k[0] for k in left})]}
