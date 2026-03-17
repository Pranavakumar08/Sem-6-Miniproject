from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

import pandas as pd


@dataclass
class StarRecord:
    hip: int
    ra_deg: float
    dec_deg: float
    mag: float
    name: str


class StarCatalog:
    """Wrapper around the bright-star CSV for convenient access."""

    REQUIRED_COLUMNS = ["hip", "ra", "dec", "mag", "name"]

    def __init__(self, csv_path: Path):
        self.csv_path = Path(csv_path)
        self._df = self._load_csv(self.csv_path)

    @staticmethod
    def _load_csv(path: Path) -> pd.DataFrame:
        if not path.exists():
            raise FileNotFoundError(f"Star catalog not found at {path}")

        df = pd.read_csv(path)
        missing = [c for c in StarCatalog.REQUIRED_COLUMNS if c not in df.columns]
        if missing:
            raise ValueError(f"Catalog is missing required columns: {missing}")

        df = df.copy()
        df["hip"] = df["hip"].astype(int)
        df["ra"] = df["ra"].astype(float)
        df["dec"] = df["dec"].astype(float)
        df["mag"] = df["mag"].astype(float)
        df["name"] = df["name"].astype(str)

        # Filter out obvious placeholder rows if present
        df = df[df["mag"] < 9.9].reset_index(drop=True)
        return df

    @property
    def dataframe(self) -> pd.DataFrame:
        return self._df

    def get_star_by_hip(self, hip: int) -> Optional[StarRecord]:
        row = self._df.loc[self._df["hip"] == hip]
        if row.empty:
            return None
        r = row.iloc[0]
        return StarRecord(
            hip=int(r["hip"]),
            ra_deg=float(r["ra"]),
            dec_deg=float(r["dec"]),
            mag=float(r["mag"]),
            name=str(r["name"]),
        )

    def brightest_stars(self, limit: int = 100) -> List[StarRecord]:
        df = self._df.sort_values("mag").head(limit)
        return [
            StarRecord(
                hip=int(r["hip"]),
                ra_deg=float(r["ra"]),
                dec_deg=float(r["dec"]),
                mag=float(r["mag"]),
                name=str(r["name"]),
            )
            for _, r in df.iterrows()
        ]

