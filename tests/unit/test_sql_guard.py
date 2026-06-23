import pytest

from openlakehouse.core.sql_guard import UnsafeQueryError, assert_read_only


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT * FROM sales.orders",
        "with cte as (select 1) select * from cte",
        "SHOW TABLES IN sales",
        "DESCRIBE sales.orders",
        "EXPLAIN SELECT * FROM sales.orders",
    ],
)
def test_allows_read_only_statements(sql):
    assert_read_only(sql)  # should not raise


@pytest.mark.parametrize(
    "sql",
    [
        "DROP TABLE sales.orders",
        "INSERT INTO sales.orders VALUES (1)",
        "DELETE FROM sales.orders",
        "UPDATE sales.orders SET x = 1",
        "ALTER TABLE sales.orders ADD COLUMN y INT",
        "CREATE TABLE foo (x INT)",
    ],
)
def test_rejects_write_and_ddl_statements(sql):
    with pytest.raises(UnsafeQueryError):
        assert_read_only(sql)


def test_rejects_statement_not_starting_with_allowed_prefix():
    with pytest.raises(UnsafeQueryError):
        assert_read_only("MERGE INTO sales.orders USING staging ON true WHEN MATCHED THEN UPDATE SET x = 1")
