from pydantic import BaseModel, Field


MAX_STRUCTURED_RETRIES_GLOBAL = 3
MAX_REPAIR_ATTEMPTS = 2
MAX_LLM_RETRIES = 1


class CancellationOption(BaseModel):
    option_id: str
    description: str
    financial_impact_ars: float
    client_relationship_impact: str = "neutral"
    recommendation_score: float = 0.5


class VehicleActivationPriority(BaseModel):
    vehicle_id: str
    branch: str
    priority: int
    reason: str = ""


class CEOResponse(BaseModel):
    summary: str = Field(description="Executive summary of the situation")
    priorities: list[str] = Field(default_factory=list)
    delegations: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    kpis_snapshot: dict = Field(default_factory=dict)
    escalations: list[str] = Field(default_factory=list)
    recommended_actions: list[str] = Field(default_factory=list)
    recommended_option: str | None = None
    cancellation_options: list[CancellationOption] = Field(default_factory=list)
    client_ltv_estimate_ars: float | None = None
    approved_rate: float | None = None
    categories: list[str] = Field(default_factory=list)
    reasoning: str | None = None
    confidence: float | None = None
    risk_flags: list[str] = Field(default_factory=list)


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
    recommended_action: str | None = None
    discount_pct: float | None = None
    discount_amount_ars: float | None = None
    justification: str | None = None
    confidence: float | None = None
    risk_flags: list[str] = Field(default_factory=list)
    min_rate: float | None = None
    max_rate: float | None = None
    recommended_rate: float | None = None
    revenue_uplift_ars: float | None = None


class COOResponse(BaseModel):
    summary: str
    blockers: list[str] = Field(default_factory=list)
    task_status: str = ""
    bottlenecks: list[str] = Field(default_factory=list)
    follow_ups: list[str] = Field(default_factory=list)
    occupancy_analysis: dict = Field(default_factory=dict)
    demand_projection: dict = Field(default_factory=dict)
    operational_risk: str | None = None
    recommended_action: str | None = None
    activation_plan: list[VehicleActivationPriority] = Field(default_factory=list)
    vehicles_to_activate_now: list[str] = Field(default_factory=list)
    vehicles_to_hold: list[str] = Field(default_factory=list)
    hold_reason: str | None = None
    operational_notes: str | None = None
    confidence: float | None = None


class CMOResponse(BaseModel):
    summary: str
    campaign_status: str = ""
    cac_analysis: dict = Field(default_factory=dict)
    conversion_funnel: dict = Field(default_factory=dict)
    recommendations: list[str] = Field(default_factory=list)
