import os
from datetime import datetime, timezone
from typing import Optional
import pandas as pd
from app.connectors.base import BaseConnector, SourceMetadata, SourceSchema, ColumnSchema


class FileConnector(BaseConnector):
    """Connector for CSV, Excel (.xlsx), and JSON files.

    Config keys:
      - file_path: str — absolute path to the file
      - file_type: str — "csv" | "excel" | "json" (auto-detected from extension if omitted)
      - encoding: str — file encoding, default "utf-8"
      - sheet_name: str | int — for Excel, default 0 (first sheet)
    """

    SUPPORTED_TYPES = {"csv", "excel", "json"}

    def __init__(self, config: dict):
        super().__init__(config)
        self.file_path: str = config["file_path"]
        self.file_type: str = config.get("file_type") or self._detect_type()
        self.encoding: str = config.get("encoding", "utf-8")
        self.sheet_name = config.get("sheet_name", 0)
        self._df: Optional[pd.DataFrame] = None

    def _detect_type(self) -> str:
        ext = os.path.splitext(self.file_path)[1].lower()
        mapping = {".csv": "csv", ".xlsx": "excel", ".xls": "excel", ".json": "json"}
        detected = mapping.get(ext)
        if not detected:
            raise ValueError(
                f"Cannot detect file type from extension: {ext}. Supported: {self.SUPPORTED_TYPES}"
            )
        return detected

    def connect(self, config: dict = None) -> bool:
        if not os.path.exists(self.file_path):
            raise FileNotFoundError(f"File not found: {self.file_path}")
        self._connected = True
        return True

    def fetch_data(self) -> pd.DataFrame:
        if not self._connected:
            self.connect(self.config)

        if self.file_type == "csv":
            self._df = pd.read_csv(self.file_path, encoding=self.encoding)
        elif self.file_type == "excel":
            self._df = pd.read_excel(self.file_path, sheet_name=self.sheet_name)
        elif self.file_type == "json":
            self._df = pd.read_json(self.file_path, encoding=self.encoding)
        else:
            raise ValueError(f"Unsupported file type: {self.file_type}")

        return self._df

    def get_metadata(self) -> SourceMetadata:
        if self._df is None:
            self.fetch_data()

        stat = os.stat(self.file_path)
        return SourceMetadata(
            name=os.path.basename(self.file_path),
            source_type="file",
            row_count=len(self._df),
            column_count=len(self._df.columns),
            columns=list(self._df.columns),
            size_bytes=stat.st_size,
            last_modified=datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
        )

    def get_schema(self) -> SourceSchema:
        if self._df is None:
            self.fetch_data()

        columns = []
        for col in self._df.columns:
            series = self._df[col]
            null_count = int(series.isna().sum())
            try:
                cardinality = int(series.nunique())
            except Exception:
                cardinality = None

            columns.append(
                ColumnSchema(
                    name=col,
                    dtype=str(series.dtype),
                    nullable=null_count > 0,
                    cardinality=cardinality,
                    sample_values=series.dropna().head(3).tolist(),
                )
            )

        return SourceSchema(
            columns=columns,
            row_count=len(self._df),
            inferred_at=datetime.now(tz=timezone.utc).isoformat(),
        )
