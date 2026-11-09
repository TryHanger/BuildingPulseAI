from pathlib import Path
from typing import Optional, Tuple
import pandas as pd
from sqlalchemy.orm import Session, joinedload
from backend.app.core.config import settings
from backend.app.db.models import Scenario

def load_scenario_data(scenario_id: str, db: Optional[Session] = None) -> Tuple[pd.DataFrame, Scenario]:
    """Loads raw historical simulation/measurement dataframe and Scenario metadata from Parquet."""
    if db is None:
        from backend.app.db.session import SessionLocal
        db_session = SessionLocal()
        close_db = True
    else:
        db_session = db
        close_db = False

    try:
        scenario = (
            db_session.query(Scenario)
            .options(joinedload(Scenario.dataset))
            .filter(Scenario.id == scenario_id)
            .first()
        )
        if not scenario:
            raise ValueError(f"Scenario '{scenario_id}' not found in database")

        parquet_path = Path(scenario.data_path)
        if not parquet_path.is_absolute():
            parquet_path = settings.BASE_DIR / parquet_path

        if not parquet_path.exists():
            raise FileNotFoundError(f"Parquet file {parquet_path} does not exist")

        df = pd.read_parquet(parquet_path)
        return df, scenario
    finally:
        if close_db:
            db_session.close()
