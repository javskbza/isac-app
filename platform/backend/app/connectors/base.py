from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional
import pandas as pd


@dataclass
class ColumnSchema:
    name: str
    dtype: str
    nullable: bool
    cardinality: Optional[int] = None
    sample_values: list = field(default_factory=list)


@dataclass
class SourceSchema:
    columns: list[ColumnSchema]
    row_count: int
    inferred_at: str  # ISO timestamp


@dataclass
class SourceMetadata:
    name: str
    source_type: str
    row_count: int
    column_count: int
    columns: list[str]
    size_bytes: Optional[int] = None
    last_modified: Optional[str] = None


class BaseConnector(ABC):
    """Abstract base class for all data source connectors.

    All v1/v2/v3 connectors must implement this interface.
    """

    def __init__(self, config: dict):
        self.config = config
        self._connected = False

    @abstractmethod
    def connect(self, config: dict) -> bool:
        """Establish connection to the data source. Returns True on success."""

    @abstractmethod
    def get_metadata(self) -> SourceMetadata:
        """Return high-level metadata about the data source."""

    @abstractmethod
    def fetch_data(self) -> pd.DataFrame:
        """Fetch and return all data as a pandas DataFrame."""

    @abstractmethod
    def get_schema(self) -> SourceSchema:
        """Infer and return schema information."""

    def disconnect(self) -> None:
        """Optional cleanup. Override if needed."""
        self._connected = False

    def is_connected(self) -> bool:
        return self._connected
