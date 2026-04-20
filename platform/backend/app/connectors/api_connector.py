from datetime import datetime, timezone
from typing import Optional
import httpx
import pandas as pd
from app.connectors.base import BaseConnector, SourceMetadata, SourceSchema, ColumnSchema


class RestAPIConnector(BaseConnector):
    """Connector for REST APIs via HTTP polling.

    Config keys:
      - url: str — endpoint URL
      - method: str — HTTP method, default "GET"
      - headers: dict — auth headers and custom headers
      - params: dict — query parameters
      - body: dict — request body (for POST)
      - polling_interval_seconds: int — polling interval in seconds (default 300)
      - response_path: str — dot-notation path to data array in response (e.g. "data.items")
      - timeout_seconds: int — request timeout (default 30)
    """

    def __init__(self, config: dict):
        super().__init__(config)
        self.url: str = config["url"]
        self.method: str = config.get("method", "GET").upper()
        self.headers: dict = config.get("headers", {})
        self.params: dict = config.get("params", {})
        self.body: Optional[dict] = config.get("body")
        self.polling_interval: int = config.get("polling_interval_seconds", 300)
        self.response_path: Optional[str] = config.get("response_path")
        self.timeout: int = config.get("timeout_seconds", 30)
        self._last_response: Optional[dict] = None
        self._df: Optional[pd.DataFrame] = None

    def connect(self, config: dict = None) -> bool:
        try:
            with httpx.Client(timeout=self.timeout) as client:
                resp = client.request(
                    method=self.method,
                    url=self.url,
                    headers=self.headers,
                    params=self.params,
                    json=self.body,
                )
                resp.raise_for_status()
                self._connected = True
                return True
        except httpx.HTTPError as e:
            raise ConnectionError(f"Failed to connect to {self.url}: {e}")

    def _extract_data(self, response_json) -> list:
        if not self.response_path:
            if isinstance(response_json, list):
                return response_json
            return [response_json]

        obj = response_json
        for key in self.response_path.split("."):
            if isinstance(obj, dict):
                obj = obj.get(key, {})
            else:
                break

        if isinstance(obj, list):
            return obj
        return [obj]

    def fetch_data(self) -> pd.DataFrame:
        with httpx.Client(timeout=self.timeout) as client:
            resp = client.request(
                method=self.method,
                url=self.url,
                headers=self.headers,
                params=self.params,
                json=self.body,
            )
            resp.raise_for_status()
            self._last_response = resp.json()

        data = self._extract_data(self._last_response)
        self._df = pd.DataFrame(data) if data else pd.DataFrame()
        self._connected = True
        return self._df

    def get_metadata(self) -> SourceMetadata:
        if self._df is None:
            self.fetch_data()

        return SourceMetadata(
            name=self.url,
            source_type="rest_api",
            row_count=len(self._df),
            column_count=len(self._df.columns),
            columns=list(self._df.columns),
            last_modified=datetime.now(tz=timezone.utc).isoformat(),
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
