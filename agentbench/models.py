from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid")


class StateAssertion(Contract):
    path: list[str | int]
    op: Literal["equals", "length", "unique"] = "equals"
    value: Any = None


class Expectations(Contract):
    output: Any = None
    check_output: bool = False
    output_fields: dict[str, Any] = Field(default_factory=dict)
    required_tools: list[str] = Field(default_factory=list)
    forbidden_tools: list[str] = Field(default_factory=list)
    max_calls: dict[str, int] = Field(default_factory=dict)
    state: list[StateAssertion] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def enable_explicit_output(cls, data):
        if isinstance(data, dict) and "output" in data and "check_output" not in data:
            return {**data, "check_output": True}
        return data

    @model_validator(mode="after")
    def valid_counts(self):
        if any(count < 0 for count in self.max_calls.values()):
            raise ValueError("max_calls values must be nonnegative")
        return self


class Scenario(Contract):
    id: str = Field(min_length=1)
    input: dict[str, Any]
    initial_state: dict[str, Any]
    expected: Expectations
    tags: list[str] = Field(default_factory=list)


class Dataset(Contract):
    version: str
    scenarios: list[Scenario] = Field(min_length=1)

    @model_validator(mode="after")
    def unique_ids(self):
        ids = [s.id for s in self.scenarios]
        if len(ids) != len(set(ids)):
            raise ValueError("scenario IDs must be unique")
        return self


class AgentResponse(Contract):
    output: Any
    usage: dict[str, int | float] | None = None


class ToolCall(Contract):
    name: str
    arguments: dict[str, Any]
    result: Any = None
    error: str | None = None


class Score(Contract):
    evaluator: str
    passed: bool
    reason: str
    evidence: dict[str, Any] = Field(default_factory=dict)


class EvaluationRun(Contract):
    id: str
    scenario_id: str
    trial: int
    status: Literal["completed", "error", "timeout", "step_limit"]
    output: Any = None
    calls: list[ToolCall] = Field(default_factory=list)
    final_state: dict[str, Any]
    scores: list[Score] = Field(default_factory=list)
    latency_ms: float
    usage: dict[str, int | float] | None = None
    error: str | None = None

    @property
    def passed(self) -> bool:
        return self.status == "completed" and bool(self.scores) and all(s.passed for s in self.scores)
