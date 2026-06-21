# ADR-0003 — Battery and supercap are separated

## Status

Accepted.

## Date

2026-06-20

## Context

Простая игровая модель могла бы иметь одну шкалу energy.

Для QIKI это создаёт ложную причинность: заряженная батарея начинает автоматически означать право на boost, high-power scan, NBL packet, active field or emergency burn.

## Decision

Battery и supercap разделяются.

Battery отвечает за длительность жизни.

Supercap отвечает за краткие пиковые действия.

Peak action requires SoC_cap, PDU allowance and thermal clearance.

## Rejected alternatives

Одна общая energy bar для всех действий.

Battery SoC as peak permission.

Boost allowed only because battery is charged.

Supercap as decorative statistic.

## Consequences

ORION должен показывать battery и supercap отдельно.

Команды пикового класса должны проверять SoC_cap.

Отказы должны иметь reason_codes: CAP_LOW, CAP_HOT, PDU_PEAK_DENIED, THERMAL_BLOCK.

Энергетика QIKI остаётся телесной, а не абстрактной.

## Related requirements

REQ-POWER-*; REQ-THERMAL-*; REQ-CMD-*.

## Related viewpoints

VP-05 Power / Thermal; VP-09 Command Safety; VP-10 Operator Evidence.

## Related interfaces

IF-PDU-POWER-001; IF-POWER-TELEM-001; IF-THERMAL-TELEM-001.

## Related documents

`01_BODY_CANON.md`; `04_CALCULATION_FRAME.md`; `05_ENGINEERING_RATIONALE.md`; `06_INTERFACE_CONTROL.md`.

## Review notes

This ADR belongs to QIKI Body v0.2.2 Documentation Package.

This ADR is documentation-only.

It does not claim runtime implementation.

Implemented requires evidence.

Verified requires evidence and verification.
