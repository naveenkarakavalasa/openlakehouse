from abc import ABC, abstractmethod

from openlakehouse.core.models import (
    CatalogRef,
    QueryResult,
    SchemaRef,
    TableSchema,
    TableSummary,
)


class LakehouseAdapter(ABC):
    """A pluggable connector to one lakehouse platform instance.

    One adapter instance == one configured connection (e.g. one Databricks
    workspace, or one AWS account/region). Multiple adapter instances of the
    same type can be active simultaneously (e.g. two Databricks workspaces).
    """

    name: str
    platform: str  # short identifier: "databricks", "aws", etc.

    @abstractmethod
    def list_catalogs(self) -> list[CatalogRef]:
        """Return all catalogs visible to the configured credentials."""

    @abstractmethod
    def list_schemas(self, catalog: str) -> list[SchemaRef]:
        """Return all schemas (databases) within a catalog."""

    @abstractmethod
    def list_tables(self, catalog: str, schema: str) -> list[TableSummary]:
        """Return all tables/views within a schema."""

    @abstractmethod
    def describe_table(self, catalog: str, schema: str, table: str) -> TableSchema:
        """Return full column/type/partition metadata for one table."""

    @abstractmethod
    def execute_query(
        self,
        sql: str,
        *,
        catalog: str | None = None,
        schema: str | None = None,
        max_rows: int = 1000,
        page_token: str | None = None,
    ) -> QueryResult:
        """Execute a read-only SQL query and return one page of results.

        Implementations MUST enforce read-only semantics (reject DDL/DML
        where the platform doesn't already guarantee it) and MUST cap
        result size at max_rows, setting `truncated=True` and a
        `next_page_token` if more rows are available rather than ever
        materializing an unbounded result set in memory.
        """

    def health_check(self) -> bool:
        """Cheap connectivity check; default impl tries list_catalogs()."""
        try:
            self.list_catalogs()
            return True
        except Exception:
            return False
