"""Unit tests for canonical metadata models."""
import pytest
from openlakehouse.core.canonical.metadata import (
    AWS_NAMESPACE,
    DATABRICKS_NAMESPACE,
    CanonicalCatalog,
    CanonicalColumn,
    CanonicalDataType,
    CanonicalSchema,
    CanonicalTable,
    CanonicalTableSchema,
    CanonicalTableType,
    PlatformNamespaceMapping,
)


def test_canonical_catalog_fields():
    cat = CanonicalCatalog(
        adapter="databricks_prod",
        platform="databricks",
        catalog="sales",
        native_catalog="sales",
    )
    assert cat.adapter == "databricks_prod"
    assert cat.platform == "databricks"
    assert cat.catalog == "sales"
    assert cat.native_catalog == "sales"
    assert cat.comment is None
    assert cat.platform_metadata == {}


def test_canonical_schema_fields():
    schema = CanonicalSchema(
        adapter="aws_prod",
        platform="aws",
        catalog="AwsDataCatalog",
        schema="analytics",
        native_schema="analytics",
    )
    assert schema.schema_name == "analytics"
    assert schema.native_schema == "analytics"
    assert schema.platform == "aws"


def test_canonical_table_default_type():
    table = CanonicalTable(
        adapter="databricks_prod",
        platform="databricks",
        catalog="sales",
        schema="orders",
        table="transactions",
    )
    assert table.table_type == CanonicalTableType.TABLE


def test_canonical_table_view_type():
    table = CanonicalTable(
        adapter="aws_prod",
        platform="aws",
        catalog="AwsDataCatalog",
        schema="analytics",
        table="summary_view",
        table_type=CanonicalTableType.VIEW,
    )
    assert table.table_type == CanonicalTableType.VIEW


def test_canonical_column_all_data_types():
    for dt in CanonicalDataType:
        col = CanonicalColumn(name="col", data_type=dt, raw_type=dt.value)
        assert col.data_type == dt


def test_canonical_table_schema_structure():
    table = CanonicalTable(
        adapter="databricks_prod", platform="databricks",
        catalog="sales", schema="orders", table="transactions",
    )
    col = CanonicalColumn(name="id", data_type=CanonicalDataType.INTEGER, raw_type="int")
    schema = CanonicalTableSchema(table=table, columns=[col], partition_columns=["id"])
    assert schema.table.table == "transactions"
    assert len(schema.columns) == 1
    assert schema.partition_columns == ["id"]


def test_canonical_catalog_serializes_to_json():
    cat = CanonicalCatalog(
        adapter="db", platform="databricks", catalog="main", native_catalog="main"
    )
    data = cat.model_dump()
    assert set(data.keys()) >= {"adapter", "platform", "catalog", "native_catalog", "comment", "platform_metadata"}


def test_platform_namespace_mappings_defined():
    assert DATABRICKS_NAMESPACE.platform == "databricks"
    assert AWS_NAMESPACE.platform == "aws"
    assert "Glue" in AWS_NAMESPACE.catalog_concept
    assert "Unity Catalog" in DATABRICKS_NAMESPACE.catalog_concept


def test_canonical_data_type_values_are_strings():
    for dt in CanonicalDataType:
        assert isinstance(dt.value, str)
        assert dt.value == dt.value.lower()
