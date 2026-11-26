"""到手价：平台费率与折扣。"""

from __future__ import annotations

from ..models import Finding

# 平台 -> (费率, 是否回收价, 说明)
PLATFORMS: dict[str, tuple[float, bool, str]] = {
    "闲鱼": (0.0, False, "个人对个人，无手续费"),
    "转转": (0.01, False, "平台抽佣约 1%"),
    "爱回收": (0.0, True, "回收商报价，按挂价约 8 折"),
    "红布林": (0.15, False, "寄卖抽佣约 15%"),
}

RECYCLE_DISCOUNT = 0.80


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
