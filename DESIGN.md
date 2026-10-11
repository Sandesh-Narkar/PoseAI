---
name: PoseAI Precision System
colors:
  surface: '#faf8ff'
  surface-dim: '#d2d9f4'
  surface-bright: '#faf8ff'
  surface-container-lowest: '#ffffff'
  surface-container-low: '#f2f3ff'
  surface-container: '#eaedff'
  surface-container-high: '#e2e7ff'
  surface-container-highest: '#dae2fd'
  on-surface: '#131b2e'
  on-surface-variant: '#3f4850'
  inverse-surface: '#283044'
  inverse-on-surface: '#eef0ff'
  outline: '#707881'
  outline-variant: '#bfc7d2'
  surface-tint: '#006398'
  primary: '#006194'
  on-primary: '#ffffff'
  primary-container: '#007bb9'
  on-primary-container: '#fdfcff'
  inverse-primary: '#93ccff'
  secondary: '#006c49'
  on-secondary: '#ffffff'
  secondary-container: '#6cf8bb'
  on-secondary-container: '#00714d'
  tertiary: '#825100'
  on-tertiary: '#ffffff'
  tertiary-container: '#a36700'
  on-tertiary-container: '#fffbff'
  error: '#ba1a1a'
  on-error: '#ffffff'
  error-container: '#ffdad6'
  on-error-container: '#93000a'
  primary-fixed: '#cce5ff'
  primary-fixed-dim: '#93ccff'
  on-primary-fixed: '#001d31'
  on-primary-fixed-variant: '#004b73'
  secondary-fixed: '#6ffbbe'
  secondary-fixed-dim: '#4edea3'
  on-secondary-fixed: '#002113'
  on-secondary-fixed-variant: '#005236'
  tertiary-fixed: '#ffddb8'
  tertiary-fixed-dim: '#ffb95f'
  on-tertiary-fixed: '#2a1700'
  on-tertiary-fixed-variant: '#653e00'
  background: '#faf8ff'
  on-background: '#131b2e'
  surface-variant: '#dae2fd'
typography:
  display-lg:
    fontFamily: Plus Jakarta Sans
    fontSize: 40px
    fontWeight: '700'
    lineHeight: 48px
    letterSpacing: -0.03em
  display-lg-mobile:
    fontFamily: Plus Jakarta Sans
    fontSize: 30px
    fontWeight: '700'
    lineHeight: 38px
    letterSpacing: -0.02em
  headline-lg:
    fontFamily: Plus Jakarta Sans
    fontSize: 28px
    fontWeight: '700'
    lineHeight: 36px
    letterSpacing: -0.02em
  headline-md:
    fontFamily: Plus Jakarta Sans
    fontSize: 22px
    fontWeight: '600'
    lineHeight: 30px
    letterSpacing: -0.015em
  headline-sm:
    fontFamily: Plus Jakarta Sans
    fontSize: 18px
    fontWeight: '600'
    lineHeight: 26px
    letterSpacing: -0.01em
  metric-stat:
    fontFamily: Plus Jakarta Sans
    fontSize: 32px
    fontWeight: '800'
    lineHeight: 36px
    letterSpacing: -0.03em
  body-lg:
    fontFamily: Plus Jakarta Sans
    fontSize: 16px
    fontWeight: '400'
    lineHeight: 24px
  body-md:
    fontFamily: Plus Jakarta Sans
    fontSize: 14px
    fontWeight: '400'
    lineHeight: 22px
  label-lg:
    fontFamily: Plus Jakarta Sans
    fontSize: 14px
    fontWeight: '600'
    lineHeight: 20px
    letterSpacing: 0.01em
  label-md:
    fontFamily: Plus Jakarta Sans
    fontSize: 12px
    fontWeight: '600'
    lineHeight: 16px
    letterSpacing: 0.02em
  caption:
    fontFamily: Plus Jakarta Sans
    fontSize: 11px
    fontWeight: '500'
    lineHeight: 14px
    letterSpacing: 0.02em
rounded:
  sm: 0.5rem
  DEFAULT: 1rem
  md: 1.5rem
  lg: 2rem
  xl: 3rem
  full: 9999px
spacing:
  gutter: 1.5rem
  gutter-mobile: 1rem
  margin: 2.5rem
  margin-mobile: 1rem
  space-xs: 0.25rem
  space-sm: 0.5rem
  space-md: 1rem
  space-lg: 1.5rem
  space-xl: 2rem
  space-2xl: 3rem
---

## Brand & Style
This design system defines an intelligent, frictionless, computer-vision fitness experience. It bridges biomechanical precision and effortless daily wellness through an Apple Health-inspired aesthetic: clean white surfaces floating on cool neutral foundations, airy margins, friendly curvature, and electric performance cues.

### Personality & Tone
- **Precision AI with Human Warmth:** Visual cues reflect diagnostic accuracy (sub-millimeter pose estimation, rep cadence, joint angle markers) without feeling clinical or punishing.
- **Empowering & Frictionless:** Interfaces prioritize high-signal metrics, clear horizontal navigation rhythms, and immediate actionability over clutter.
- **Modern Wellness Athleticism:** Rooted in sleek contemporary minimalism, subtle surface elevation, and purposeful kinetic energy.

### Visual Style
A tailored blend of **Minimalist Tactile Modernism** and **Card-Centric Spatial Architecture**. Features include:
- Pure white container cards resting on ultra-soft off-white canvas backgrounds.
- Completely sidebar-free horizontal top navigation that maximizes lateral display space for workout streaming and biomechanical telemetry.
- High-radii corners (`rounded-2xl` to `rounded-3xl`) that soften complex computational health metrics into approachable, modular widgets.

## Colors
The palette balances an ultra-clean, clinical-grade canvas with energetic, focused athletic accents.

### Palette Architecture
- **Primary Accent (`#0284C7` / `#0EA5E9` / `#38BDF8`):** Athletic cyber sky. Used for focal callouts, active tracking sessions, interactive buttons, joint vector paths, and dominant navigation states.
- **Secondary Success (`#10B981`):** Kinetic emerald. Reserved for rep completions, perfect posture feedback, target heart rate locks, and completed weekly milestones.
- **Tertiary Alert (`#F59E0B`):** Biomechanical amber. Flags posture misalignments, strain warnings, and recovery reminders without evoking harsh failure.
- **Neutrals:**
  - `Canvas Background`: `#F8FAFC` (cool soft slate tint) transitioning down to `#F1F5F9` for secondary recessed groupings.
  - `Card Surface`: `#FFFFFF` pure crisp white for tactile contrast against the tinted canvas.
  - `Primary Text`: `#0F172A` deep midnight slate for crisp, readable contrast.
  - `Secondary / Muted Text`: `#64748B` cool slate for secondary descriptors, time stamps, and unit markers.
  - `Subtle Borders`: `#E2E8F0` hairline demarcations for cards, inputs, and segment controls.

## Typography
**Plus Jakarta Sans** powers all hierarchy tiers, delivering a balanced blend of geometric precision and welcoming warmth.

- **Display & Headlines:** Tightly tracked headings (`-0.03em` to `-0.015em`) maintain punchy editorial energy across dashboards and workout summaries.
- **Metric Stat:** A dedicated heavy-weight numerical style (`metric-stat`) guarantees instantaneous visual absorption during active workout motion tracking.
- **Labels & Captions:** Elevated weights (`600`) with neutral-to-positive letter-tracking ensure high legibility on pill badges, telemetry chips, and calendar date markers.

## Layout & Spacing
The layout follows a spacious, modular card-grid architecture that eliminates sidebars in favor of an expansive full-width top navigation bar and dashboard canvas.

### Layout Philosophy
- **Horizontal Top Bar Navigation:** A sticky, full-width glass header hosts identity, main navigation tabs (`Workouts`, `Health`, `Analytics`, `Nutrition`), global search, telemetry status, and profile controls.
- **Modular Fluid Grid:** 
  - **Desktop (12 Columns):** Multi-card distribution supporting quick telemetry stat quads (4 columns of 3 units), featured training plans, and split-screen video/telemetry maps.
  - **Tablet (8 Columns):** Fluid wrap with 2-up stat widgets and stacked workout queues.
  - **Mobile (4 Columns):** Single-column stacked cards with horizontal-scroll carousels for metrics and workout cards.
- **Internal Card Padding:** High internal padding (`space-lg` to `space-xl`) creates breathing room around metrics, charts, and camera viewport previews.

## Elevation & Depth
Depth relies on ultra-diffused, ambient shadows paired with soft boundary borders rather than heavy drop shadows.

### Elevation Levels
- **Canvas Base (`Level 0`):** `#F8FAFC` flat surface.
- **Standard Floating Card (`Level 1`):** Solid `#FFFFFF` fill, bordered with `1px solid #E2E8F0`, elevated by `box-shadow: 0 4px 20px -2px rgba(15, 23, 42, 0.04), 0 2px 6px -1px rgba(15, 23, 42, 0.02)`.
- **Interactive / Hover Card (`Level 2`):** Elevated upon focus or hover with `box-shadow: 0 12px 28px -4px rgba(14, 165, 239, 0.08), 0 4px 12px -2px rgba(15, 23, 42, 0.04)` and a `-2px` Y-axis translation.
- **Active Overlay / Floating Header (`Level 3`):** Semi-transparent `#FFFFFFee` with `backdrop-filter: blur(16px)` and `box-shadow: 0 8px 32px 0 rgba(15, 23, 42, 0.06)`.

## Shapes
This design system embraces hyper-rounded, approachable geometric forms reflecting vitality and modern industrial design:
- **Pill Elements (`rounded-full`):** Used universally for status badges, search bars, interactive tab indicators, metric icon backdrops, and action buttons.
- **Dashboard Modules & Cards (`rounded-3xl` / `1.5rem` to `2rem`):** Large structural containers adopt pronounced corner rounding, eliminating rigid edges.
- **Action Buttons & Media Thumbnails (`rounded-2xl` / `1rem`):** Sits harmoniously between the pill chips and large module frames.

## Components

### Top Navigation Bar
- Completely sidebar-free horizontal bar spanning 100% viewport width with a subtle bottom border (`#E2E8F0`) or frosted glass elevation.
- Active items marked by an athletic electric blue bottom pill stroke or soft tinted pill capsule background (`#0284C7` at 10% opacity with `#0284C7` text).
- Embedded centered or right-aligned unified search bar styled as a wide rounded pill (`#FFFFFF` with `#E2E8F0` border).

### Metric & Telemetry Cards
- Compact, pure white rounded squares/rectangles (`rounded-2xl`) hosting:
  - Top-left or center icon enclosed in an ultra-soft tinted circle (e.g., `#E0F2FE` for blue steps, `#FEF3C7` for calories).
  - Bold prominent metric (`metric-stat`) rendered in `#0F172A`.
  - Subtitle label (`label-md`) in `#64748B`.

### Workout Session Cards
- Vertical or landscape modules with rounded media thumbnails (`rounded-2xl`).
- Accent variations: Default white card with standard border, or primary active training state cloaked in full `#0EA5E9` vibrant gradient with crisp white typography.
- Includes duration chips, workout intensity ratings, and a clear directional forward arrow or "Start" trigger.

### Buttons
- **Primary:** High-radii pill (`rounded-full`) filled with `#0284C7` (or `#0EA5E9`), pure white typography, zero outline, subtle cyan glow on hover.
- **Secondary / Ghost:** White background, `1px solid #E2E8F0`, text `#0F172A`, turning subtly slate on hover (`#F1F5F9`).
- **Icon Quick Action:** Circular (`rounded-full`) button with neutral or tinted background hosting micro-icons for camera, audio, or bookmarking.

### Form Inputs & Date Strips
- **Input Fields:** Soft rounded-full or `rounded-2xl` inputs, `#FFFFFF` fill with `#E2E8F0` border, shifting to `#0EA5E9` stroke with a 3px diffused outer halo on focus.
- **Calendar Ribbon:** Horizontal inline days selector where the current active day is framed inside a prominent blue pill container (`#0EA5E9`) with white text.