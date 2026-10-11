"""
PoseAI Nutrition Engine — NutritionValidator
============================================
Validates structured nutrition dicts for impossible or suspicious values.

Rules (all per-serving):
- protein_g    : 0 – 100 g
- carbs_g      : 0 – 200 g
- fat_g        : 0 – 100 g
- calories_kcal: 0 – 1200 kcal
- fiber_g      : 0 – 80 g
- sugar_g      : 0 – 150 g
- sodium_mg    : 0 – 5000 mg
- Calorie consistency: if |declared_kcal - computed_kcal| / declared_kcal > 0.25 → warning
- Impossible combo: protein > 50g AND calories < 50 → error
"""

from __future__ import annotations

from typing import Any


class NutritionValidator:
    """Validate and sanitize a nutrition dict before display or storage."""

    # Per-serving plausible ranges  (min, max)
    _RANGES: dict[str, tuple[float, float]] = {
        "calories_kcal": (0.0, 1200.0),
        "protein_g":     (0.0, 100.0),
        "carbs_g":       (0.0, 200.0),
        "fat_g":         (0.0, 100.0),
        "fiber_g":       (0.0, 80.0),
        "sugar_g":       (0.0, 150.0),
        "sodium_mg":     (0.0, 5000.0),
    }

    def validate(self, nutrition: dict[str, Any]) -> dict[str, Any]:
        """
        Validate a nutrition dict.

        Returns:
            {
              "valid": bool,
              "errors": list[str],       # hard failures — do not display
              "warnings": list[str],     # soft flags — display with caution badge
            }
        """
        errors: list[str] = []
        warnings: list[str] = []

        if not nutrition:
            errors.append("Empty nutrition data.")
            return {"valid": False, "errors": errors, "warnings": warnings}

        # Range checks
        for field, (lo, hi) in self._RANGES.items():
            val = nutrition.get(field)
            if val is None:
                continue
            try:
                fval = float(val)
            except (TypeError, ValueError):
                errors.append(f"{field}: non-numeric value '{val}'")
                continue
            if fval < lo or fval > hi:
                errors.append(
                    f"{field}: value {fval} is outside plausible range [{lo}, {hi}]."
                )

        # Impossible combination: very high protein + near-zero calories
        prot = float(nutrition.get("protein_g") or 0)
        cal  = float(nutrition.get("calories_kcal") or 0)
        if prot > 50.0 and cal < 50.0:
            errors.append(
                f"Impossible values: protein={prot}g but only {cal} kcal "
                f"(protein alone would contribute {prot * 4:.0f} kcal)."
            )

        # Calorie consistency check
        consistency = self.check_calorie_consistency(nutrition)
        if not consistency["consistent"]:
            warnings.append(
                f"Calorie inconsistency: label says {consistency['actual_kcal']} kcal "
                f"but macro calculation estimates ~{consistency['expected_kcal']:.0f} kcal "
                f"({consistency['delta_pct']:.0f}% difference). "
                f"Data may require verification."
            )

        return {
            "valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings,
        }

    def check_calorie_consistency(self, nutrition: dict[str, Any]) -> dict[str, Any]:
        """
        Check if declared calories roughly match macro computation.
        Returns consistent=True if within 25% tolerance or not enough data to check.
        """
        cal   = float(nutrition.get("calories_kcal") or 0)
        prot  = float(nutrition.get("protein_g")     or 0)
        carbs = float(nutrition.get("carbs_g")       or 0)
        fat   = float(nutrition.get("fat_g")         or 0)

        if cal <= 0:
            return {"consistent": True, "expected_kcal": 0.0, "actual_kcal": 0, "delta_pct": 0.0}

        expected = (prot * 4.0) + (carbs * 4.0) + (fat * 9.0)
        delta_pct = abs(cal - expected) / cal * 100.0

        return {
            "consistent": delta_pct <= 25.0,
            "expected_kcal": round(expected, 1),
            "actual_kcal": int(cal),
            "delta_pct": round(delta_pct, 1),
        }

    def sanitize(self, nutrition: dict[str, Any]) -> dict[str, Any]:
        """
        Return a copy of nutrition with None values replaced by 0 and
        values clamped within plausible ranges.
        Does NOT round or alter values that are already valid.
        """
        result: dict[str, Any] = dict(nutrition)
        for field, (lo, hi) in self._RANGES.items():
            raw = result.get(field)
            if raw is None:
                result[field] = 0 if field == "sodium_mg" else 0.0
            else:
                try:
                    fval = float(raw)
                    clamped = max(lo, min(hi, fval))
                    # Preserve int for calories / sodium
                    if field in ("calories_kcal", "sodium_mg"):
                        result[field] = int(round(clamped))
                    else:
                        result[field] = round(clamped, 1)
                except (TypeError, ValueError):
                    result[field] = 0 if field == "sodium_mg" else 0.0
        return result


# ── Cross-source conflict detection ───────────────────────────────────

    # Severity thresholds on the relative delta of each compared field.
    _CONFLICT_PCT = {"low": 10.0, "medium": 25.0, "high": 40.0}

    # Fields compared between two sources (order = report order).
    _COMPARE_FIELDS: tuple[str, ...] = (
        "calories_kcal", "protein_g", "carbs_g", "fat_g", "sugar_g", "sodium_mg",
    )

    def compare_sources(
        self,
        source_a: dict[str, Any] | None,
        source_b: dict[str, Any] | None,
        label_a: str = "source_a",
        label_b: str = "source_b",
    ) -> dict[str, Any]:
        """
        Compare two nutrition dicts and report how far apart they are.

        Used when independent sources describe the same item — e.g. a barcode
        database lookup vs. a nutrition-label OCR read — so the UI can surface
        a conflict badge instead of silently trusting one.

        Severity (based on the largest relative delta across compared fields).
        Each delta is measured relative to source_a, the reference reading.
          < 10%          -> "none"    (has_conflict False)
          10% - < 25%    -> "low"
          25% - < 40%    -> "medium"
          >= 40%         -> "high"

        Returns:
            {
              "has_conflict": bool,
              "severity": str,                          # none|low|medium|high
              "fields": list[str],                      # conflicting fields
              "delta_pct": dict[str, float],            # per conflicting field
              "higher_source": str | None,              # label of the higher reading
              "compared_fields": list[str],             # fields actually compared
              "message": str,
            }
        """
        result: dict[str, Any] = {
            "has_conflict": False,
            "severity": "none",
            "fields": [],
            "delta_pct": {},
            "higher_source": None,
            "compared_fields": [],
            "message": "No conflict detected.",
        }

        if not source_a or not source_b:
            result["message"] = "Insufficient data to compare sources."
            return result

        delta_pct: dict[str, float] = {}
        compared: list[str] = []
        higher_a = 0
        higher_b = 0

        for field in self._COMPARE_FIELDS:
            a_raw = source_a.get(field)
            b_raw = source_b.get(field)
            if a_raw is None or b_raw is None:
                continue
            try:
                a_val = float(a_raw)
                b_val = float(b_raw)
            except (TypeError, ValueError):
                continue

            # Skip fields that are effectively absent in both sources.
            if a_val <= 0 and b_val <= 0:
                continue

            compared.append(field)
            # Delta is relative to source_a — the reference reading (e.g. the
            # printed label). Falls back to source_b when source_a is zero.
            base = abs(a_val) if a_val != 0 else abs(b_val)
            if base <= 0:
                continue

            delta = abs(a_val - b_val) / base * 100.0
            delta_pct[field] = round(delta, 1)
            if a_val > b_val:
                higher_a += 1
            elif b_val > a_val:
                higher_b += 1

        if not delta_pct:
            result["compared_fields"] = compared
            result["message"] = "Not enough overlapping fields to compare sources."
            return result

        result["compared_fields"] = compared

        # Only report fields that actually conflict at or above the "low" floor.
        conflicting = {
            f: d for f, d in delta_pct.items()
            if d >= self._CONFLICT_PCT["low"]
        }

        if not conflicting:
            result["message"] = "Sources agree within tolerance."
            return result

        worst = max(conflicting.values())
        if worst >= self._CONFLICT_PCT["high"]:
            severity = "high"
        elif worst >= self._CONFLICT_PCT["medium"]:
            severity = "medium"
        else:
            severity = "low"

        result.update({
            "has_conflict": True,
            "severity": severity,
            "fields": list(conflicting.keys()),
            "delta_pct": conflicting,
            "higher_source": (
                label_a if higher_a > higher_b
                else label_b if higher_b > higher_a
                else None
            ),
            "message": (
                f"Nutrition sources disagree by up to {worst:.0f}% on "
                f"{', '.join(conflicting.keys())}."
            ),
        })
        return result


# Module-level singleton for convenience
_validator = NutritionValidator()


def validate_nutrition(nutrition: dict[str, Any]) -> dict[str, Any]:
    return _validator.validate(nutrition)


def sanitize_nutrition(nutrition: dict[str, Any]) -> dict[str, Any]:
    return _validator.sanitize(nutrition)


def check_calorie_consistency(nutrition: dict[str, Any]) -> dict[str, Any]:
    return _validator.check_calorie_consistency(nutrition)


def compare_nutrition_sources(
    source_a: dict[str, Any] | None,
    source_b: dict[str, Any] | None,
    label_a: str = "source_a",
    label_b: str = "source_b",
) -> dict[str, Any]:
    """Compare two independent nutrition readings and report any conflict."""
    return _validator.compare_sources(source_a, source_b, label_a, label_b)
