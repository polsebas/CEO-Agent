from pydantic import BaseModel, Field


MAX_STRUCTURED_RETRIES_GLOBAL = 3
MAX_REPAIR_ATTEMPTS = 2
MAX_LLM_RETRIES = 1


class CEOResponse(BaseModel):
    summary: str = Field(description="Executive summary of the situation")
    priorities: list[str] = Field(default_factory=list)
    delegations: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    kpis_snapshot: dict = Field(default_factory=dict)
    escalations: list[str] = Field(default_factory=list)
    recommended_actions: list[str] = Field(default_factory=list)


class CTOResponse(BaseModel):
    summary: str
    incidents: list[str] = Field(default_factory=list)
    deployment_status: str = ""
    tech_debt_items: list[str] = Field(default_factory=list)
    bugs_priority: list[str] = Field(default_factory=list)
    github_summary: dict = Field(default_factory=dict)
    recommended_actions: list[str] = Field(default_factory=list)


class CFOResponse(BaseModel):
    summary: str
    cashflow_status: str = ""
    runway_months: float = 0.0
    anomalies: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)


class COOResponse(BaseModel):
    summary: str
    blockers: list[str] = Field(default_factory=list)
    task_status: str = ""
    bottlenecks: list[str] = Field(default_factory=list)
    follow_ups: list[str] = Field(default_factory=list)


class CMOResponse(BaseModel):
    summary: str
    campaign_status: str = ""
    cac_analysis: dict = Field(default_factory=dict)
    conversion_funnel: dict = Field(default_factory=dict)
    recommendations: list[str] = Field(default_factory=list)
