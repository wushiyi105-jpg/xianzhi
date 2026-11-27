"""到手价：平台费率与折扣。"""

from __future__ import annotations

from ..catalog import platforms
from ..models import Finding

_RAW = platforms()
RECYCLE_DISCOUNT = float(_RAW["recycle_discount"])

# 平台 -> (费率, 是否回收价, 说明)
PLATFORMS: dict[str, tuple[float, bool, str]] = {
    name: (float(row["fee"]), bool(row["recycle"]), str(row["note"]))
    for name, row in _RAW["platforms"].items()
}


def net_prices(listed_cents: int) -> tuple[dict[str, int], list[Finding]]:
    out: dict[str, int] = {}
    for name, (fee, is_recycle, _) in PLATFORMS.items():
        gross = int(listed_cents * RECYCLE_DISCOUNT) if is_recycle else listed_cents
        out[name] = int(gross * (1 - fee))
    findings: list[Finding] = []
    if out.get("爱回收") and out["爱回收"] < int(listed_cents * 0.85):
        findings.append(
            Finding(
                rule_id="fees.recycle_gap",
                severity="info",
                message="回收价明显低于挂价",
                evidence=f"挂 {listed_cents / 100:.0f}，回收 {out['爱回收'] / 100:.0f}",
                suggestion="急用钱选回收，不急就挂着慢慢卖",
            )
        )
    return out, findings
