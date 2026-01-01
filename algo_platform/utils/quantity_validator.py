from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from algo_platform.models import SymbolKey
from algo_platform.utils.contract_master import ContractMaster


@dataclass(frozen=True)
class QtyValidation:
    ok: bool
    message: str = ""


class QuantityValidator:
    def __init__(self, contract_master: ContractMaster) -> None:
        self._cm = contract_master

    def validate(self, symbol: SymbolKey, qty: int) -> QtyValidation:
        if qty <= 0:
            return QtyValidation(ok=False, message="Quantity must be > 0")

        # For cash, allow any positive qty.
        if symbol.segment.upper() in ("CASH", "INDEX"):
            return QtyValidation(ok=True)

        lot = self._cm.get_lot_size(symbol)
        if lot is None:
            # If we can't determine lot size, don't hard-block; warn.
            return QtyValidation(ok=True, message="Lot size unknown (contract master not loaded).")
        if lot <= 0:
            return QtyValidation(ok=True)
        if qty % lot != 0:
            return QtyValidation(ok=False, message=f"Invalid qty {qty}; must be multiple of lot size {lot}.")
        return QtyValidation(ok=True)

