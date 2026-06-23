from dataclasses import dataclass

from openlakehouse.core.adapter import LakehouseAdapter
from openlakehouse.core.errors import AdapterNotFoundError
from openlakehouse.identity.resolver import IdentityResolver
from openlakehouse.policy.engine import PolicyEngine


@dataclass
class ServerContext:
    adapters: dict[str, LakehouseAdapter]
    policy_engine: PolicyEngine
    identity_resolver: IdentityResolver

    def get_adapter(self, name: str) -> LakehouseAdapter:
        if name not in self.adapters:
            raise AdapterNotFoundError(name)
        return self.adapters[name]
