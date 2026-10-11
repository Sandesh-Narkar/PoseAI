from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any, Optional

import cv2
import numpy as np

logger = logging.getLogger("poseai.nutrition.food_recognition")


# ---------------------------------------------------------------------------
# 1. Name normalization
# ---------------------------------------------------------------------------

# Colloquial / misspelled / concatenated forms -> canonical vocabulary name.
_NAME_ALIASES: dict[str, str] = {
    "vadapav": "vada pav",
    "vada pao": "vada pav",
    "wada pav": "vada pav",
    "wada pao": "vada pav",
    "wadapav": "vada pav",
    "batata vada pav": "vada pav",
    "bombay burger": "vada pav",
    "batatavada": "batata vada",
    "bhajiya": "pakora",
    "bhaji": "pakora",
    "bhel": "bhel puri",
    "bhelpuri": "bhel puri",
    "sevpuri": "sev puri",
    "panipuri": "pani puri",
    "golgappa": "pani puri",
    "puchka": "pani puri",
    "pavbhaji": "pav bhaji",
    "misalpav": "misal pav",
    "idly": "idli",
    "dose": "dosa",
    "masala dose": "masala dosa",
    "meduvada": "medu vada",
    "medhu vada": "medu vada",
    "vadai": "medu vada",
    "chana masala": "chole",
    "biriyani": "biryani",
    "fries": "french fries",
    "chips": "french fries",
    "shahi paneer": "paneer butter masala",
    "murgh makhani": "butter chicken",
    "chapathi": "roti chapati",
    "phulka": "roti chapati",
    "soda": "cold drink",
    "coke": "cold drink",
    "pepsi": "cold drink",
}


def name_key(text: str) -> str:
    """Collapse a food name to a comparison key: lowercase, letters/digits only."""
    return re.sub(r"[^a-z0-9]+", "", str(text or "").lower())


def normalize_food_name(text: str) -> str:
    """
    Normalize a user/AI/OCR supplied food name to a canonical form.

    ``"Vadapav"`` / ``"WADA  PAO"`` / ``"BhelPuri"`` all resolve to a clean,
    space-separated canonical name so database + alias lookups succeed
    regardless of spelling or spacing.
    """
    raw = " ".join(str(text or "").strip().lower().split())
    raw = re.sub(r"[^a-z0-9 ]+", " ", raw).strip()
    if not raw:
        return ""

    if raw in _NAME_ALIASES:
        return _NAME_ALIASES[raw]

    collapsed = name_key(raw)
    if collapsed in _NAME_ALIASES:
        return _NAME_ALIASES[collapsed]

    return raw


# ---------------------------------------------------------------------------
# 2. Visual evidence extraction
# ---------------------------------------------------------------------------

# Evidence keys are the shared vocabulary between signal extraction,
# the candidate vocabulary, and the scoring function.
EVIDENCE_KEYS: tuple[str, ...] = (
    "layered_sandwich", "compact_snack", "round_flat", "bowl_container",
    "scattered_small", "many_grains", "liquid_surface",
    "high_texture", "smooth_uniform", "fried_golden",
    "bun_bread", "chutney_red", "chutney_green", "gravy",
    "dark_chunks", "meat_chunk", "white_rice", "yellow_dal",
    "green_leafy", "cheese_melt",
)

# Evidence is considered "present" at or above this strength.
EVIDENCE_PRESENT = 0.34

EVIDENCE_LABELS: dict[str, str] = {
    "layered_sandwich": "layered bread-and-filling structure",
    "compact_snack": "compact single-piece snack shape",
    "round_flat": "round flat disc shape",
    "bowl_container": "served in a bowl/plate with several components",
    "scattered_small": "several small scattered pieces",
    "many_grains": "grain/rice texture",
    "liquid_surface": "liquid surface with highlights",
    "high_texture": "crispy/busy texture with many edges",
    "smooth_uniform": "smooth uniform surface",
    "fried_golden": "golden fried/batter coating",
    "bun_bread": "bread or bun present",
    "chutney_red": "red chutney/sauce/spice",
    "chutney_green": "green chutney/herbs",
    "gravy": "gravy or sauce pool",
    "dark_chunks": "dark chunks or pieces",
    "meat_chunk": "distinct meat-like pieces",
    "white_rice": "white/pale base",
    "yellow_dal": "yellow lentil/oil tone",
    "green_leafy": "green leafy matter",
    "cheese_melt": "melted cheese/topping layer",
}


@dataclass
class FoodEvidence:
    """Measurable visual signals extracted from a single image."""

    strengths: dict[str, float] = field(default_factory=dict)
    quality: dict[str, Any] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)

    def present(self, threshold: float = EVIDENCE_PRESENT) -> set[str]:
        return {k for k, v in self.strengths.items() if v >= threshold}

    def strength(self, key: str) -> float:
        return float(self.strengths.get(key, 0.0))

    def describe(self, limit: int = 6) -> list[str]:
        """Human-readable evidence bullets for the UI, strongest first."""
        present = sorted(self.present(), key=lambda k: -self.strength(k))
        return [EVIDENCE_LABELS.get(k, k) for k in present[:limit]]


def _ratio(mask: np.ndarray, total: float) -> float:
    return float(np.count_nonzero(mask)) / total if total > 0 else 0.0


def _detect_layered_structure(img: np.ndarray, bbox: tuple[int, int, int, int]) -> float:
    """
    Detect a bread -> filling -> bread band pattern (burger / vada pav / sandwich).

    Splits the dominant blob's bounding box into horizontal bands and measures
    how far the middle band sits from the outer bands while the outer bands
    agree with each other. That A-B-A pattern is a strong sandwich signature and
    is exactly the evidence that was missing when a Vada Pav was read as curry.
    """
    try:
        x, y, bw, bh = bbox
        if bw < 20 or bh < 30:
            return 0.0
        bands = 5
        band_h = max(1, bh // bands)
        means: list[np.ndarray] = []
        for i in range(bands):
            y0 = y + i * band_h
            y1 = min(y + (i + 1) * band_h, img.shape[0])
            if y1 <= y0:
                continue
            strip = img[y0:y1, x:x + bw]
            means.append(strip.reshape(-1, 3).mean(axis=0))
        if len(means) < 3:
            return 0.0

        outer = (means[0] + means[-1]) / 2.0
        middle = means[len(means) // 2]
        outer_gap = float(np.linalg.norm(means[0] - means[-1]))
        mid_gap = float(np.linalg.norm(outer - middle))
        if mid_gap < 22.0:
            return 0.0
        similarity = 1.0 - min(outer_gap / 60.0, 1.0)
        contrast = min(mid_gap / 90.0, 1.0)
        return float(np.clip(similarity * contrast, 0.0, 1.0))
    except Exception:
        return 0.0


def extract_evidence(img: np.ndarray) -> FoodEvidence:
    """
    Extract candidate-independent visual evidence from an image.

    Returns strengths in 0..1 per evidence key plus an image-quality report.
    All computation is deterministic OpenCV — no model required.
    """
    ev = FoodEvidence()
    if img is None or getattr(img, "size", 0) == 0:
        ev.quality = {"acceptable": False, "reason": "No image data."}
        return ev

    try:
        h, w = img.shape[:2]
        total = float(h * w)
        hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

        # ── Image quality ────────────────────────────────────────────
        blur_var = float(cv2.Laplacian(gray, cv2.CV_64F).var())
        brightness = float(np.mean(gray))
        ev.quality = {
            "width": w,
            "height": h,
            "blur_variance": round(blur_var, 1),
            "brightness": round(brightness, 1),
            "acceptable": blur_var >= 40.0 and 25.0 <= brightness <= 245.0,
        }
        if blur_var < 40.0:
            ev.quality["reason"] = "Image appears blurry or out of focus."
        elif brightness < 25.0:
            ev.quality["reason"] = "Image is too dark to analyse."
        elif brightness > 245.0:
            ev.quality["reason"] = "Image is over-exposed."
        if min(h, w) < 120:
            ev.quality["acceptable"] = False
            ev.quality["reason"] = "Image resolution is too low to identify food."

        # ── Colour region ratios ─────────────────────────────────────
        yellow = cv2.inRange(hsv, np.array([18, 45, 45]), np.array([35, 255, 255]))
        green = cv2.inRange(hsv, np.array([36, 40, 40]), np.array([85, 255, 255]))
        red = cv2.bitwise_or(
            cv2.inRange(hsv, np.array([0, 55, 55]), np.array([14, 255, 255])),
            cv2.inRange(hsv, np.array([168, 55, 55]), np.array([180, 255, 255])),
        )
        white = cv2.inRange(hsv, np.array([0, 0, 185]), np.array([180, 42, 255]))
        brown = cv2.inRange(hsv, np.array([10, 40, 50]), np.array([25, 200, 200]))
        golden = cv2.inRange(hsv, np.array([14, 70, 70]), np.array([30, 255, 255]))
        dark = cv2.inRange(hsv, np.array([0, 0, 0]), np.array([180, 255, 95]))

        y_ratio, g_ratio = _ratio(yellow, total), _ratio(green, total)
        r_ratio, w_ratio = _ratio(red, total), _ratio(white, total)
        b_ratio, gold_ratio = _ratio(brown, total), _ratio(golden, total)
        dark_ratio = _ratio(dark, total)

        # ── Texture / edges ──────────────────────────────────────────
        edges = cv2.Canny(gray, 60, 150)
        edge_density = _ratio(edges, total)

        lap = cv2.Laplacian(gray, cv2.CV_64F)
        tile = 32
        tile_stds: list[float] = []
        for y0 in range(0, h - tile + 1, tile):
            for x0 in range(0, w - tile + 1, tile):
                tile_stds.append(float(np.std(lap[y0:y0 + tile, x0:x0 + tile])))
        uniform_ratio = (
            sum(1 for s in tile_stds if s < 6.0) / len(tile_stds)
            if tile_stds else 0.0
        )

        # ── Shape / blob analysis ────────────────────────────────────
        # Food foreground = anything that is not the pale background plate.
        bg = cv2.inRange(hsv, np.array([0, 0, 150]), np.array([180, 45, 255]))
        fg = cv2.bitwise_not(bg)
        fg = cv2.morphologyEx(fg, cv2.MORPH_OPEN, np.ones((5, 5), np.uint8))
        contours, _ = cv2.findContours(fg, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        contours = [c for c in contours if cv2.contourArea(c) > 0.002 * total]

        compact_shape = round_flat = scattered = layered = 0.0
        food_area_ratio = 0.0

        if contours:
            main = max(contours, key=cv2.contourArea)
            area = cv2.contourArea(main)
            food_area_ratio = area / total
            hull_area = cv2.contourArea(cv2.convexHull(main)) or 1.0
            compact_shape = float(np.clip(area / hull_area, 0.0, 1.0))

            peri = cv2.arcLength(main, True) or 1.0
            circularity = float(np.clip(4.0 * np.pi * area / (peri * peri), 0.0, 1.0))
            x, y, bw, bh = cv2.boundingRect(main)
            aspect = bw / float(bh or 1)
            round_flat = float(np.clip(circularity * (1.0 if aspect > 0.8 else 0.5), 0.0, 1.0))

            big = [c for c in contours if cv2.contourArea(c) >= 0.004 * total]
            if len(big) >= 4:
                scattered = float(np.clip(len(big) / 8.0, 0.0, 1.0))

            layered = _detect_layered_structure(img, (x, y, bw, bh))

        # Build the strengths mapping and assign it to the evidence object.
        ev.strengths = {
            "layered_sandwich": layered,
            "compact_snack": compact_shape if food_area_ratio > 0.04 else 0.0,
            "round_flat": round_flat,
            "bowl_container": float(np.clip(min(food_area_ratio * 1.6, 1.0), 0.0, 1.0)),
            "scattered_small": scattered,
            "many_grains": float(np.clip(edge_density * 6.0 * (1.0 - uniform_ratio), 0.0, 1.0)),
            "liquid_surface": float(np.clip(uniform_ratio * (0.4 + w_ratio), 0.0, 1.0)),
            "high_texture": float(np.clip(edge_density * 8.0, 0.0, 1.0)),
            "smooth_uniform": float(np.clip(uniform_ratio, 0.0, 1.0)),
            "fried_golden": float(np.clip(gold_ratio * 2.6, 0.0, 1.0)),
            "bun_bread": float(np.clip(b_ratio * 2.0 + w_ratio * 0.25, 0.0, 1.0)),
            "chutney_red": float(np.clip(r_ratio * 2.4, 0.0, 1.0)),
            "chutney_green": float(np.clip(g_ratio * 2.6, 0.0, 1.0)),
            "gravy": float(np.clip(
                (uniform_ratio * 0.6 + dark_ratio * 0.7) * (1.0 - min(edge_density * 6.0, 1.0))
                * (1.0 - min(layered * 1.6, 0.9)),
                0.0, 1.0)),
            "dark_chunks": float(np.clip(dark_ratio * 2.2, 0.0, 1.0)),
            "meat_chunk": float(np.clip(dark_ratio * 1.4 * (1.0 - min(layered * 1.5, 0.9)), 0.0, 1.0)),
            "white_rice": float(np.clip((w_ratio - r_ratio * 0.5) * 1.3, 0.0, 1.0)),
            "yellow_dal": float(np.clip(y_ratio * 2.2, 0.0, 1.0)),
            "green_leafy": float(np.clip(g_ratio * 2.2, 0.0, 1.0)),
            "cheese_melt": float(np.clip(
                y_ratio * 1.2 * (1.0 - min(edge_density * 5.0, 1.0)), 0.0, 1.0)),
        }
        ev.notes.append(
            f"ratios y={y_ratio:.2f} g={g_ratio:.2f} r={r_ratio:.2f} "
            f"w={w_ratio:.2f} b={b_ratio:.2f}; edge_density={edge_density:.3f}; "
            f"food_area={food_area_ratio:.2f}"
        )

    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("Evidence extraction failed: %s", exc)
        ev.quality = {"acceptable": False, "reason": "Could not analyse the image."}

    return ev

# ---------------------------------------------------------------------------
# 4. Scoring: positive evidence, missing requirements (negative evidence),
#    forbidden signals (hard reject), and structure validation.
# ---------------------------------------------------------------------------


def _score_candidate(cand: FoodCandidate, ev: FoodEvidence) -> dict:
    """Score one candidate. Returns score/conf mapping + rejected flag."""
    positive = 0.0
    weight_sum = 0.0
    missing: list[str] = []
    forbidden_hit: str | None = None

    for key, weight in cand.requires.items():
        weight_sum += weight
        s = ev.strength(key)
        positive += s * weight
        if s < 0.34:
            missing.append(key)

    coverage = (positive / weight_sum) if weight_sum else 0.0

    # Structure compatibility gate.
    structure_bonus = 0.10 if cand.structure == _dominant_structure(ev) else 0.0

    # Forbidden signals: strong presence of something the food must not have.
    penalty = 0.0
    for fkey, thresh, w, reason in cand.forbids:
        s = ev.strength(fkey)
        if s >= thresh:
            penalty += w
            forbidden_hit = reason
            break

    score = coverage * 0.9 + structure_bonus - penalty

    # Hard reject: incompatible with evidence.
    rejected = penalty >= 0.45 or score < 0.05

    # Calibrated confidence: conservative mapping that keeps ambiguous
    # images in low/medium bands (never inherit an AI model's tone).
    if rejected:
        conf = min(score, 0.12)
    else:
        conf = 0.30 + score * 0.62 - 0.10 * len(missing) / max(len(cand.requires), 1)
        conf = float(min(max(conf, 0.05), 0.93))

    return {
        "candidate": cand,
        "score": round(float(score), 3),
        "confidence": round(float(conf), 3),
        "missing": missing,
        "forbidden_hit": forbidden_hit,
        "rejected": bool(rejected),
    }


def _dominant_structure(ev: FoodEvidence) -> str:
    """Pick the most-supported serving structure from evidence strengths."""
    struct_scores = {
        "sandwich_stack": ev.strength("layered_sandwich") * 1.2
        + ev.strength("bun_bread") * 0.5,
        "bowl_single": ev.strength("bowl_container") * 0.8
        + ev.strength("gravy") * 0.6,
        "curry_bowl": ev.strength("gravy") * 1.1
        + ev.strength("dark_chunks") * 0.5,
        "rice_mound": ev.strength("many_grains") * 1.1
        + ev.strength("white_rice") * 0.5,
        "flatbread": ev.strength("round_flat") * 1.1,
        "snack_piece": ev.strength("compact_snack") * 0.9
        + ev.strength("fried_golden") * 0.4,
        "chutney_plate": ev.strength("chutney_red") * 0.7
        + ev.strength("chutney_green") * 0.7,
    }
    return max(struct_scores, key=lambda k: struct_scores[k])


def _confidence_band(conf: float) -> str:
    if conf >= 0.90:
        return "high"
    if conf >= 0.75:
        return "medium"
    if conf >= 0.50:
        return "low"
    return "unknown"


# ---------------------------------------------------------------------------
# 5. Recognition entry point — evidence -> ranked candidates -> decision
# ---------------------------------------------------------------------------

def _gemini_candidates() -> list[dict]:
    """Ask Gemini for *candidate names only* (never nutrition/confidence)."""
    try:
        from nutrition.gemini_vision import identify_food_with_gemini
    except Exception:
        return []
    return []


def rank_candidates(
    ev: FoodEvidence,
    ai_names: list[str] | None = None,
    hint: str | None = None,
) -> dict:
    """Score every vocabulary candidate; fuse optional AI/hint names as a
    small bonus (never as the decision). Returns ranked + rejected lists."""
    scored = [_score_candidate(c, ev) for c in _CANDIDATES]

    norm_ai = {normalize_food_name(n) for n in (ai_names or []) if n}
    norm_hint = normalize_food_name(hint) if hint else ""
    for s in scored:
        cand = s["candidate"]
        keys = {normalize_food_name(cand.display_name)}
        keys |= {normalize_food_name(a) for a in cand.aliases}
        keys.add(normalize_food_name(cand.food_id.replace("_", " ")))
        bonus = 0.0
        if norm_hint and norm_hint in keys:
            bonus += 0.12
        if keys & norm_ai:
            bonus += 0.08
        if bonus:
            s["score"] = round(s["score"] + bonus, 3)
            if not s["rejected"]:
                s["confidence"] = round(min(s["confidence"] + bonus * 0.5, 0.93), 3)

    scored.sort(key=lambda s: s["confidence"], reverse=True)
    accepted = [s for s in scored if not s["rejected"]]
    rejected = [s for s in scored if s["rejected"]]
    return {"accepted": accepted, "rejected": rejected, "evidence": ev}


def recognize_food(
    img,
    hint: str | None = None,
    ai_names: list[str] | None = None,
) -> dict:
    """Full pipeline: quality -> evidence -> candidates -> decision dict.

    Returned dict matches the MASTER FIX response contract (status,
    category, primary_prediction, alternatives, visual_evidence,
    rejected_candidates, nutrition=None, requires_confirmation).
    """
    ev = extract_evidence(img)
    if not ev.quality.get("acceptable", True):
        return {
            "status": "needs_confirmation",
            "category": "unknown",
            "primary_prediction": None,
            "alternatives": [],
            "visual_evidence": [],
            "rejected_candidates": [],
            "nutrition": None,
            "requires_confirmation": True,
            "quality_issue": ev.quality.get("reason", "Poor image quality."),
            "food_confidence": 0.0,
            "confidence_band": "unknown",
        }

    ranked = rank_candidates(ev, ai_names=ai_names, hint=hint)
    accepted = ranked["accepted"]
    rejected = ranked["rejected"]

    top = accepted[:3]
    primary = top[0] if top else None

    def _entry(s: dict) -> dict:
        cand = s["candidate"]
        return {
            "food_id": cand.food_id,
            "name": cand.display_name,
            "confidence": s["confidence"],
            "band": _confidence_band(s["confidence"]),
            "broad_category": cand.broad_category,
            "requires_confirmation": s["confidence"] < 0.90,
        }

    primary_entry = _entry(primary) if primary else None
    alternatives = [_entry(s) for s in top[1:3]]

    rejected_out = [
        {
            "name": s["candidate"].display_name,
            "reason": s.get("forbidden_hit")
            or f"Missing expected evidence: {', '.join(s.get('missing', [])[:3]) or 'multiple signals'}",
        }
        for s in rejected[:6]
    ]

    if primary is None:
        status, band, conf = "needs_confirmation", "unknown", 0.0
        category = "unknown"
        needs_confirm = True
    else:
        conf = primary["confidence"]
        band = _confidence_band(conf)
        category = primary["candidate"].broad_category
        needs_confirm = conf < 0.90
        status = "identified" if conf >= 0.90 else "needs_confirmation"

    return {
        "status": status,
        "category": category,
        "primary_prediction": primary_entry,
        "alternatives": alternatives,
        "visual_evidence": ev.describe(),
        "evidence_strengths": {k: round(v, 3) for k, v in ev.strengths.items()},
        "rejected_candidates": rejected_out,
        "nutrition": None,
        "requires_confirmation": needs_confirm,
        "food_confidence": round(conf, 3) if primary else 0.0,
        "confidence_band": band,
    }


def candidate_food_ids() -> list[str]:
    return [c.food_id for c in _CANDIDATES]


def lookup_candidate(choice: str) -> FoodCandidate | None:
    """Resolve a user-confirmed name/id/alias to a vocabulary candidate."""
    norm = normalize_food_name(choice)
    for cand in _CANDIDATES:
        pool = {normalize_food_name(cand.display_name),
                normalize_food_name(cand.food_id.replace("_", " "))}
        pool |= {normalize_food_name(a) for a in cand.aliases}
        if norm in pool:
            return cand
    # Fall back to food_db search for anything outside the CV vocabulary.
    try:
        from nutrition.food_db import search_foods
        hits = search_foods(choice, limit=1)
        if hits:
            return FoodCandidate(
                hits[0]["id"], hits[0]["name"], "user_confirmed",
                {}, [], "user_confirmed", (choice,),
            )
    except Exception:
        pass
    return None

# ---------------------------------------------------------------------------
# 3. Candidate vocabulary  (recognition candidates only — never nutrition)
# ---------------------------------------------------------------------------

@dataclass
class FoodCandidate:
    food_id: str
    display_name: str
    broad_category: str
    requires: dict
    forbids: list
    structure: str
    aliases: tuple = ()


CAT_STREET = "indian_street_food"
CAT_CURRY = "indian_curry"
CAT_RICE = "rice_dish"
CAT_BREAD = "bread"
CAT_FRIED = "fried_snack"
CAT_BREAKFAST = "indian_breakfast"
CAT_DAL = "dal_lentil"
CAT_FRUIT = "fruit"
CAT_VEG = "vegetable"
CAT_PROTEIN = "protein_grilled"
CAT_PACKED = "packaged_snack"
CAT_MIXED = "mixed_meal"
CAT_SHAKE = "beverage_shake"

_CANDIDATES: list = [
    FoodCandidate("roti_chapati", "Roti / Chapati", CAT_BREAD,
                  {"round_flat": 0.55, "bun_bread": 0.25, "smooth_uniform": 0.2},
                  [("gravy", 0.45, 0.45, "no curry/gravy expected around plain roti"),
                   ("layered_sandwich", 0.4, 0.5, "roti is a single flat disc, not layered"),
                   ("many_grains", 0.4, 0.4, "no rice grains expected")],
                  "flatbread", ("roti", "chapati", "phulka", "fulka", "flatbread")),
    FoodCandidate("plain_naan", "Butter / Plain Naan", CAT_BREAD,
                  {"round_flat": 0.5, "bun_bread": 0.3, "smooth_uniform": 0.2},
                  [("gravy", 0.5, 0.4, "naan served plain, not floating in gravy"),
                   ("layered_sandwich", 0.4, 0.5, "naan is a single flat piece")],
                  "flatbread", ("naan", "butter naan", "garlic naan")),
    FoodCandidate("paratha_aloo", "Aloo Paratha", CAT_BREAD,
                  {"round_flat": 0.45, "fried_golden": 0.35, "bun_bread": 0.2},
                  [("gravy", 0.5, 0.4, "paratha is pan-fried flatbread, not curry"),
                   ("layered_sandwich", 0.45, 0.45, "paratha is flat, not a sandwich stack")],
                  "flatbread", ("paratha", "aloo paratha", "stuffed paratha")),
    FoodCandidate("steamed_rice", "Steamed White Rice", CAT_RICE,
                  {"white_rice": 0.55, "many_grains": 0.45},
                  [("layered_sandwich", 0.35, 0.55, "rice has no bread layers"),
                   ("gravy", 0.55, 0.35, "plain rice has no thick gravy pool"),
                   ("fried_golden", 0.5, 0.4, "steamed rice is not fried")],
                  "rice_mound", ("rice", "white rice", "steamed rice", "chawal")),
    FoodCandidate("brown_rice", "Brown Rice", CAT_RICE,
                  {"white_rice": 0.4, "many_grains": 0.45, "bun_bread": 0.15},
                  [("layered_sandwich", 0.35, 0.55, "rice has no bread layers"),
                   ("gravy", 0.55, 0.35, "plain rice has no thick gravy pool")],
                  "rice_mound", ("brown rice",)),
    FoodCandidate("biryani_chicken", "Chicken Biryani", CAT_RICE,
                  {"many_grains": 0.4, "yellow_dal": 0.3, "dark_chunks": 0.2,
                   "meat_chunk": 0.1},
                  [("layered_sandwich", 0.35, 0.55, "biryani is layered rice, not a sandwich"),
                   ("bun_bread", 0.5, 0.4, "biryani contains no bun or bread")],
                  "rice_mound", ("biryani", "biriyani", "chicken biryani")),
    FoodCandidate("biryani_veg", "Veg Biryani / Pulao", CAT_RICE,
                  {"many_grains": 0.45, "yellow_dal": 0.3, "green_leafy": 0.1,
                   "chutney_green": 0.15},
                  [("layered_sandwich", 0.35, 0.55, "pulao is rice, not a sandwich"),
                   ("bun_bread", 0.5, 0.4, "pulao contains no bun or bread"),
                   ("meat_chunk", 0.4, 0.45, "veg pulao has no meat pieces")],
                  "rice_mound", ("veg biryani", "pulao", "fried rice")),
    FoodCandidate("dal_tadka", "Dal Tadka / Yellow Dal", CAT_DAL,
                  {"yellow_dal": 0.55, "liquid_surface": 0.25, "smooth_uniform": 0.2},
                  [("layered_sandwich", 0.35, 0.55, "dal is served in a bowl, not in bread"),
                   ("many_grains", 0.45, 0.4, "dal tadka has no distinct rice grains"),
                   ("fried_golden", 0.5, 0.35, "dal is not a fried snack")],
                  "curry_bowl", ("dal", "dal tadka", "yellow dal", "tadka dal")),
    FoodCandidate("paneer_curry", "Paneer Butter Masala", CAT_CURRY,
                  {"gravy": 0.45, "chutney_red": 0.25, "smooth_uniform": 0.3},
                  [("layered_sandwich", 0.35, 0.55, "paneer curry is a bowl curry, not a sandwich"),
                   ("many_grains", 0.45, 0.4, "paneer curry has no rice grains"),
                   ("meat_chunk", 0.4, 0.4, "paneer curry is vegetarian")],
                  "curry_bowl", ("paneer", "shahi paneer", "paneer butter masala")),
    FoodCandidate("paneer_raw_grilled", "Grilled Paneer Cubes", CAT_PROTEIN,
                  {"white_rice": 0.35, "compact_snack": 0.35, "high_texture": 0.3},
                  [("gravy", 0.5, 0.45, "grilled paneer has no gravy pool"),
                   ("layered_sandwich", 0.4, 0.5, "paneer cubes are not layered bread")],
                  "protein_pieces", ("grilled paneer", "paneer tikka", "paneer cubes")),
    FoodCandidate("chicken_curry", "Chicken Curry / Tariwala Chicken", CAT_CURRY,
                  {"gravy": 0.4, "dark_chunks": 0.3, "meat_chunk": 0.2, "chutney_red": 0.1},
                  [("layered_sandwich", 0.4, 0.6, "curry is served in a bowl, not layered in bread"),
                   ("many_grains", 0.45, 0.45, "chicken curry has no rice grains"),
                   ("bun_bread", 0.5, 0.5, "no bun or bread expected in a curry bowl photo")],
                  "curry_bowl", ("chicken curry", "chicken gravy", "murgh curry",
                                 "tariwala chicken")),
    FoodCandidate("butter_chicken", "Butter Chicken", CAT_CURRY,
                  {"gravy": 0.45, "chutney_red": 0.25, "smooth_uniform": 0.3},
                  [("layered_sandwich", 0.4, 0.6, "butter chicken is a bowl curry, not a sandwich"),
                   ("many_grains", 0.45, 0.45, "butter chicken has no rice grains"),
                   ("bun_bread", 0.5, 0.45, "no bun expected in a butter chicken bowl")],
                  "curry_bowl", ("butter chicken", "murgh makhani", "chicken makhani")),
    FoodCandidate("palak_paneer", "Palak Paneer", CAT_CURRY,
                  {"green_leafy": 0.45, "chutney_green": 0.35, "gravy": 0.2},
                  [("layered_sandwich", 0.35, 0.55, "palak paneer is a bowl curry, not a sandwich"),
                   ("many_grains", 0.45, 0.4, "palak paneer has no rice grains"),
                   ("meat_chunk", 0.4, 0.4, "palak paneer is vegetarian")],
                  "curry_bowl", ("palak paneer", "saag paneer", "spinach paneer")),
    FoodCandidate("indian_thali", "Complete Indian Thali", CAT_MIXED,
                  {"bowl_container": 0.4, "many_grains": 0.2, "white_rice": 0.15,
                   "yellow_dal": 0.15, "green_leafy": 0.1},
                  [("layered_sandwich", 0.45, 0.45, "a thali is a multi-item platter, not one sandwich"),
                   ("compact_snack", 0.7, 0.35, "a thali is a large spread, not one compact snack")],
                  "thali_platter", ("thali", "veg thali", "indian thali")),
    FoodCandidate("idli_sambar", "Idli with Sambar", CAT_BREAKFAST,
                  {"round_flat": 0.4, "white_rice": 0.35, "smooth_uniform": 0.25},
                  [("layered_sandwich", 0.4, 0.55, "idli are steamed cakes, not a sandwich"),
                   ("fried_golden", 0.45, 0.45, "idli is steamed, never fried golden"),
                   ("meat_chunk", 0.4, 0.4, "idli sambar is vegetarian")],
                  "idli_steamed", ("idli", "idly", "idli sambar")),
    FoodCandidate("dosa_masala", "Masala Dosa", CAT_BREAKFAST,
                  {"round_flat": 0.4, "fried_golden": 0.35, "yellow_dal": 0.25},
                  [("layered_sandwich", 0.45, 0.5, "dosa is a thin crepe roll, not a sandwich stack"),
                   ("gravy", 0.5, 0.4, "dosa is a crepe, not a gravy bowl"),
                   ("meat_chunk", 0.4, 0.4, "masala dosa filling is potato, not meat")],
                  "dosa_crepe", ("dosa", "dose", "masala dosa", "masala dose")),
    FoodCandidate("poha", "Poha", CAT_BREAKFAST,
                  {"yellow_dal": 0.4, "high_texture": 0.35, "many_grains": 0.25},
                  [("layered_sandwich", 0.35, 0.55, "poha is flattened-rice flakes, not a sandwich"),
                   ("gravy", 0.5, 0.45, "poha has no gravy"),
                   ("bun_bread", 0.5, 0.45, "poha has no bread")],
                  "poha_flakes", ("poha", "kanda poha", "flattened rice")),
    FoodCandidate("vada_pav", "Vada Pav", CAT_STREET,
                  {"layered_sandwich": 0.45, "bun_bread": 0.3, "fried_golden": 0.15,
                   "chutney_red": 0.1},
                  [("gravy", 0.4, 0.55, "vada pav is dry in bread, not served in a gravy bowl"),
                   ("many_grains", 0.4, 0.5, "vada pav has no rice"),
                   ("meat_chunk", 0.35, 0.55, "vada pav filling is potato, not meat")],
                  "sandwich_stack", ("vada pav", "vadapav", "vada pao", "wada pav",
                                     "wada pao", "bombay burger", "batata vada pav")),
    FoodCandidate("samosa", "Samosa (Potato)", CAT_FRIED,
                  {"compact_snack": 0.4, "fried_golden": 0.4, "high_texture": 0.2},
                  [("layered_sandwich", 0.45, 0.5, "samosa is a single fried pastry, not layered bread"),
                   ("gravy", 0.5, 0.5, "samosa is dry-fried, not in gravy"),
                   ("many_grains", 0.4, 0.45, "samosa has no rice grains")],
                  "fried_triangle", ("samosa", "singara", "aloo samosa")),
    FoodCandidate("pav_bhaji", "Pav Bhaji", CAT_STREET,
                  {"bun_bread": 0.3, "chutney_red": 0.3, "high_texture": 0.2,
                   "bowl_container": 0.2},
                  [("many_grains", 0.4, 0.5, "pav bhaji has no rice"),
                   ("meat_chunk", 0.35, 0.5, "pav bhaji is vegetarian"),
                   ("layered_sandwich", 0.5, 0.35, "bhaji is mashed curry beside pav, not a stacked sandwich")],
                  "pav_with_bhaji", ("pav bhaji", "pavbhaji", "bhaji pav")),
    FoodCandidate("misal_pav", "Misal Pav", CAT_STREET,
                  {"gravy": 0.3, "chutney_red": 0.3, "high_texture": 0.2, "bun_bread": 0.2},
                  [("many_grains", 0.4, 0.5, "misal has no rice"),
                   ("meat_chunk", 0.35, 0.5, "misal is vegetarian"),
                   ("smooth_uniform", 0.55, 0.3, "misal is chunky sprouts curry, not a smooth surface")],
                  "misal_bowl", ("misal", "misal pav", "misalpav", "kolhapuri misal")),
    FoodCandidate("boiled_eggs", "Boiled Eggs (Whole)", CAT_PROTEIN,
                  {"round_flat": 0.35, "white_rice": 0.35, "smooth_uniform": 0.3},
                  [("gravy", 0.5, 0.45, "boiled eggs served plain have no gravy"),
                   ("layered_sandwich", 0.4, 0.55, "boiled eggs are not layered bread"),
                   ("many_grains", 0.45, 0.45, "no rice grains expected")],
                  "egg_round", ("boiled egg", "boiled eggs", "anda", "egg")),
    FoodCandidate("egg_whites", "Egg Whites (Cooked)", CAT_PROTEIN,
                  {"white_rice": 0.45, "smooth_uniform": 0.35, "round_flat": 0.2},
                  [("gravy", 0.5, 0.45, "egg whites served plain have no gravy"),
                   ("layered_sandwich", 0.4, 0.55, "egg whites are not layered bread")],
                  "egg_round", ("egg white", "egg whites")),
    FoodCandidate("chicken_breast_grilled", "Grilled Chicken Breast", CAT_PROTEIN,
                  {"meat_chunk": 0.4, "dark_chunks": 0.3, "fried_golden": 0.2,
                   "compact_snack": 0.1},
                  [("layered_sandwich", 0.4, 0.55, "grilled chicken is a fillet, not layered bread"),
                   ("gravy", 0.5, 0.45, "grilled breast has no gravy pool"),
                   ("many_grains", 0.45, 0.45, "no rice grains expected")],
                  "protein_pieces", ("grilled chicken", "chicken breast", "tandoori chicken")),
    FoodCandidate("oatmeal_porridge", "Oatmeal Porridge", CAT_BREAKFAST,
                  {"smooth_uniform": 0.4, "liquid_surface": 0.3, "white_rice": 0.3},
                  [("layered_sandwich", 0.4, 0.55, "oatmeal is a bowl porridge, not a sandwich"),
                   ("fried_golden", 0.45, 0.5, "oatmeal is never fried"),
                   ("meat_chunk", 0.35, 0.5, "oatmeal is vegetarian")],
                  "upma_porridge", ("oatmeal", "oats", "porridge", "daliya")),
    FoodCandidate("whey_protein_shake", "Whey Protein Shake", CAT_SHAKE,
                  {"liquid_surface": 0.5, "smooth_uniform": 0.35, "white_rice": 0.15},
                  [("layered_sandwich", 0.35, 0.6, "a shake is a drink, not a sandwich"),
                   ("many_grains", 0.4, 0.5, "a shake has no grains"),
                   ("fried_golden", 0.45, 0.5, "a shake is never fried")],
                  "shake_glass", ("whey", "protein shake", "protein smoothie")),
    FoodCandidate("greek_yogurt", "Greek Yogurt / Hung Curd", CAT_BREAKFAST,
                  {"white_rice": 0.45, "smooth_uniform": 0.4, "liquid_surface": 0.15},
                  [("layered_sandwich", 0.4, 0.55, "yogurt is a bowl, not a sandwich"),
                   ("fried_golden", 0.45, 0.5, "yogurt is never fried"),
                   ("meat_chunk", 0.35, 0.5, "yogurt is vegetarian")],
                  "curd_bowl", ("yogurt", "greek yogurt", "curd", "dahi", "hung curd")),
    FoodCandidate("poha_flakes", "Poha (Flattened Rice)", CAT_BREAKFAST,
                  {"yellow_dal": 0.35, "high_texture": 0.3, "smooth_uniform": 0.25},
                  [("layered_sandwich", 0.35, 0.55, "poha is flattened-rice flakes, not a sandwich"),
                   ("gravy", 0.5, 0.45, "poha has no gravy"),
                   ("bun_bread", 0.5, 0.45, "poha has no bread")],
                  "poha_flakes", ("poha", "kanda poha", "flattened rice")),
    FoodCandidate("upma", "Rava Upma", CAT_BREAKFAST,
                  {"yellow_dal": 0.35, "high_texture": 0.35, "smooth_uniform": 0.3},
                  [("layered_sandwich", 0.35, 0.55, "upma is a semolina porridge, not a sandwich"),
                   ("gravy", 0.5, 0.45, "upma has no gravy"),
                   ("bun_bread", 0.5, 0.45, "upma has no bread")],
                  "upma_porridge", ("upma", "rava upma", "sooji upma")),
    FoodCandidate("dal_tadka_plain", "Dal (Plain Bowl)", CAT_DAL,
                  {"yellow_dal": 0.5, "liquid_surface": 0.3, "smooth_uniform": 0.2},
                  [("layered_sandwich", 0.35, 0.55, "dal is a bowl curry, not a sandwich"),
                   ("many_grains", 0.45, 0.4, "plain dal has no rice grains"),
                   ("fried_golden", 0.5, 0.35, "dal is not fried")],
                  "curry_bowl", ("dal", "plain dal")),
    FoodCandidate("dal_makhani", "Dal Makhani", CAT_DAL,
                  {"gravy": 0.45, "dark_chunks": 0.25, "smooth_uniform": 0.3},
                  [("layered_sandwich", 0.35, 0.55, "dal makhani is a bowl curry, not a sandwich"),
                   ("many_grains", 0.45, 0.4, "dal makhani has no rice grains"),
                   ("meat_chunk", 0.4, 0.4, "dal makhani is vegetarian")],
                  "curry_bowl", ("dal makhani", "kali dal", "black dal")),
    FoodCandidate("chole_curry", "Chole / Chickpea Curry", CAT_CURRY,
                  {"gravy": 0.45, "dark_chunks": 0.35, "high_texture": 0.2},
                  [("layered_sandwich", 0.35, 0.55, "chole is a bowl curry, not a sandwich"),
                   ("many_grains", 0.45, 0.4, "chole has no rice grains"),
                   ("meat_chunk", 0.4, 0.4, "chole is vegetarian")],
                  "curry_bowl", ("chole", "chana masala", "chickpea curry")),
    FoodCandidate("rajma_masala", "Rajma / Kidney Bean Curry", CAT_CURRY,
                  {"gravy": 0.45, "dark_chunks": 0.35, "chutney_red": 0.2},
                  [("layered_sandwich", 0.35, 0.55, "rajma is a bowl curry, not a sandwich"),
                   ("many_grains", 0.45, 0.4, "rajma has no rice grains"),
                   ("meat_chunk", 0.4, 0.4, "rajma is vegetarian")],
                  "curry_bowl", ("rajma", "kidney bean curry")),
]
