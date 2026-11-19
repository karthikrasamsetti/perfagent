# =====================================================================
# APPEND THIS to src/perfagent/db/models.py
# (reuse the existing `Base` declared at the top of that module --
#  do NOT create a second Base)
# =====================================================================
import enum
from datetime import datetime
from sqlalchemy import (
    Column, String, Integer, Float, DateTime, Enum as SAEnum, JSON, Text,
)
# from .models import Base   <-- already present in the file; shown for clarity


class RunStatus(str, enum.Enum):
    RUNNING = "running"
    PASSED = "passed"              # mirrors verdict PASS
    FAILED = "failed"             # verdict FAIL
    INCONCLUSIVE = "inconclusive"  # verdict INCONCLUSIVE


class RunRecord(Base):
    """Denormalized per-run row for historical reporting & coverage.

    Populated at run completion from stats/aggregator.py + analyzer/
    verdict.py. Separate from the raw runs/reports tables so reporting
    queries stay cheap and the schema here is purpose-built for trend
    and coverage lookups.
    """
    __tablename__ = "run_records"

    run_id = Column(String, primary_key=True)
    scenario = Column(String, nullable=False, index=True)
    environment = Column(String, nullable=False, index=True)  # dev/staging/prod
    target_url = Column(String, nullable=False)
    load_tool = Column(String, nullable=False, default="k6")
    status = Column(SAEnum(RunStatus), nullable=False, index=True)

    started_at = Column(DateTime(timezone=True), nullable=False, index=True)
    finished_at = Column(DateTime(timezone=True), nullable=True)

    total_requests = Column(Integer, default=0)
    error_rate = Column(Float, default=0.0)
    p50_ms = Column(Float, nullable=True)
    p90_ms = Column(Float, nullable=True)
    p95_ms = Column(Float, nullable=True)
    p99_ms = Column(Float, nullable=True)
    rps = Column(Float, nullable=True)
    max_vus = Column(Integer, nullable=True)

    verdict = Column(String, nullable=True)        # PASS/FAIL/INCONCLUSIVE
    thresholds = Column(JSON, nullable=True)       # evaluated SLA rules
    coverage = Column(JSON, nullable=True)         # endpoints/flows exercised
    ai_narrative = Column(Text, nullable=True)     # narrator output (read-only)
    requested_by = Column(String, nullable=True)   # stakeholder attribution

    def as_full_dict(self) -> dict:
        out = {}
        for c in self.__table__.columns:
            v = getattr(self, c.name)
            if isinstance(v, datetime):
                v = v.isoformat()
            elif isinstance(v, RunStatus):
                v = v.value
            out[c.name] = v
        return out
