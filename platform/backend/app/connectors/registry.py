from typing import Type
from app.connectors.base import BaseConnector


class ConnectorRegistry:
    """Registry for connector plugins. Add new connector types here."""

    _registry: dict[str, Type[BaseConnector]] = {}

    @classmethod
    def register(cls, source_type: str, connector_class: Type[BaseConnector]) -> None:
        cls._registry[source_type] = connector_class

    @classmethod
    def get(cls, source_type: str) -> Type[BaseConnector]:
        connector_class = cls._registry.get(source_type)
        if not connector_class:
            raise ValueError(
                f"No connector registered for source type: '{source_type}'. "
                f"Registered types: {list(cls._registry.keys())}"
            )
        return connector_class

    @classmethod
    def create(cls, source_type: str, config: dict) -> BaseConnector:
        """Factory method: create and return a connector instance."""
        connector_class = cls.get(source_type)
        return connector_class(config)

    @classmethod
    def list_types(cls) -> list[str]:
        return list(cls._registry.keys())


def _register_defaults() -> None:
    from app.connectors.file_connector import FileConnector
    from app.connectors.api_connector import RestAPIConnector

    ConnectorRegistry.register("file", FileConnector)
    ConnectorRegistry.register("rest_api", RestAPIConnector)


_register_defaults()
