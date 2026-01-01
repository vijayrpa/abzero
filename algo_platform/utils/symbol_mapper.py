from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional, Tuple

from algo_platform.models import SymbolKey


@dataclass
class SymbolMapping:
    internal: SymbolKey
    # broker_name -> broker-specific identifier (token, instrument_id etc.)
    broker_ids: Dict[str, str]
    broker_tradingsymbols: Dict[str, str]


class SymbolMapper:
    """
    Provides unified symbol mapping across brokers.
    For broker adapters that require instrument tokens, store them in broker_ids.
    """

    def __init__(self) -> None:
        self._by_key: Dict[str, SymbolMapping] = {}

    def upsert_mapping(
        self,
        internal: SymbolKey,
        broker_name: str,
        broker_id: str,
        broker_tradingsymbol: Optional[str] = None,
    ) -> None:
        k = internal.key()
        if k not in self._by_key:
            self._by_key[k] = SymbolMapping(internal=internal, broker_ids={}, broker_tradingsymbols={})
        self._by_key[k].broker_ids[broker_name] = str(broker_id)
        if broker_tradingsymbol:
            self._by_key[k].broker_tradingsymbols[broker_name] = broker_tradingsymbol

    def get_broker_id(self, internal: SymbolKey, broker_name: str) -> Optional[str]:
        m = self._by_key.get(internal.key())
        if not m:
            return None
        return m.broker_ids.get(broker_name)

    def get_broker_tradingsymbol(self, internal: SymbolKey, broker_name: str) -> Optional[str]:
        m = self._by_key.get(internal.key())
        if not m:
            return None
        return m.broker_tradingsymbols.get(broker_name, internal.tradingsymbol)

