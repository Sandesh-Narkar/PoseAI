"""
core/ui_layout.py
-------------------
Professional desktop UI compositor for the PoseAI AI Fitness Trainer.

Builds a single combined OpenCV (BGR) frame in a clean, premium,
"commercial fitness app" visual language (think Apple Fitness / Samsung
Health / modern gym software) rather than a debug/OpenCV-demo look:

    * A white top header bar (branding, exercise name, timer, set counter)
    * A large, card-framed camera viewport (~75% width) showing the live
      webcam feed with a soft rounded border - the primary visual focus
    * A right-hand "Exercise Guide" sidebar (~25% width) laid out as
      clearly separated rounded sections: guide image, name, metadata,
      instructions
    * A bottom row of four equally sized, evenly spaced, identical-height
      rounded cards:
        1. Exercise + Reps + Progress bar
        2. Stage + Angle + FPS
        3. Feedback (colored message box)
        4. Workout Statistics (elapsed time, completed sets, completion %)

It also provides three full-screen overlay states used by the app's
session flow:
    * render_set_complete()      - shown between sets of an exercise
    * render_workout_complete()  - shown once all sets of an exercise finish
    * render_session_summary()   - the Session Summary Dashboard, shown
                                    when the user quits (Q). Offers
                                    ENTER (back to exercise selection)
                                    and ESC (exit PoseAI) as on-screen
                                    button prompts.

LAYOUT SYSTEM
-------------
The whole layout is resolution independent and expressed as explicit
(x, y, width, height) rectangles, computed by `_calculate_layout()`
(which internally calls `_calculate_header_rect`,
`_calculate_camera_rect`, `_calculate_sidebar_rect`,
`_calculate_bottom_rect` and `_calculate_bottom_cards` /
`_calculate_card_dimensions`) and stored as:

    header_rect, camera_rect, sidebar_rect, bottom_rect,
    exercise_rect, metrics_rect, feedback_rect, stats_rect, card_rects

Layout is recalculated only when the window size changes (constructor
or `set_window_size()`) - never on a per-frame basis - and every
render-time cache (static panels, camera-fit cache, sidebar cache) is
invalidated at that point.

PERFORMANCE
-----------
Static, per-frame-identical drawing is cached and reused via
`.copy()` instead of being redrawn every frame:

    * `_header_base`        - brand/border, everything but the exercise
                               name / timer / set-counter chip
    * `_camera_card_base`   - camera card border/background (video is
                               resized once via a cached fit and pasted
                               on top each frame - never resized twice)
    * `_card_base_panel`    - shared rounded rect background/border
                               reused for all four (identically sized)
                               bottom cards
    * `_sidebar_cache`      - the *entire* sidebar panel, keyed by
                               (exercise name, active instruction index)
                               since sidebar content never depends on
                               per-frame values like reps/fps/timer

Text sizes for repeated strings are memoized in `_text_size_cache` via
`_get_text_size()` instead of calling `cv2.getTextSize()` every frame.

All exercise reference information (name, guide image, target
muscles, difficulty, goal reps, sets and instructions) is sourced from
core/exercise_data.py - nothing exercise-specific is hardcoded here,
so new exercises added to that registry are picked up automatically
with no changes required in this file.
"""

from __future__ import annotations

import os
from typing import Dict, List, Optional, Sequence, Tuple

import cv2
import numpy as np

from core.exercise_data import ExerciseInfo, get_exercise_info_by_name


# A rectangle is always expressed as (x, y, width, height) in pixels,
# relative to the full compositor canvas.
Rect = Tuple[int, int, int, int]

# A camera "fit" result: (new_width, new_height, x_offset, y_offset)
# describing the resized frame size and its centered position within
# the target area.
CameraFit = Tuple[int, int, int, int]


# ---------------------------------------------------------------------------
# Visual theme constants
# ---------------------------------------------------------------------------

class Theme:
    """
    Central color / font palette so the whole UI stays consistent.

    Colors are stored as OpenCV BGR tuples. The design palette (given
    in hex/RGB) maps to BGR as follows:

        Background        #FFFFFF -> white app background
        Cards             #F5F7FA -> very light gray card background
        Primary Accent    #2563EB -> blue
        Secondary Accent  #22C55E -> green
        Warning           #F59E0B -> orange
        Error             #EF4444 -> red
        Text              #1F2937 -> dark gray
        Borders           #E5E7EB -> light gray
    """

    # --- Core surface colors -------------------------------------------------
    BACKGROUND = (255, 255, 255)       # page/app background - pure white
    CARD_BG = (250, 247, 245)          # #F5F7FA - light card surface
    CARD_BG_ALT = (245, 241, 238)      # #EEF1F5 - nested/inset surface (tracks, wells)
    HEADER_BG = (255, 255, 255)        # header shares the white background

    # The live camera feed is the one intentionally "dark" surface in the
    # UI (like a video player), so it reads clearly against the light theme.
    # This is also the color used to fill any empty letterbox space
    # around the camera frame.
    CAMERA_BG = (38, 38, 38)

    # --- Accents ---------------------------------------------------------
    ACCENT = (235, 99, 37)             # #2563EB - primary blue
    ACCENT_SOFT = (254, 234, 219)      # #DBEAFE - soft blue tint (badges/buttons)
    ACCENT_DARK = (170, 70, 20)        # pressed/darker blue for outlines

    SUCCESS = (94, 197, 34)            # #22C55E - green
    SUCCESS_SOFT = (222, 245, 220)     # soft green tint
    WARNING = (11, 158, 245)           # #F59E0B - orange
    WARNING_SOFT = (210, 235, 253)     # soft orange tint
    DANGER = (68, 68, 239)             # #EF4444 - red
    DANGER_SOFT = (220, 220, 253)      # soft red tint

    # --- Text --------------------------------------------------------------
    TEXT_PRIMARY = (55, 41, 31)        # #1F2937 - dark gray, main text
    TEXT_SECONDARY = (99, 85, 75)      # #4B5563 - secondary gray
    TEXT_MUTED = (175, 163, 156)       # #9CA3AF - muted gray
    TEXT_ON_DARK = (240, 240, 240)     # near-white, for text on the camera surface
    TEXT_ON_ACCENT = (255, 255, 255)   # white text on solid accent fills

    BORDER = (235, 231, 229)           # #E5E7EB - light gray hairline border

    FONT = cv2.FONT_HERSHEY_SIMPLEX
    FONT_BOLD = cv2.FONT_HERSHEY_DUPLEX

    # --- Text style scales (title / section header / label / value /
    #     instruction / feedback) so text roles stay visually consistent
    #     wherever they're used.
    SCALE_TITLE = 0.62
    SCALE_SECTION_HEADER = 0.38
    SCALE_LABEL = 0.42
    SCALE_VALUE = 0.55
    SCALE_INSTRUCTION = 0.44
    SCALE_FEEDBACK = 0.55


# ---------------------------------------------------------------------------
# Low level drawing helpers (stateless, free functions)
# ---------------------------------------------------------------------------

def _put_text(
    image: np.ndarray,
    text: str,
    origin: Tuple[int, int],
    font_scale: float = 0.6,
    color: Tuple[int, int, int] = Theme.TEXT_PRIMARY,
    thickness: int = 1,
    font: int = Theme.FONT,
) -> None:
    """Draw a single line of text. Thin wrapper kept for consistency."""
    cv2.putText(image, text, origin, font, font_scale, color, thickness, cv2.LINE_AA)


def _draw_rect(
    image: np.ndarray,
    top_left: Tuple[int, int],
    bottom_right: Tuple[int, int],
    color: Tuple[int, int, int],
    filled: bool = True,
    thickness: int = 1,
    radius: int = 0,
) -> None:
    """Draw a filled or outlined rectangle, optionally rounded."""
    if radius <= 0:
        cv2.rectangle(image, top_left, bottom_right, color,
                       -1 if filled else thickness)
        return

    x1, y1 = top_left
    x2, y2 = bottom_right
    r = min(radius, (x2 - x1) // 2, (y2 - y1) // 2)
    fill = -1 if filled else thickness

    cv2.rectangle(image, (x1 + r, y1), (x2 - r, y2), color, fill)
    cv2.rectangle(image, (x1, y1 + r), (x2, y2 - r), color, fill)
    for cx, cy in [(x1 + r, y1 + r), (x2 - r, y1 + r),
                   (x1 + r, y2 - r), (x2 - r, y2 - r)]:
        cv2.circle(image, (cx, cy), r, color, fill)


def _wrap_text(text: str, max_chars: int) -> List[str]:
    """Greedy word-wrap a string into lines no longer than max_chars."""
    words = text.split()
    lines: List[str] = []
    current = ""

    for word in words:
        candidate = f"{current} {word}".strip()
        if len(candidate) <= max_chars:
            current = candidate
        else:
            if current:
                lines.append(current)
            current = word

    if current:
        lines.append(current)

    return lines or [""]


def _overlay_image(background: np.ndarray, foreground: np.ndarray, x: int, y: int) -> None:
    """Paste `foreground` onto `background` at (x, y), clipped to bounds."""
    bg_h, bg_w = background.shape[:2]
    fg_h, fg_w = foreground.shape[:2]

    if x >= bg_w or y >= bg_h or x + fg_w <= 0 or y + fg_h <= 0:
        return

    x_start = max(0, x)
    y_start = max(0, y)
    x_end = min(x + fg_w, bg_w)
    y_end = min(y + fg_h, bg_h)

    fg_x_start = x_start - x
    fg_y_start = y_start - y
    fg_x_end = fg_x_start + (x_end - x_start)
    fg_y_end = fg_y_start + (y_end - y_start)

    if x_end <= x_start or y_end <= y_start:
        return

    background[y_start:y_end, x_start:x_end] = foreground[fg_y_start:fg_y_end, fg_x_start:fg_x_end]


def _compute_fit_dimensions(
    src_width: int, src_height: int, max_width: int, max_height: int, max_upscale: float = 1.0
) -> Tuple[int, int]:
    """
    Compute the largest (width, height) that a (src_width, src_height)
    source can be scaled to so it fits entirely within
    (max_width, max_height) while preserving its aspect ratio (never
    stretched). `max_upscale` caps how far the source may be enlarged
    beyond its native size (1.0 = never enlarge, only shrink or keep
    as-is) so quality is preserved when the source is smaller than the
    available area.
    """
    if src_width <= 0 or src_height <= 0 or max_width <= 0 or max_height <= 0:
        return max(1, src_width), max(1, src_height)

    scale = min(max_width / src_width, max_height / src_height)
    scale = min(scale, max_upscale)
    scale = max(scale, 1e-6)

    new_w = max(1, int(round(src_width * scale)))
    new_h = max(1, int(round(src_height * scale)))
    return new_w, new_h


# ---------------------------------------------------------------------------
# Guide image loading (with in-memory caching) - unchanged loading logic
# ---------------------------------------------------------------------------

class GuideImageLoader:
    """
    Loads exercise guide images from disk (assets/exercise_guides/) and
    caches both the raw decoded image and resized results so repeated
    render() calls don't hit the filesystem or re-run cv2.resize every
    frame.

    Image filenames are never hardcoded here - they come from each
    exercise's "image" field in core/exercise_data.EXERCISE_DATA, so
    this loader works automatically for any exercise added to that
    registry.
    """

    # Guide images are allowed to be upscaled slightly to fill the
    # card, but never enlarged so far that visible quality is lost.
    DEFAULT_MAX_UPSCALE = 1.15

    def __init__(self, guides_dir: str = "assets/exercise_guides"):
        self._guides_dir = guides_dir
        # filename -> decoded raw image (or None if missing/unreadable)
        self._raw_cache: Dict[str, Optional[np.ndarray]] = {}
        # (filename, max_width, max_height) -> resized image (or None)
        self._resized_cache: Dict[Tuple[str, int, int], Optional[np.ndarray]] = {}

    def _resolve_path(self, image_filename: str) -> Optional[str]:
        """
        Resolve the on-disk path for a guide image filename. Returns
        None (without raising) if the file doesn't exist, so callers
        can gracefully fall back to a placeholder.
        """
        if not image_filename:
            return None

        candidate = os.path.join(self._guides_dir, image_filename)
        if os.path.isfile(candidate):
            return candidate

        return None

    def load_guide_image(self, image_filename: str) -> Optional[np.ndarray]:
        """
        Decode and return the raw BGR guide image for `image_filename`,
        or None if it doesn't exist / can't be read. The decoded image
        is cached per filename so disk I/O and decoding only ever
        happen once per exercise, regardless of how many frames are
        rendered or at what target size.
        """
        if image_filename in self._raw_cache:
            return self._raw_cache[image_filename]

        raw: Optional[np.ndarray] = None
        path = self._resolve_path(image_filename)
        if path is not None:
            decoded = cv2.imread(path, cv2.IMREAD_COLOR)
            if decoded is not None and decoded.size > 0:
                raw = decoded

        self._raw_cache[image_filename] = raw
        return raw

    def resize_guide_image(
        self,
        image: np.ndarray,
        max_width: int,
        max_height: int,
        max_upscale: float = DEFAULT_MAX_UPSCALE,
    ) -> np.ndarray:
        """
        Resize `image` to fit within (max_width, max_height), always
        preserving its original aspect ratio (never stretched). If the
        image is smaller than the available space it may be scaled up
        slightly (bounded by `max_upscale`) but never enlarged so much
        that it visibly degrades in quality.
        """
        height, width = image.shape[:2]
        new_w, new_h = _compute_fit_dimensions(width, height, max_width, max_height, max_upscale)

        if new_w == width and new_h == height:
            return image

        interpolation = cv2.INTER_AREA if (new_w <= width and new_h <= height) else cv2.INTER_LINEAR
        return cv2.resize(image, (new_w, new_h), interpolation=interpolation)

    def get(self, image_filename: str, max_width: int, max_height: int) -> Optional[np.ndarray]:
        """
        Convenience: load + resize combined, fully cached per
        (filename, max_width, max_height). Recalculated only when the
        requested size actually changes (e.g. on window resize).
        """
        cache_key = (image_filename, max_width, max_height)
        if cache_key in self._resized_cache:
            return self._resized_cache[cache_key]

        raw = self.load_guide_image(image_filename)
        resized = self.resize_guide_image(raw, max_width, max_height) if raw is not None else None

        self._resized_cache[cache_key] = resized
        return resized


# ---------------------------------------------------------------------------
# Main layout compositor
# ---------------------------------------------------------------------------

class UILayout:
    """
    Builds the complete PoseAI desktop UI frame.

    Usage:
        layout = UILayout(window_width=1280, window_height=800)
        combined_frame = layout.render(
            camera_frame=frame,
            workout_name="Crossover Toe Touches",
            workout_data={"reps": 4, "stage": "CENTER", "feedback": "Good Cross", "angle": 172.4},
            fps=28.3,
            elapsed_time=95.0,
            current_set=1,
            total_sets=3,
        )
        cv2.imshow("PoseAI", combined_frame)
    """

    # --- Layout proportions (fractions of the full window) ---------------
    HEADER_HEIGHT_RATIO = 0.10
    BOTTOM_HEIGHT_RATIO = 0.26
    CAMERA_WIDTH_RATIO = 0.75       # camera stays the primary visual focus (~75% width)
    NUM_BOTTOM_CARDS = 4            # exercise/reps, stage/fps, feedback, workout stats

    # --- Professional spacing constants (single source of truth for
    #     every margin/padding/gap used throughout the UI) -----------------
    WINDOW_PADDING = 16     # outer margin between the window edge and header/camera/sidebar
    CARD_PADDING = 18       # internal padding inside every card's content area
    SECTION_SPACING = 14    # vertical gap between stacked sidebar sections
    CARD_SPACING = 10       # gap left around/between adjacent bottom cards
    TEXT_SPACING = 6        # extra vertical gap between text lines/instructions

    # Circle radius used for the numbered instruction markers.
    INSTRUCTION_CIRCLE_RADIUS = 9

    def __init__(
        self,
        window_width: int = 1280,
        window_height: int = 800,
        guides_dir: str = "assets/exercise_guides",
    ):
        self.window_width = window_width
        self.window_height = window_height
        self._guide_loader = GuideImageLoader(guides_dir)

        # --- Render-time caches --------------------------------------
        # Camera fit results, keyed by (src_w, src_h, target_w, target_h).
        self._camera_fit_cache: Dict[Tuple[int, int, int, int], CameraFit] = {}
        # Memoized cv2.getTextSize() results, keyed by (text, font, scale, thickness).
        self._text_size_cache: Dict[Tuple[str, int, float, int], Tuple[int, int]] = {}
        # Fully rendered sidebar panels, keyed by (exercise name, active instruction index).
        self._sidebar_cache: Dict[Tuple[str, int], np.ndarray] = {}
        # Static base panels, rebuilt only when their rect/size changes.
        self._header_base: Optional[np.ndarray] = None
        self._camera_card_base: Optional[np.ndarray] = None
        self._camera_inner_offset: Tuple[int, int] = (0, 0)
        self._camera_inner_size: Tuple[int, int] = (1, 1)
        self._card_base_panel: Optional[np.ndarray] = None

        self._calculate_layout()

    # ------------------------------------------------------------------
    # Layout calculation (only ever runs when the window size changes)
    # ------------------------------------------------------------------

    def set_window_size(self, window_width: int, window_height: int) -> None:
        """
        Update the target window size and recompute every layout
        rectangle + invalidate render caches. Call this if the app's
        window is resized at runtime - no other code changes are
        required, every section adapts automatically.
        """
        if window_width == self.window_width and window_height == self.window_height:
            return  # nothing changed - avoid pointless recalculation

        self.window_width = window_width
        self.window_height = window_height
        self._calculate_layout()

    def _calculate_header_rect(self) -> Rect:
        """Top branding/timer/set-counter bar, full width."""
        height = int(self.window_height * self.HEADER_HEIGHT_RATIO)
        return (0, 0, self.window_width, height)

    def _calculate_bottom_rect(self, header_height: int) -> Rect:
        """Full-width bottom row that contains all four info cards."""
        height = int(self.window_height * self.BOTTOM_HEIGHT_RATIO)
        y = self.window_height - height
        return (0, y, self.window_width, height)

    def _calculate_camera_rect(self, header_height: int, middle_height: int) -> Rect:
        """Live webcam viewport - the primary visual focus (~70-75% width)."""
        camera_width = int(self.window_width * self.CAMERA_WIDTH_RATIO)
        return (0, header_height, camera_width, middle_height)

    def _calculate_sidebar_rect(self, header_height: int, middle_height: int, camera_width: int) -> Rect:
        """Exercise Guide sidebar - remaining ~25-30% width."""
        sidebar_width = self.window_width - camera_width
        return (camera_width, header_height, sidebar_width, middle_height)

    def _calculate_card_dimensions(self, index: int, count: int, area_rect: Rect) -> Rect:
        """
        Compute the rect for the `index`-th of `count` equally sized
        cards tiled left-to-right within `area_rect`. All cards share
        the exact same width and height so they stay aligned and
        identical regardless of window size.
        """
        area_x, area_y, area_width, area_height = area_rect
        card_width = area_width // count
        return (area_x + index * card_width, area_y, card_width, area_height)

    def _calculate_bottom_cards(self, bottom_rect: Rect, count: int) -> List[Rect]:
        """Four equally sized, evenly spaced, identical-height bottom cards."""
        return [self._calculate_card_dimensions(i, count, bottom_rect) for i in range(count)]

    def _calculate_layout(self) -> None:
        """
        Compute every top-level UI section as an explicit rectangle and
        store it. This is the single place layout math happens - it is
        only ever invoked from the constructor or `set_window_size()`,
        never per-frame, and every render-time cache is invalidated
        here so stale cached panels are never reused after a resize.
        """
        header_rect = self._calculate_header_rect()
        header_height = header_rect[3]

        bottom_rect = self._calculate_bottom_rect(header_height)
        middle_height = self.window_height - header_height - bottom_rect[3]

        camera_rect = self._calculate_camera_rect(header_height, middle_height)
        sidebar_rect = self._calculate_sidebar_rect(header_height, middle_height, camera_rect[2])

        card_rects = self._calculate_bottom_cards(bottom_rect, self.NUM_BOTTOM_CARDS)

        self.header_rect: Rect = header_rect
        self.camera_rect: Rect = camera_rect
        self.sidebar_rect: Rect = sidebar_rect
        self.bottom_rect: Rect = bottom_rect
        self.card_rects: List[Rect] = card_rects

        self.exercise_rect: Rect = card_rects[0]   # exercise + reps + progress bar
        self.metrics_rect: Rect = card_rects[1]    # stage + angle + FPS
        self.feedback_rect: Rect = card_rects[2]   # feedback message box
        self.stats_rect: Rect = card_rects[3]      # workout statistics

        # Legacy convenience attributes (kept for any external readers).
        self.header_height = header_height
        self.bottom_height = bottom_rect[3]
        self.middle_height = middle_height
        self.camera_width = camera_rect[2]
        self.right_panel_width = sidebar_rect[2]
        self.bottom_card_width = card_rects[0][2]

        self._invalidate_render_caches()

    def _invalidate_render_caches(self) -> None:
        """Drop every size-dependent cached panel/measurement after a layout change."""
        self._camera_fit_cache.clear()
        self._sidebar_cache.clear()
        self._header_base = None
        self._camera_card_base = None
        self._card_base_panel = None
        # Text-size cache is keyed by (text, font, scale, thickness) only,
        # not by layout, so it stays valid across resizes and is not cleared.

    # ------------------------------------------------------------------
    # Text measurement / drawing toolkit
    # ------------------------------------------------------------------

    def _get_text_size(self, text: str, font: int, scale: float, thickness: int) -> Tuple[int, int]:
        """Memoized cv2.getTextSize() - avoids recomputing the same measurement every frame."""
        key = (text, font, scale, thickness)
        cached = self._text_size_cache.get(key)
        if cached is None:
            cached = cv2.getTextSize(text, font, scale, thickness)[0]
            self._text_size_cache[key] = cached
        return cached

    def _draw_title(self, panel: np.ndarray, text: str, origin: Tuple[int, int],
                     color: Tuple[int, int, int] = Theme.TEXT_PRIMARY) -> None:
        """Card/section title style: bold, slightly larger."""
        _put_text(panel, text, origin, Theme.SCALE_TITLE, color, 2, Theme.FONT_BOLD)

    def _draw_section_header(self, panel: np.ndarray, text: str, origin: Tuple[int, int],
                              color: Tuple[int, int, int] = Theme.TEXT_MUTED) -> None:
        """Small muted uppercase section header (e.g. 'EXERCISE GUIDE')."""
        _put_text(panel, text, origin, Theme.SCALE_SECTION_HEADER, color, 1)

    def _draw_label(self, panel: np.ndarray, text: str, origin: Tuple[int, int],
                     color: Tuple[int, int, int] = Theme.TEXT_MUTED) -> None:
        """Left-aligned field label (e.g. 'Target Muscle', 'Elapsed Time')."""
        _put_text(panel, text, origin, Theme.SCALE_LABEL, color, 1)

    def _draw_value(self, panel: np.ndarray, text: str, origin: Tuple[int, int],
                     color: Tuple[int, int, int] = Theme.TEXT_PRIMARY, bold: bool = True) -> None:
        """Left-aligned field value, bold by default for emphasis."""
        font = Theme.FONT_BOLD if bold else Theme.FONT
        thickness = 2 if bold else 1
        _put_text(panel, text, origin, Theme.SCALE_VALUE, color, thickness, font)

    def _draw_wrapped_text(
        self,
        panel: np.ndarray,
        text: str,
        x: int,
        y: int,
        max_chars: int,
        line_height: int,
        color: Tuple[int, int, int] = Theme.TEXT_SECONDARY,
        scale: float = Theme.SCALE_INSTRUCTION,
        max_lines: Optional[int] = None,
        bottom_limit: Optional[int] = None,
    ) -> int:
        """
        Left-aligned, word-wrapped text block starting at (x, y).
        Stops early if `bottom_limit` would be exceeded, so text never
        overflows outside its card. Returns the y coordinate after the
        last line actually drawn.
        """
        lines = _wrap_text(text, max_chars)
        if max_lines is not None:
            lines = lines[:max_lines]

        for line in lines:
            if bottom_limit is not None and y > bottom_limit:
                break
            _put_text(panel, line, (x, y), scale, color, 1)
            y += line_height

        return y

    def _draw_instruction_list(
        self,
        panel: np.ndarray,
        instructions: Sequence[str],
        x: int,
        y: int,
        max_chars: int,
        line_height: int,
        bottom_limit: int,
        active_index: int = -1,
    ) -> int:
        """
        Draw a numbered instruction list, each item marked with a small
        circled number (① ② ③ ④ style, rendered as a drawn circle with
        the digit inside rather than a unicode glyph, since the active
        Hershey fonts don't support circled-digit characters). The
        active instruction (matched to the current workout stage, when
        available) is highlighted with a filled accent circle and
        primary text color; the rest use muted outlines and secondary
        text. Returns the y coordinate after the last line drawn.
        """
        radius = self.INSTRUCTION_CIRCLE_RADIUS
        text_x = x + radius * 2 + 10

        for index, instruction in enumerate(instructions):
            if y > bottom_limit:
                break

            is_active = index == active_index
            circle_color = Theme.ACCENT if is_active else Theme.TEXT_MUTED
            text_color = Theme.TEXT_PRIMARY if is_active else Theme.TEXT_SECONDARY

            circle_cx = x + radius
            circle_cy = y - 4
            if is_active:
                cv2.circle(panel, (circle_cx, circle_cy), radius, circle_color, -1, cv2.LINE_AA)
                number_color = Theme.TEXT_ON_ACCENT
            else:
                cv2.circle(panel, (circle_cx, circle_cy), radius, circle_color, 1, cv2.LINE_AA)
                number_color = Theme.TEXT_MUTED

            number_text = str(index + 1)
            num_w, num_h = self._get_text_size(number_text, Theme.FONT, 0.35, 1)
            _put_text(panel, number_text, (circle_cx - num_w // 2, circle_cy + num_h // 2),
                      0.35, number_color, 1)

            y = self._draw_wrapped_text(
                panel, instruction, text_x, y, max_chars, line_height,
                color=text_color, scale=Theme.SCALE_INSTRUCTION, bottom_limit=bottom_limit,
            )
            y += self.TEXT_SPACING

        return y

    @staticmethod
    def _infer_active_instruction_index(instructions: Sequence[str], stage: str, progress: float) -> int:
        """
        Best-effort guess at which instruction step the user is
        currently on, used to highlight it in the guide list:

            1. If the current workout `stage` text appears inside one
               of the instruction strings, that instruction is active.
            2. Otherwise, fall back to a simple progress-based bucket
               (rep progress toward the goal maps onto the instruction
               list) so *something* sensible highlights as reps advance.

        Returns -1 if there are no instructions to highlight.
        """
        if not instructions:
            return -1

        stage_lower = (stage or "").strip().lower()
        if stage_lower:
            for index, instruction in enumerate(instructions):
                if stage_lower in instruction.lower():
                    return index

        if len(instructions) == 1:
            return 0

        bucket = min(len(instructions) - 1, int(max(0.0, min(1.0, progress)) * len(instructions)))
        return bucket

    # ------------------------------------------------------------------
    # Public API - live dashboard
    # ------------------------------------------------------------------

    def render(
        self,
        camera_frame: Optional[np.ndarray],
        workout_name: str,
        workout_data: Dict,
        fps: float,
        elapsed_time: float,
        current_set: int,
        total_sets: int,
    ) -> np.ndarray:
        """
        Compose the full PoseAI window for a single frame.

        Args:
            camera_frame: latest webcam frame (BGR), or None.
            workout_name: display name of the active exercise. Used to
                automatically look up all guide/reference info (image,
                target muscle, difficulty, goal reps, instructions)
                from core/exercise_data.EXERCISE_DATA.
            workout_data: dict produced by the active workout, expected
                to (optionally) contain "reps", "stage", "feedback",
                and "angle" keys. Missing keys degrade gracefully.
            fps: current processing frame rate.
            elapsed_time: seconds elapsed in the current workout/set.
            current_set: 1-indexed current set number. Displayed
                automatically in the header as "Set X / Y".
            total_sets: total number of sets in the session.

        Returns:
            A single BGR np.ndarray of size (window_height, window_width, 3)
            ready to be shown with cv2.imshow.
        """
        # Resolve every exercise-specific detail once per frame from
        # the central registry - nothing exercise-specific lives here.
        exercise_info = get_exercise_info_by_name(workout_name)

        canvas = np.full(
            (self.window_height, self.window_width, 3), Theme.BACKGROUND, dtype=np.uint8
        )

        # --- Information hierarchy: camera first (primary focus), then
        #     guide, then the feedback/reps/progress/stage/stats cards. --
        header_x, header_y, _hw, _hh = self.header_rect
        _overlay_image(canvas, self._render_header(exercise_info, elapsed_time, current_set, total_sets),
                        header_x, header_y)

        camera_x, camera_y, _cw, _ch = self.camera_rect
        _overlay_image(canvas, self._render_camera(camera_frame), camera_x, camera_y)

        sidebar_x, sidebar_y, _sw, _sh = self.sidebar_rect
        _overlay_image(canvas, self._render_sidebar(exercise_info, workout_data), sidebar_x, sidebar_y)

        card_panels = self._render_bottom_cards(exercise_info, workout_data, fps, elapsed_time, current_set, total_sets)
        for rect, card in zip(self.card_rects, card_panels):
            card_x, card_y, _cw2, _ch2 = rect
            _overlay_image(canvas, card, card_x, card_y)

        return canvas

    # ------------------------------------------------------------------
    # Public API - full-screen overlay states (unchanged design/logic)
    # ------------------------------------------------------------------

    def render_set_complete(
        self,
        workout_name: str,
        current_set: int,
        total_sets: int,
    ) -> np.ndarray:
        """
        Full-screen "Set Complete" overlay shown between sets of the
        same exercise, while waiting for the user to press SPACE.
        """
        stat_rows: List[Tuple[str, str, Optional[Tuple[int, int, int]]]] = [
            ("Exercise", workout_name, None),
            ("Set Finished", f"{current_set} / {total_sets}", Theme.WARNING),
        ]
        return self._render_overlay_screen(
            title="Set Complete",
            title_color=Theme.WARNING,
            subtitle="Take a short breather",
            stat_rows=stat_rows,
            footer_lines=["Press SPACE to continue"],
            icon=None,
        )

    def render_workout_complete(
        self,
        workout_name: str,
        total_reps: float,
        workout_time: float,
        average_fps: float,
    ) -> np.ndarray:
        """
        Full-screen "Exercise Completed" overlay shown once all sets
        of the current exercise are finished, while waiting for the
        user to press ENTER to move on to the next exercise.
        """
        stat_rows: List[Tuple[str, str, Optional[Tuple[int, int, int]]]] = [
            ("Exercise", workout_name, None),
            ("Total Reps", str(int(total_reps)), Theme.SUCCESS),
            ("Workout Time", self._format_time(workout_time), None),
            ("Average FPS", f"{average_fps:.1f}", None),
        ]
        return self._render_overlay_screen(
            title="Exercise Completed",
            title_color=Theme.SUCCESS,
            subtitle="Great Job!",
            stat_rows=stat_rows,
            footer_lines=["Press ENTER for next exercise"],
            icon="check",
        )

    def render_session_summary(
        self,
        workout_name: str,
        completed_sets: int,
        goal_sets: int,
        total_time: float,
        total_reps: float,
        average_fps: float,
        calories: float,
        avg_rep_speed: float,
        completion_pct: float,
        rating: str,
        timestamp_str: str,
    ) -> np.ndarray:
        """
        Professional Session Summary Dashboard shown when the user
        quits (Q). Displays exercise name, completed/goal sets, total
        reps, workout duration, average FPS, estimated calories,
        average repetition speed, completion percentage, performance
        rating and the current date/time - then offers two on-screen
        button prompts:

            ENTER -> back to exercise selection
            ESC   -> exit PoseAI
        """
        rating_colors = {
            "Excellent": Theme.SUCCESS,
            "Good": Theme.WARNING,
            "Needs Improvement": Theme.DANGER,
        }
        rating_color = rating_colors.get(rating, Theme.TEXT_PRIMARY)

        stat_rows: List[Tuple[str, str, Optional[Tuple[int, int, int]]]] = [
            ("Exercise Name", workout_name, None),
            ("Completed Sets", f"{completed_sets} / {goal_sets}", Theme.ACCENT),
            ("Total Repetitions", str(int(total_reps)), None),
            ("Workout Duration", self._format_time(total_time), None),
            ("Average FPS", f"{average_fps:.1f}", None),
            ("Calories Burned (Est.)", f"{calories:.0f} kcal", None),
            ("Avg. Rep Speed", f"{avg_rep_speed:.1f} reps/min", None),
            ("Completion", f"{completion_pct:.0f}%", Theme.SUCCESS if completion_pct >= 100 else Theme.WARNING),
            ("Performance", rating, rating_color),
        ]
        return self._render_overlay_screen(
            title="Session Summary Dashboard",
            title_color=rating_color,
            subtitle=f"Thanks for training with PoseAI  •  {timestamp_str}",
            stat_rows=stat_rows,
            footer_lines=[
                "[ ENTER ]  Back to Exercise Selection",
                "[ ESC ]  Exit PoseAI",
            ],
            icon=None,
        )

    # ------------------------------------------------------------------
    # Overlay screen builder (shared by the three full-screen states)
    # ------------------------------------------------------------------

    def _render_overlay_screen(
        self,
        title: str,
        title_color: Tuple[int, int, int],
        subtitle: Optional[str],
        stat_rows: Sequence[Tuple[str, str, Optional[Tuple[int, int, int]]]],
        footer_lines: Sequence[str],
        icon: Optional[str] = None,
    ) -> np.ndarray:
        """
        Render a modern, centered "card" overlay covering the full
        window - used for Set Complete, Exercise Completed and Session
        Summary screens so they all share one consistent, professional
        design language.

        The card auto-grows vertically with the number of stat_rows /
        footer_lines so longer dashboards (e.g. the Session Summary)
        remain readable and don't overflow the card border. These
        screens are shown only during infrequent state transitions (not
        every frame), so they are rebuilt on demand rather than cached.
        """
        canvas = np.full(
            (self.window_height, self.window_width, 3), Theme.BACKGROUND, dtype=np.uint8
        )

        card_width = int(self.window_width * 0.50)

        base_height = int(self.window_height * 0.40)
        extra_for_rows = max(0, len(stat_rows) - 2) * 42
        extra_for_footer = max(0, len(footer_lines) - 1) * 34
        card_height = min(
            int(self.window_height * 0.90),
            base_height + extra_for_rows + extra_for_footer,
        )

        card_x = (self.window_width - card_width) // 2
        card_y = (self.window_height - card_height) // 2

        shadow_offset = 8
        _draw_rect(
            canvas,
            (card_x + shadow_offset, card_y + shadow_offset),
            (card_x + card_width + shadow_offset, card_y + card_height + shadow_offset),
            (225, 225, 225), filled=True, radius=24,
        )

        _draw_rect(canvas, (card_x, card_y), (card_x + card_width, card_y + card_height),
                   Theme.CARD_BG, filled=True, radius=24)
        _draw_rect(canvas, (card_x, card_y), (card_x + card_width, card_y + card_height),
                   Theme.BORDER, filled=False, thickness=1, radius=24)

        _draw_rect(canvas, (card_x + 24, card_y), (card_x + card_width - 24, card_y + 6),
                   title_color, filled=True, radius=3)

        y = card_y + 50

        if icon == "check":
            icon_radius = 28
            icon_cx = card_x + card_width // 2
            icon_cy = y + icon_radius
            cv2.circle(canvas, (icon_cx, icon_cy), icon_radius, title_color, 3, cv2.LINE_AA)
            p1 = (icon_cx - 13, icon_cy + 2)
            p2 = (icon_cx - 3, icon_cy + 13)
            p3 = (icon_cx + 15, icon_cy - 13)
            cv2.line(canvas, p1, p2, title_color, 3, cv2.LINE_AA)
            cv2.line(canvas, p2, p3, title_color, 3, cv2.LINE_AA)
            y += icon_radius * 2 + 24

        title_size = self._get_text_size(title, Theme.FONT_BOLD, 0.95, 2)
        title_x = card_x + (card_width - title_size[0]) // 2
        _put_text(canvas, title, (title_x, y), 0.95, Theme.TEXT_PRIMARY, 2, Theme.FONT_BOLD)
        y += 38

        if subtitle:
            subtitle_size = self._get_text_size(subtitle, Theme.FONT, 0.52, 1)
            subtitle_x = card_x + (card_width - subtitle_size[0]) // 2
            _put_text(canvas, subtitle, (subtitle_x, y), 0.52, Theme.TEXT_SECONDARY, 1)
            y += 34
        else:
            y += 12

        cv2.line(canvas, (card_x + 40, y), (card_x + card_width - 40, y), Theme.BORDER, 1)
        y += 32

        row_x_label = card_x + 50
        row_x_value_right_edge = card_x + card_width - 50

        for label, value, value_color in stat_rows:
            _put_text(canvas, label, (row_x_label, y), 0.52, Theme.TEXT_MUTED, 1)
            color = value_color or Theme.TEXT_PRIMARY
            value_size = self._get_text_size(value, Theme.FONT_BOLD, 0.6, 2)
            _put_text(canvas, value, (row_x_value_right_edge - value_size[0], y),
                      0.6, color, 2, Theme.FONT_BOLD)
            y += 38

        y += 6
        cv2.line(canvas, (card_x + 40, y), (card_x + card_width - 40, y), Theme.BORDER, 1)
        y += 34

        button_height = 40
        button_gap = 14
        button_width = card_width - 80

        for line in footer_lines:
            btn_x1 = card_x + 40
            btn_y1 = y
            btn_x2 = btn_x1 + button_width
            btn_y2 = btn_y1 + button_height

            _draw_rect(canvas, (btn_x1, btn_y1), (btn_x2, btn_y2),
                       Theme.ACCENT_SOFT, filled=True, radius=8)
            _draw_rect(canvas, (btn_x1, btn_y1), (btn_x2, btn_y2),
                       Theme.ACCENT, filled=False, thickness=1, radius=8)

            line_size = self._get_text_size(line, Theme.FONT, 0.55, 1)
            line_x = btn_x1 + (button_width - line_size[0]) // 2
            line_y = btn_y1 + (button_height + line_size[1]) // 2
            _put_text(canvas, line, (line_x, line_y), 0.55, Theme.ACCENT, 1)

            y += button_height + button_gap

        return canvas

    # ------------------------------------------------------------------
    # Header (static base cached, dynamic values drawn fresh each frame)
    # ------------------------------------------------------------------

    def _build_header_base(self) -> np.ndarray:
        """Static header content: background, border line, and brand labels."""
        _x, _y, width, height = self.header_rect
        panel = np.full((height, width, 3), Theme.HEADER_BG, dtype=np.uint8)
        cv2.line(panel, (0, height - 1), (width, height - 1), Theme.BORDER, 2)

        mid_y = height // 2
        self._draw_title(panel, "PoseAI", (self.WINDOW_PADDING + 8, mid_y - 4), Theme.ACCENT)
        _put_text(panel, "AI Fitness Trainer", (150, mid_y - 4), 0.5, Theme.TEXT_MUTED, 1)
        return panel

    def _render_header(
        self,
        exercise_info: ExerciseInfo,
        elapsed_time: float,
        current_set: int,
        total_sets: int,
    ) -> np.ndarray:
        """Top header: brand (cached), exercise name, workout timer, set counter."""
        if self._header_base is None:
            self._header_base = self._build_header_base()

        panel = self._header_base.copy()
        _x, _y, width, height = self.header_rect
        mid_y = height // 2

        _put_text(panel, exercise_info["name"], (150, mid_y + 20), 0.55, Theme.TEXT_PRIMARY, 1)

        timer_text = self._format_time(elapsed_time)
        set_text = f"Set {current_set} / {total_sets}"

        set_text_size = self._get_text_size(set_text, Theme.FONT, 0.6, 2)
        timer_text_size = self._get_text_size(timer_text, Theme.FONT_BOLD, 0.8, 2)

        set_chip_w = set_text_size[0] + 28
        set_chip_h = 34
        set_chip_x2 = width - self.WINDOW_PADDING - 8
        set_chip_x1 = set_chip_x2 - set_chip_w
        set_chip_y1 = mid_y - set_chip_h // 2
        set_chip_y2 = mid_y + set_chip_h // 2

        _draw_rect(panel, (set_chip_x1, set_chip_y1), (set_chip_x2, set_chip_y2),
                   Theme.ACCENT_SOFT, filled=True, radius=17)
        _put_text(panel, set_text, (set_chip_x1 + 14, mid_y + 6), 0.6, Theme.ACCENT, 2)

        timer_x = set_chip_x1 - timer_text_size[0] - 40
        _put_text(panel, timer_text, (timer_x, mid_y + 6), 0.8, Theme.TEXT_PRIMARY, 2, Theme.FONT_BOLD)
        _put_text(panel, "TIMER", (timer_x, mid_y - 14), 0.35, Theme.TEXT_MUTED, 1)

        return panel

    # ------------------------------------------------------------------
    # Camera panel + dynamic camera scaling (single resize per frame)
    # ------------------------------------------------------------------

    def _build_camera_card_base(self) -> None:
        """
        Build (once) the static camera card background/border, and
        precompute the fixed inner video-area offset/size so the same
        math isn't repeated every frame.
        """
        _x, _y, width, height = self.camera_rect
        panel = np.full((height, width, 3), Theme.BACKGROUND, dtype=np.uint8)

        margin = self.CARD_SPACING + 6
        radius = 20
        x1, y1 = margin, margin
        x2, y2 = width - margin, height - margin

        _draw_rect(panel, (x1, y1), (x2, y2), Theme.CARD_BG, filled=True, radius=radius)
        _draw_rect(panel, (x1, y1), (x2, y2), Theme.BORDER, filled=False, thickness=2, radius=radius)

        inset = 8
        video_w = max(1, (x2 - x1) - 2 * inset)
        video_h = max(1, (y2 - y1) - 2 * inset)

        self._camera_card_base = panel
        self._camera_inner_offset = (x1 + inset, y1 + inset)
        self._camera_inner_size = (video_w, video_h)

    def _fit_camera(self, frame: np.ndarray, max_width: int, max_height: int) -> Optional[CameraFit]:
        """
        Compute (and cache) the largest size the given camera frame can
        be resized to so it fits entirely within (max_width, max_height)
        without stretching or cropping, plus the (x, y) offset needed
        to center it there. Cached per (source resolution, target size)
        pair so a webcam whose resolution doesn't change skips
        recomputing the same scale/offset every call.
        """
        if frame is None or frame.size == 0:
            return None

        src_h, src_w = frame.shape[:2]
        if src_w <= 0 or src_h <= 0:
            return None

        cache_key = (src_w, src_h, max_width, max_height)
        cached = self._camera_fit_cache.get(cache_key)
        if cached is not None:
            return cached

        new_w, new_h = _compute_fit_dimensions(src_w, src_h, max_width, max_height, max_upscale=1.0)
        x_offset = (max_width - new_w) // 2
        y_offset = (max_height - new_h) // 2

        fit: CameraFit = (new_w, new_h, x_offset, y_offset)
        self._camera_fit_cache[cache_key] = fit
        return fit

    @staticmethod
    def _resize_camera(frame: np.ndarray, new_width: int, new_height: int) -> np.ndarray:
        """
        Resize `frame` to exactly (new_width, new_height) - once. If
        already that size, the resize is skipped entirely so rendering
        stays smooth. Downscaling uses INTER_AREA; upscaling uses
        INTER_LINEAR.
        """
        src_h, src_w = frame.shape[:2]
        if new_width == src_w and new_height == src_h:
            return frame

        interpolation = cv2.INTER_AREA if (new_width <= src_w and new_height <= src_h) else cv2.INTER_LINEAR
        return cv2.resize(frame, (new_width, new_height), interpolation=interpolation)

    def _render_camera(self, camera_frame: Optional[np.ndarray]) -> np.ndarray:
        """
        Largest area: live webcam feed, framed as a card. The card
        background/border is cached and reused; the source frame is
        resized exactly once per frame (via the cached fit) and pasted
        directly into the camera panel, then centered both horizontally
        and vertically. Any remaining space is filled with the camera
        surface's background color. Works automatically for any
        incoming webcam resolution (640x480, 1280x720, 1920x1080, ...).
        """
        if self._camera_card_base is None:
            self._build_camera_card_base()

        panel = self._camera_card_base.copy()
        off_x, off_y = self._camera_inner_offset
        area_w, area_h = self._camera_inner_size

        fit = self._fit_camera(camera_frame, area_w, area_h) if camera_frame is not None else None

        if fit is None:
            surface = np.full((area_h, area_w, 3), Theme.CAMERA_BG, dtype=np.uint8)
            text = "No Camera Feed"
            text_size = self._get_text_size(text, Theme.FONT, 0.8, 2)
            _put_text(surface, text, ((area_w - text_size[0]) // 2, area_h // 2), 0.8, Theme.TEXT_ON_DARK, 2)
            _overlay_image(panel, surface, off_x, off_y)
            return panel

        new_w, new_h, x_offset, y_offset = fit
        resized_frame = self._resize_camera(camera_frame, new_w, new_h)

        if new_w == area_w and new_h == area_h:
            # Frame fills the area exactly - paste it directly, no letterbox needed.
            _overlay_image(panel, resized_frame, off_x, off_y)
        else:
            surface = np.full((area_h, area_w, 3), Theme.CAMERA_BG, dtype=np.uint8)
            _overlay_image(surface, resized_frame, x_offset, y_offset)
            _overlay_image(panel, surface, off_x, off_y)

        return panel

    # ------------------------------------------------------------------
    # Sidebar / Exercise Guide (fully cached per exercise + active step)
    # ------------------------------------------------------------------

    def _draw_guide_image(
        self,
        panel: np.ndarray,
        image_filename: str,
        area_x: int,
        area_y: int,
        area_width: int,
        area_height: int,
        padding: int,
    ) -> None:
        """
        Draw the exercise guide image centered within
        (area_width, area_height), with equal padding on all four
        sides. Falls back to a centered "No Guide Available" message
        if no image exists for the exercise. Never stretches, never
        crops, never enlarges past `GuideImageLoader`'s quality cap.
        """
        raw_image = self._guide_loader.load_guide_image(image_filename)

        if raw_image is None:
            text = "No Guide Available"
            text_size = self._get_text_size(text, Theme.FONT, 0.5, 1)
            text_x = area_x + (area_width - text_size[0]) // 2
            text_y = area_y + area_height // 2
            _put_text(panel, text, (text_x, text_y), 0.5, Theme.TEXT_MUTED, 1)
            return

        inner_width = max(1, area_width - 2 * padding)
        inner_height = max(1, area_height - 2 * padding)

        resized_image = self._guide_loader.resize_guide_image(raw_image, inner_width, inner_height)
        img_h, img_w = resized_image.shape[:2]

        offset_x = area_x + (area_width - img_w) // 2
        offset_y = area_y + (area_height - img_h) // 2
        _overlay_image(panel, resized_image, offset_x, offset_y)

    def _build_sidebar_panel(self, exercise_info: ExerciseInfo, active_instruction_index: int) -> np.ndarray:
        """
        Build the full sidebar panel: Exercise Guide image, name,
        metadata (target/difficulty/goal/sets), and numbered
        instructions (with the active step highlighted). This panel
        contains nothing that changes on a per-frame basis (reps, fps,
        timer live in the bottom cards), so the caller caches the
        result per (exercise, active_instruction_index).
        """
        _x, _y, width, height = self.sidebar_rect
        panel = np.full((height, width, 3), Theme.BACKGROUND, dtype=np.uint8)

        outer_margin = self.WINDOW_PADDING
        section_gap = self.SECTION_SPACING
        content_x1 = outer_margin
        content_x2 = width - outer_margin
        content_width = content_x2 - content_x1

        y = outer_margin

        # --- Section 1: Exercise Guide image card, centered image with
        #     equal padding on all sides, never overlapping other sections.
        image_card_height = int(height * 0.30)
        image_card_y1, image_card_y2 = y, y + image_card_height
        _draw_rect(panel, (content_x1, image_card_y1), (content_x2, image_card_y2),
                   Theme.CARD_BG, filled=True, radius=14)
        _draw_rect(panel, (content_x1, image_card_y1), (content_x2, image_card_y2),
                   Theme.BORDER, filled=False, thickness=1, radius=14)

        label_y = image_card_y1 + 20
        self._draw_section_header(panel, "EXERCISE GUIDE", (content_x1 + 16, label_y))

        image_area_top = label_y + 10
        image_area_height = image_card_y2 - image_area_top - 14
        self._draw_guide_image(
            panel, exercise_info.get("image", ""),
            content_x1, image_area_top, content_width, image_area_height,
            self.CARD_PADDING - 6,
        )

        y = image_card_y2 + section_gap

        # --- Exercise name --------------------------------------------------
        name_text = exercise_info["name"]
        max_name_chars = max(14, content_width // 11)
        name_lines = _wrap_text(name_text, max_name_chars)[:2]
        self._draw_title(panel, name_lines[0], (content_x1, y + 18))
        y += 26
        if len(name_lines) > 1:
            self._draw_title(panel, name_lines[1], (content_x1, y + 18))
            y += 26
        y += section_gap

        # --- Section 2: metadata card (target / difficulty / goal / sets),
        #     labels and values aligned to the same left/right columns.
        meta_rows = [
            ("Target Muscle", str(exercise_info.get("target", "-"))),
            ("Difficulty", str(exercise_info.get("difficulty", "-"))),
            ("Goal Reps", str(exercise_info.get("goal", "-"))),
            ("Sets", str(exercise_info.get("sets", "-"))),
        ]
        row_height = 30
        meta_card_height = 20 + len(meta_rows) * row_height
        meta_y1, meta_y2 = y, y + meta_card_height
        _draw_rect(panel, (content_x1, meta_y1), (content_x2, meta_y2),
                   Theme.CARD_BG, filled=True, radius=14)
        _draw_rect(panel, (content_x1, meta_y1), (content_x2, meta_y2),
                   Theme.BORDER, filled=False, thickness=1, radius=14)

        row_y = meta_y1 + 26
        for label, value in meta_rows:
            self._draw_label(panel, label, (content_x1 + 16, row_y))
            value_size = self._get_text_size(value, Theme.FONT, 0.46, 1)
            _put_text(panel, value, (content_x2 - 16 - value_size[0], row_y), 0.46, Theme.TEXT_PRIMARY, 1)
            row_y += row_height

        y = meta_y2 + section_gap

        # --- Section 3: numbered Instructions card, never overlapping the
        #     guide image / metadata above it - each gets its own vertical
        #     slice of the sidebar, sized to fit the remaining height.
        instructions = exercise_info.get("instructions", []) or []
        max_chars = max(20, (content_width - self.CARD_PADDING * 2 - self.INSTRUCTION_CIRCLE_RADIUS * 2) // 8)

        wrapped_line_counts = [len(_wrap_text(instr, max_chars)) for instr in instructions[:4]]
        instructions_lines_total = sum(wrapped_line_counts)
        instructions_card_height = min(
            height - (y - outer_margin) - outer_margin,
            40 + instructions_lines_total * 18 + max(0, len(wrapped_line_counts) - 1) * (self.TEXT_SPACING + 4),
        )
        instructions_card_height = max(instructions_card_height, 60)

        instr_y1, instr_y2 = y, y + instructions_card_height
        _draw_rect(panel, (content_x1, instr_y1), (content_x2, instr_y2),
                   Theme.CARD_BG, filled=True, radius=14)
        _draw_rect(panel, (content_x1, instr_y1), (content_x2, instr_y2),
                   Theme.BORDER, filled=False, thickness=1, radius=14)

        self._draw_section_header(panel, "INSTRUCTIONS", (content_x1 + 16, instr_y1 + 22))

        self._draw_instruction_list(
            panel,
            instructions[:4],
            content_x1 + 16,
            instr_y1 + 46,
            max_chars,
            18,
            bottom_limit=instr_y2 - 12,
            active_index=active_instruction_index,
        )

        return panel

    def _render_sidebar(self, exercise_info: ExerciseInfo, workout_data: Dict) -> np.ndarray:
        """
        Return the sidebar panel for the current exercise, from cache
        whenever possible. The sidebar has no per-frame-varying content
        of its own (reps/fps/timer live in the bottom cards) other than
        which instruction step is highlighted, so the cache key is
        (exercise name, active instruction index) - a small, bounded
        set of distinct panels reused across many frames.
        """
        instructions = exercise_info.get("instructions", []) or []
        reps = int(workout_data.get("reps", 0) or 0)
        goal = max(1, int(exercise_info.get("goal", 1) or 1))
        progress = min(1.0, reps / goal) if goal else 0.0
        stage = str(workout_data.get("stage", "") or "")

        active_index = self._infer_active_instruction_index(instructions, stage, progress)

        cache_key = (exercise_info["name"], active_index)
        cached = self._sidebar_cache.get(cache_key)
        if cached is not None:
            return cached

        panel = self._build_sidebar_panel(exercise_info, active_index)
        self._sidebar_cache[cache_key] = panel
        return panel

    # ------------------------------------------------------------------
    # Bottom row: four equally sized, identical-height, evenly spaced cards
    # ------------------------------------------------------------------

    def _get_card_base_panel(self, width: int, height: int) -> np.ndarray:
        """
        Return the shared static card background/border (rounded rect),
        rebuilding it only if the requested size differs from what's
        cached. All four bottom cards share the same size, so this is
        built once per layout and reused via `.copy()` for every card
        every frame instead of redrawing the rounded rect four times.
        """
        base = self._card_base_panel
        if base is None or base.shape[1] != width or base.shape[0] != height:
            panel = np.full((height, width, 3), Theme.BACKGROUND, dtype=np.uint8)
            x1, y1 = self.CARD_SPACING, self.CARD_SPACING
            x2, y2 = width - self.CARD_SPACING, height - self.CARD_SPACING
            _draw_rect(panel, (x1, y1), (x2, y2), Theme.CARD_BG, filled=True, radius=16)
            _draw_rect(panel, (x1, y1), (x2, y2), Theme.BORDER, filled=False, thickness=1, radius=16)
            self._card_base_panel = panel
            base = panel
        return base

    def _card_content_bounds(self, width: int, height: int) -> Tuple[int, int, int, int]:
        """Inner content rect shared by every bottom card (single source of the inset math)."""
        pad = self.CARD_SPACING + self.CARD_PADDING
        return pad, pad, width - pad, height - pad

    def _render_bottom_cards(
        self,
        exercise_info: ExerciseInfo,
        workout_data: Dict,
        fps: float,
        elapsed_time: float,
        current_set: int,
        total_sets: int,
    ) -> List[np.ndarray]:
        """Build all four bottom cards in information-hierarchy order: reps/progress, stage, feedback, stats."""
        return [
            self._build_card_exercise_reps(exercise_info, workout_data),
            self._build_card_stage_metrics(workout_data, fps),
            self._build_card_feedback(workout_data),
            self._build_card_workout_stats(elapsed_time, current_set, total_sets),
        ]

    def _build_card_exercise_reps(self, exercise_info: ExerciseInfo, workout_data: Dict) -> np.ndarray:
        """Card 1 (exercise_rect): exercise name, reps count, progress bar."""
        _rx, _ry, card_width, card_height = self.exercise_rect
        panel = self._get_card_base_panel(card_width, card_height).copy()
        x1, y1, x2, y2 = self._card_content_bounds(card_width, card_height)
        content_width = x2 - x1

        exercise_name = str(workout_data.get("exercise", exercise_info["name"]))
        reps = int(workout_data.get("reps", 0) or 0)
        goal = max(1, int(exercise_info.get("goal", 1) or 1))
        progress = min(1.0, reps / goal)

        self._draw_section_header(panel, "EXERCISE", (x1, y1 + 6))
        max_name_chars = max(10, content_width // 9)
        name_line = _wrap_text(exercise_name, max_name_chars)[0]
        self._draw_label(panel, name_line, (x1, y1 + 30), Theme.TEXT_PRIMARY)

        self._draw_section_header(panel, "REPS", (x1, y1 + 60))
        _put_text(panel, f"{reps} / {goal}", (x1, y1 + 90), 0.72, Theme.ACCENT, 2, Theme.FONT_BOLD)

        # --- Rounded progress bar: blue while progressing, green when done --
        bar_h = 16
        bar_y1 = y2 - bar_h - 18
        bar_y2 = bar_y1 + bar_h
        _draw_rect(panel, (x1, bar_y1), (x2, bar_y2), Theme.CARD_BG_ALT, filled=True, radius=bar_h // 2)
        fill_w = int(content_width * progress)
        if fill_w > 0:
            bar_color = Theme.SUCCESS if progress >= 1.0 else Theme.ACCENT
            fill_x2 = min(x1 + max(fill_w, bar_h), x2)
            _draw_rect(panel, (x1, bar_y1), (fill_x2, bar_y2), bar_color, filled=True, radius=bar_h // 2)
        _draw_rect(panel, (x1, bar_y1), (x2, bar_y2), Theme.BORDER, filled=False, thickness=1, radius=bar_h // 2)

        _put_text(panel, f"{int(progress * 100)}% complete", (x1, y2), 0.4, Theme.TEXT_SECONDARY, 1)

        return panel

    def _build_card_stage_metrics(self, workout_data: Dict, fps: float) -> np.ndarray:
        """Card 2 (metrics_rect): current stage, joint angle, live processing FPS."""
        _rx, _ry, card_width, card_height = self.metrics_rect
        panel = self._get_card_base_panel(card_width, card_height).copy()
        x1, y1, x2, y2 = self._card_content_bounds(card_width, card_height)

        stage = str(workout_data.get("stage", "-"))
        angle = workout_data.get("angle", None)
        angle_text = f"{angle:.1f}°" if isinstance(angle, (int, float)) else "-"

        row_gap = (y2 - y1) // 3

        self._draw_section_header(panel, "STAGE", (x1, y1 + 6))
        _put_text(panel, stage, (x1, y1 + 30), 0.6, Theme.TEXT_PRIMARY, 2, Theme.FONT_BOLD)

        self._draw_section_header(panel, "ANGLE", (x1, y1 + row_gap + 6))
        _put_text(panel, angle_text, (x1, y1 + row_gap + 30), 0.58, Theme.TEXT_PRIMARY, 2, Theme.FONT_BOLD)

        fps_color = Theme.SUCCESS if fps >= 20 else (Theme.WARNING if fps >= 10 else Theme.DANGER)
        self._draw_section_header(panel, "FPS", (x1, y1 + 2 * row_gap + 6))
        _put_text(panel, f"{fps:.1f}", (x1, y1 + 2 * row_gap + 30), 0.58, fps_color, 2, Theme.FONT_BOLD)

        return panel

    def _build_card_feedback(self, workout_data: Dict) -> np.ndarray:
        """Card 3 (feedback_rect): live coaching feedback, in a colored message box."""
        _rx, _ry, card_width, card_height = self.feedback_rect
        panel = self._get_card_base_panel(card_width, card_height).copy()
        x1, y1, x2, y2 = self._card_content_bounds(card_width, card_height)

        self._draw_section_header(panel, "FEEDBACK", (x1, y1 + 6))

        feedback = str(workout_data.get("feedback", "") or "Get Ready")
        accent_color, soft_color = self._feedback_colors(feedback)

        box_y1 = y1 + 20
        box_y2 = y2
        _draw_rect(panel, (x1, box_y1), (x2, box_y2), soft_color, filled=True, radius=12)
        _draw_rect(panel, (x1, box_y1), (x2, box_y2), accent_color, filled=False, thickness=1, radius=12)

        content_width = x2 - x1
        max_chars = max(12, (content_width - 20) // 10)
        lines = _wrap_text(feedback, max_chars)[:3]
        line_y = (box_y1 + box_y2) // 2 - (len(lines) - 1) * 13
        for line in lines:
            line_size = self._get_text_size(line, Theme.FONT_BOLD, Theme.SCALE_FEEDBACK, 2)
            line_x = x1 + max(0, (content_width - line_size[0]) // 2)
            _put_text(panel, line, (line_x, line_y), Theme.SCALE_FEEDBACK, accent_color, 2, Theme.FONT_BOLD)
            line_y += 26

        return panel

    def _build_card_workout_stats(self, elapsed_time: float, current_set: int, total_sets: int) -> np.ndarray:
        """Card 4 (stats_rect): workout statistics - elapsed time, completed sets, completion %."""
        _rx, _ry, card_width, card_height = self.stats_rect
        panel = self._get_card_base_panel(card_width, card_height).copy()
        x1, y1, x2, y2 = self._card_content_bounds(card_width, card_height)

        completed_sets = max(0, current_set - 1)
        total_sets_safe = max(1, total_sets)
        completion_pct = min(100.0, (completed_sets / total_sets_safe) * 100.0)
        completion_color = Theme.SUCCESS if completion_pct >= 100 else Theme.ACCENT

        row_gap = (y2 - y1) // 3

        self._draw_section_header(panel, "WORKOUT STATS", (x1, y1 + 6))

        self._draw_label(panel, "Elapsed Time", (x1, y1 + row_gap - 4), Theme.TEXT_SECONDARY)
        time_text = self._format_time(elapsed_time)
        time_size = self._get_text_size(time_text, Theme.FONT_BOLD, 0.5, 2)
        _put_text(panel, time_text, (x2 - time_size[0], y1 + row_gap - 4), 0.5, Theme.TEXT_PRIMARY, 2, Theme.FONT_BOLD)

        self._draw_label(panel, "Completed Sets", (x1, y1 + 2 * row_gap - 4), Theme.TEXT_SECONDARY)
        sets_text = f"{completed_sets} / {total_sets_safe}"
        sets_size = self._get_text_size(sets_text, Theme.FONT_BOLD, 0.5, 2)
        _put_text(panel, sets_text, (x2 - sets_size[0], y1 + 2 * row_gap - 4), 0.5, Theme.TEXT_PRIMARY, 2, Theme.FONT_BOLD)

        self._draw_label(panel, "Completion", (x1, y2 - 6), Theme.TEXT_SECONDARY)
        pct_text = f"{completion_pct:.0f}%"
        pct_size = self._get_text_size(pct_text, Theme.FONT_BOLD, 0.5, 2)
        _put_text(panel, pct_text, (x2 - pct_size[0], y2 - 6), 0.5, completion_color, 2, Theme.FONT_BOLD)

        return panel

    # ------------------------------------------------------------------
    # Utilities
    # ------------------------------------------------------------------

    @staticmethod
    def _feedback_colors(feedback: str) -> Tuple[Tuple[int, int, int], Tuple[int, int, int]]:
        """
        Pick a (accent_color, soft_background_color) pair for the
        feedback message box based on simple keyword heuristics -
        green for positive feedback, orange for corrective cues, red
        for anything indicating stop/pain/danger.
        """
        lowered = feedback.lower()
        if any(k in lowered for k in ("excellent", "good", "great", "perfect")):
            return Theme.SUCCESS, Theme.SUCCESS_SOFT
        if any(k in lowered for k in ("stop", "danger", "pain")):
            return Theme.DANGER, Theme.DANGER_SOFT
        if any(k in lowered for k in ("keep", "bend", "straight", "rotate", "hold", "return", "cross", "lower", "higher")):
            return Theme.WARNING, Theme.WARNING_SOFT
        return Theme.ACCENT, Theme.ACCENT_SOFT

    @staticmethod
    def _format_time(seconds: float) -> str:
        """Format elapsed seconds as MM:SS."""
        seconds = max(0, int(seconds))
        minutes, secs = divmod(seconds, 60)
        return f"{minutes:02d}:{secs:02d}"
        """ bscitit9@gmail,com"""