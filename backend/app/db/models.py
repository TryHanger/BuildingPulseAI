import datetime
from sqlalchemy import Column, String, Integer, Float, Boolean, DateTime, Text, ForeignKey, JSON
from sqlalchemy.orm import relationship
from backend.app.db.session import Base

class Dataset(Base):
    __tablename__ = "datasets"

    id = Column(String(64), primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    source_kind = Column(String(32), nullable=False)  # PUBLIC_REAL, SIMULATED_BENCHMARK, SYNTHETIC_DEMO, USER_UPLOADED
    source_url = Column(String(512), nullable=True)
    license_note = Column(String(512), nullable=True)
    sha256 = Column(String(64), nullable=True, index=True)
    size_bytes = Column(Integer, nullable=True)
    imported_at = Column(DateTime, default=datetime.datetime.utcnow)
    processing_version = Column(String(32), default="1.0.0")
    status = Column(String(32), default="READY")  # READY, IMPORTING, ERROR
    provenance_note = Column(Text, nullable=True)

    scenarios = relationship("Scenario", back_populates="dataset", cascade="all, delete-orphan")


class Scenario(Base):
    __tablename__ = "scenarios"

    id = Column(String(64), primary_key=True, index=True)
    dataset_id = Column(String(64), ForeignKey("datasets.id"), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    start_at = Column(String(32), nullable=True)  # ISO-8601 string representation
    end_at = Column(String(32), nullable=True)
    sample_interval_seconds = Column(Integer, default=60)
    timezone_status = Column(String(32), default="unknown")  # unknown, UTC, local_tmy
    source_fault_label = Column(String(128), nullable=True)  # Ground truth from dataset source
    source_fault_label_type = Column(String(64), nullable=True)  # FAULT_FREE, SENSOR_BIAS, VALVE_LEAK, VALVE_STUCK, DAMPER_STUCK
    description = Column(Text, nullable=True)
    data_path = Column(String(512), nullable=False)  # Relative or absolute path to Parquet file
    total_rows = Column(Integer, default=0)

    dataset = relationship("Dataset", back_populates="scenarios")
    sensors = relationship("Sensor", back_populates="scenario", cascade="all, delete-orphan")
    events = relationship("DiagnosticEvent", back_populates="scenario", cascade="all, delete-orphan")


class Sensor(Base):
    __tablename__ = "sensors"

    id = Column(Integer, primary_key=True, autoincrement=True)
    scenario_id = Column(String(64), ForeignKey("scenarios.id"), nullable=False, index=True)
    canonical_key = Column(String(64), nullable=False, index=True)
    original_column = Column(String(128), nullable=False)
    display_name_ru = Column(String(255), nullable=False)
    unit_raw = Column(String(32), nullable=True)
    unit_normalized = Column(String(32), nullable=True)
    component = Column(String(64), nullable=False)  # OUTDOOR, MIXING, COOLING_COIL, FAN, RETURN, ZONE
    signal_kind = Column(String(32), nullable=False)  # MEASUREMENT, COMMAND, FEEDBACK
    is_basic = Column(Boolean, default=True)
    is_available = Column(Boolean, default=True)

    scenario = relationship("Scenario", back_populates="sensors")


class ImportRecord(Base):
    __tablename__ = "imports"

    id = Column(String(64), primary_key=True, index=True)
    filename = Column(String(255), nullable=False)
    sha256 = Column(String(64), nullable=False, index=True)
    status = Column(String(32), nullable=False)  # SUCCESS, FAILED, DUPLICATE_SKIPPED
    errors = Column(Text, nullable=True)
    rows_count = Column(Integer, default=0)
    imported_at = Column(DateTime, default=datetime.datetime.utcnow)


class DiagnosticEvent(Base):
    __tablename__ = "diagnostic_events"

    id = Column(String(64), primary_key=True, index=True)
    scenario_id = Column(String(64), ForeignKey("scenarios.id"), nullable=False, index=True)
    started_at = Column(String(32), nullable=False)
    ended_at = Column(String(32), nullable=False)
    rule_id = Column(String(64), nullable=False)
    severity = Column(String(32), default="WARNING")  # INFO, WARNING, CRITICAL
    evidence_json = Column(JSON, nullable=True)
    conclusion_type = Column(String(64), nullable=False)  # DATA_QUALITY, PHYSICAL_BASELINE
    generated_by_version = Column(String(32), default="rule_engine_v1")

    scenario = relationship("Scenario", back_populates="events")
