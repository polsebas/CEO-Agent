from pydantic import BaseModel, Field


class AgentHealth(BaseModel):
    agent_id: str
    success_rate: float = Field(default=1.0, ge=0.0, le=1.0)
    avg_latency_ms: float = 0.0
    hallucination_rate: float = Field(default=0.0, ge=0.0, le=1.0)
    policy_violations: int = 0
    retries_per_run: float = 0.0
    degraded_mode: bool = False
    total_runs: int = 0
    successful_runs: int = 0

    def record_run(self, *, success: bool, latency_ms: float, structured_failure: bool = False) -> None:
        self.total_runs += 1
        if success:
            self.successful_runs += 1
        if structured_failure:
            failures = self.hallucination_rate * (self.total_runs - 1) + 1
            self.hallucination_rate = failures / self.total_runs
        self.success_rate = self.successful_runs / self.total_runs if self.total_runs else 1.0
        self.avg_latency_ms = (
            (self.avg_latency_ms * (self.total_runs - 1) + latency_ms) / self.total_runs
            if self.total_runs
            else latency_ms
        )
        self.degraded_mode = self.success_rate < 0.7
