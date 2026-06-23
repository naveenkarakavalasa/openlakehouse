from pydantic import BaseModel, ConfigDict, Field


class PolicyRule(BaseModel):
    """One allow or deny rule, matched against adapter/catalog/schema/table."""

    model_config = ConfigDict(populate_by_name=True)

    effect: str = Field(pattern="^(allow|deny)$")
    adapter: str = "*"
    catalog: str = "*"
    schema_name: str = Field(default="*", alias="schema")
    table: str = "*"

    def matches(self, adapter: str, catalog: str, schema: str | None, table: str | None) -> bool:
        def _m(pattern: str, value: str | None) -> bool:
            if pattern == "*":
                return True
            if value is None:
                return False
            return pattern == value

        return (
            _m(self.adapter, adapter)
            and _m(self.catalog, catalog)
            and _m(self.schema_name, schema)
            and _m(self.table, table)
        )


class Role(BaseModel):
    name: str = ""
    rules: list[PolicyRule]
    can_execute_queries: bool = True


class PolicyDocument(BaseModel):
    identities: dict[str, str] = Field(default_factory=dict)
    roles: dict[str, Role] = Field(default_factory=dict)
    default_role: str | None = None
