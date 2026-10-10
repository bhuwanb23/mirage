# Phase 6 — Frontend Dashboard & Integration (Complete Deep Dive)

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                    MIRAGE WEB APP                           │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐    │
│  │  GLOBAL LAYOUT (app/layout.tsx)                      │    │
│  │  ┌───────┐ ┌──────────────────────────────┐ ┌─────┐ │    │
│  │  │ Logo  │ │ Nav: Dashboard│Drill│Guardian │ │Score│ │    │
│  │  │ 🛡️    │ │      │Graph│Family            │ │  67 │ │    │
│  │  └───────┘ └──────────────────────────────┘ └─────┘ │    │
│  └──────────────────────┬──────────────────────────────┘    │
│                         │                                   │
│  ┌──────────────────────▼──────────────────────────────┐    │
│  │  PAGES                                              │    │
│  │                                                     │    │
│  │  / .............. Landing Page (6.1)                │    │
│  │  /dashboard ...... Dashboard (6.2)                  │    │
│  │  /drill .......... Fire Drill (6.3)                 │    │
│  │  /guardian ....... Live Guardian (6.4)              │    │
│  │  /graph .......... Scam Graph + Map (6.5)           │    │
│  │  /family ......... Family Network (6.6)             │    │
│  │                                                     │    │
│  └─────────────────────────────────────────────────────┘    │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐    │
│  │  SHARED LAYERS                                      │    │
│  │  • Dark mode (bg-gray-950, text-white) (6.7)        │    │
│  │  • Responsive (mobile-first) (6.7)                  │    │
│  │  • API client (lib/api.ts)                          │    │
│  │  • Auth context (lib/auth.ts)                       │    │
│  │  • Toast notifications (sonner)                     │    │
│  │  • Loading skeletons                                │    │
│  └─────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────┘
```

---

## Global Design System

### Color Palette (Tailwind config)

| Token | Value | Usage |
|-------|-------|-------|
| `background` | `#030712` (gray-950) | Page background |
| `surface` | `#111827` (gray-900) | Card backgrounds |
| `surface-hover` | `#1f2937` (gray-800) | Card hover states |
| `border` | `#374151` (gray-700) | Card borders, dividers |
| `border-subtle` | `#1f2937` (gray-800) | Subtle separators |
| `text-primary` | `#f9fafb` (gray-50) | Headings, important text |
| `text-secondary` | `#9ca3af` (gray-400) | Body text, labels |
| `text-muted` | `#6b7280` (gray-500) | Placeholders, hints |
| `accent` | `#3b82f6` (blue-500) | Primary buttons, links |
| `accent-glow` | `#60a5fa` (blue-400) | Glow effects, hover |
| `danger` | `#ef4444` (red-500) | Scam alerts, critical |
| `danger-glow` | `#f87171` (red-400) | Pulsing alerts |
| `warning` | `#f59e0b` (amber-500) | Medium risk |
| `success` | `#22c55e` (green-500) | Safe, verified |
| `info` | `#8b5cf6` (violet-500) | Informational |

### Typography

| Element | Font | Size | Weight | Tailwind |
|---------|------|------|--------|----------|
| Page title | Inter | 36px | Bold | `text-4xl font-bold` |
| Section title | Inter | 24px | Semibold | `text-2xl font-semibold` |
| Card title | Inter | 18px | Semibold | `text-lg font-semibold` |
| Body | Inter | 16px | Regular | `text-base` |
| Small / label | Inter | 14px | Medium | `text-sm font-medium` |
| Caption | Inter | 12px | Regular | `text-xs text-gray-500` |
| Score number | JetBrains Mono | 64px | Bold | `text-6xl font-bold font-mono` |
| Code / data | JetBrains Mono | 14px | Regular | `font-mono text-sm` |

### Spacing System

| Token | Value | Usage |
|-------|-------|-------|
| `page-padding` | 24px (16px mobile) | Page edges |
| `section-gap` | 32px | Between sections |
| `card-gap` | 16px | Between cards in a grid |
| `card-padding` | 24px | Inside cards |
| `content-max-width` | 1280px | Centered content container |

### Component Library (shadcn/ui)

Install these components at the start of Phase 6:

```
npx shadcn@latest add button card badge input textarea dialog
npx shadcn@latest add tabs progress separator skeleton
npx shadcn@latest add dropdown-menu avatar tooltip
npx shadcn@latest add alert alert-dialog scroll-area
npx shadcn@latest add sheet (for mobile nav)
```

---

## 6.1 · Landing Page

### File Location
`frontend/app/page.tsx` + `frontend/components/landing/`

### Purpose
First impression for judges and users. Must communicate the value proposition in < 5 seconds and drive them to try the Fire Drill.

### Page Structure (top to bottom)

---

**Section 1: Hero**

```
┌─────────────────────────────────────────────────────────┐
│                                                         │
│  [Navbar — transparent background, overlaid on hero]    │
│                                                         │
│                                                         │
│            🛡️                                           │
│                                                         │
│     Your Personal AI Immune                             │
│     System Against Scams                                │
│                                                         │
│     We attack you first, so real                        │
│     scammers can't.                                     │
│                                                         │
│     [🔥 Start Your First Fire Drill]  [📱 Try the Bot]  │
│         (primary, large)              (outline)         │
│                                                         │
│     ✓ Free forever    ✓ No app install   ✓ 3 languages  │
│                                                         │
│  [Animated background: subtle shield/pulse animation]   │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

**Hero Animation Details:**

- **Background:** A radial gradient from `blue-900/20` at center to transparent at edges, slowly pulsing (Framer Motion `animate={{ scale: [1, 1.05, 1] }}` with `transition={{ duration: 4, repeat: Infinity }}`)
- **Shield icon:** A large shield SVG (from Lucide `ShieldCheck`) with a subtle glow effect (`shadow-blue-500/30`) that pulses
- **Title animation:** Each word fades in sequentially with a slight upward slide (`initial={{ opacity: 0, y: 20 }}` → `animate={{ opacity: 1, y: 0 }}` with staggered `delay`)
- **Subtitle:** Fades in after the title (`delay: 0.5s`)
- **CTA buttons:** Slide up after subtitle (`delay: 0.8s`)
- **Trust badges:** Fade in last (`delay: 1.1s`)

**CTA Button Behavior:**
- "Start Your First Fire Drill" → `router.push('/drill')` — primary blue button with a flame emoji and subtle hover glow
- "Try the Bot" → opens Telegram bot link in new tab — outline button with a phone emoji

---

**Section 2: Problem Statement**

```
┌─────────────────────────────────────────────────────────┐
│                                                         │
│   The Problem                                           │
│                                                         │
│   ┌───────────┐  ┌───────────┐  ┌───────────┐         │
│   │  ₹7,000Cr │  │  1 in 3   │  │  85%      │         │
│   │  lost to  │  │  Indians  │  │  of scam  │         │
│   │  scams in │  │  targeted │  │  victims  │         │
│   │  India    │  │  in 2024  │  │  are 50+  │         │
│   │  (2024)   │  │           │  │  years old│         │
│   └───────────┘  └───────────┘  └───────────┘         │
│                                                         │
│   Current solutions detect scams AFTER you've been      │
│   targeted. Mirage trains you BEFORE.                   │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

**Animation:** Stats count up from 0 when the section scrolls into view (use `framer-motion` `useInView` hook + `useSpring` for the number animation).

**Stat card styling:**
- Background: `bg-gray-900 border border-gray-800`
- Number: `text-4xl font-bold text-red-400 font-mono`
- Label: `text-sm text-gray-400 mt-2`

---

**Section 3: How It Works (3 steps)**

```
┌─────────────────────────────────────────────────────────┐
│                                                         │
│   How Mirage Protects You                               │
│                                                         │
│   ┌─────────────┐    ┌─────────────┐    ┌─────────────┐│
│   │             │    │             │    │             ││
│   │   🔥 1      │    │   🛡️ 2      │    │   📊 3      ││
│   │             │    │             │    │             ││
│   │  Scam Fire  │    │  Live       │    │  Scam       ││
│   │  Drill      │    │  Guardian   │    │  Intelligence││
│   │             │    │             │    │             ││
│   │  We simulate│    │  Monitors   │    │  Tracks     ││
│   │  a real scam│    │  your calls │    │  scammer    ││
│   │  using YOUR │    │  in real-   │    │  networks   ││
│   │  details so │    │  time and   │    │  and warns  ││
│   │  you learn  │    │  alerts you │    │  your       ││
│   │  to spot    │    │  BEFORE you │    │  community  ││
│   │  the signs. │    │  pay.       │    │             ││
│   │             │    │             │    │             ││
│   │ [Try it →]  │    │ [Try it →]  │    │ [View →]    ││
│   └─────────────┘    └─────────────┘    └─────────────┘│
│                                                         │
└─────────────────────────────────────────────────────────┘
```

**Animation:** Cards slide in from the left with staggered delays (0s, 0.2s, 0.4s) when scrolled into view.

**Card styling:**
- Background: `bg-gray-900/50 border border-gray-800 hover:border-blue-500/50`
- Hover: slight upward lift (`hover:-translate-y-1`) + border glow
- Step number: large, semi-transparent (`text-6xl font-bold text-gray-800 absolute top-2 right-4`)
- Icon: 48px, colored (`text-blue-400`, `text-green-400`, `text-purple-400`)

---

**Section 4: Comparison Table**

```
┌─────────────────────────────────────────────────────────┐
│                                                         │
│   Why Mirage is Different                               │
│                                                         │
│   ┌──────────────────┬───────────────┬───────────────┐  │
│   │                  │ Typical Tool  │ Mirage        │  │
│   ├──────────────────┼───────────────┼───────────────┤  │
│   │ Approach         │ Detects after │ Trains before │  │
│   │ Input types      │ Text only     │ Text, voice,  │  │
│   │                  │               │ image, live   │  │
│   │ Output           │ Verdict only  │ Evidence +    │  │
│   │                  │               │ debrief       │  │
│   │ Personalization  │ Generic       │ Your real     │  │
│   │                  │               │ details       │  │
│   │ Family protect   │ ❌            │ ✅ Alerts     │  │
│   │ Voice clone test │ ❌            │ ✅ Fire Drill │  │
│   └──────────────────┴───────────────┴───────────────┘  │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

**Styling:** Mirage column has a subtle blue highlight (`bg-blue-500/10`). Checkmarks are green, X marks are red.

---

**Section 5: Final CTA**

```
┌─────────────────────────────────────────────────────────┐
│                                                         │
│   Ready to become scam-proof?                           │
│                                                         │
│   [🔥 Start Your First Fire Drill — It takes 2 minutes] │
│                                                         │
│   Free • No signup required • Works on mobile           │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

**Background:** Gradient from `blue-900/30` to `purple-900/20`.

---

**Footer:**

```
┌─────────────────────────────────────────────────────────┐
│  Mirage AI • Built for Forgehacks 2025                  │
│  Report scams: 📞 1930 • 🌐 cybercrime.gov.in          │
│  GitHub • Team • Privacy                                │
└─────────────────────────────────────────────────────────┘
```

### Edge Cases

| Edge Case | Behavior |
|-----------|----------|
| User visits on mobile | Hero text scales down (`text-3xl` → `text-2xl`). Buttons stack vertically. Stats go to a single column. |
| User has slow internet | Framer Motion animations are lightweight (CSS transforms, no heavy JS). If animations fail, content is still readable. |
| User has `prefers-reduced-motion` | Disable all animations. Show static content. Use `motion-reduce:` Tailwind variant. |
| Judge visits the page | The hero + problem statement + comparison table should tell the full story even if they don't scroll further. |

---

## 6.2 · Dashboard

### File Location
`frontend/app/dashboard/page.tsx` + `frontend/components/dashboard/`

### Purpose
The command center. Shows the user's current security posture at a glance and provides quick access to all features.

### Page Layout

```
┌─────────────────────────────────────────────────────────┐
│  Dashboard                                              │
│  Welcome back, Priya 👋                                 │
│                                                         │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐   │
│  │ 🛡️ Score │ │ 🔥 Drills│ │ 🚨 Scams │ │ 👨‍👩‍👧 Family│   │
│  │          │ │          │ │          │ │          │   │
│  │   67     │ │    3     │ │   12     │ │    4     │   │
│  │ /100     │ │ completed│ │ detected │ │ protected│   │
│  │          │ │          │ │          │ │          │   │
│  │ 🟩 +25   │ │ Last: 2h │ │ ↑ 3 today│ │ 1 alert  │   │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘   │
│                                                         │
│  ┌─────────────────────────┐ ┌───────────────────────┐  │
│  │ 📈 Resilience Trend     │ │ 🗺️ Scam Weather       │  │
│  │                         │ │                       │  │
│  │  100│        ╱──●       │ │   [Mini India map     │  │
│  │   75│     ╱──           │ │    with 3-4 hot       │  │
│  │   50│  ╱──              │ │    spots]             │  │
│  │   25│──●                │ │                       │  │
│  │    0│──────────────     │ │   Delhi: 🔴 47        │  │
│  │     D1   D2   D3        │ │   Mumbai: 🟠 38       │  │
│  │                         │ │   Your city: 🟢 Safe  │  │
│  └─────────────────────────┘ └───────────────────────┘  │
│                                                         │
│  ┌─────────────────────────┐ ┌───────────────────────┐  │
│  │ 📋 Recent Activity      │ │ ⚡ Quick Actions       │  │
│  │                         │ │                       │  │
│  │ • Drill: Bank KYC ✅    │ │ [🔥 New Fire Drill]   │  │
│  │   2 hours ago, +25 pts  │ │ [🛡️ Start Guardian]  │  │
│  │                         │ │ [📱 Open Bot]         │  │
│  │ • Scam: UPI Reversal 🚨 │ │ [👨‍👩‍👧 Family Settings] │  │
│  │   5 hours ago, WhatsApp │ │ [📊 View Scam Graph]  │  │
│  │                         │ │                       │  │
│  │ • Alert: Dad received   │ │                       │  │
│  │   bank scam ⚠️          │ │                       │  │
│  │   Yesterday             │ │                       │  │
│  └─────────────────────────┘ └───────────────────────┘  │
└─────────────────────────────────────────────────────────┘
```

### Component Breakdown

**StatCard Component** (`components/dashboard/StatCard.tsx`):

| Prop | Type | Example |
|------|------|---------|
| `title` | string | "Resilience Score" |
| `value` | number | 67 |
| `suffix` | string | "/100" |
| `change` | number | +25 |
| `changeLabel` | string | "from last drill" |
| `icon` | ReactNode | Shield icon |
| `color` | string | "green" |
| `onClick` | function | Navigate to drill page |

**Styling:**
- Card: `bg-gray-900 border border-gray-800 rounded-xl p-6 hover:border-gray-700 transition-all cursor-pointer`
- Value: `text-3xl font-bold font-mono`
- Change indicator: green up arrow for positive, red down arrow for negative
- Icon: top-right corner, semi-transparent (`text-gray-700`)

**ResilienceChart Component** (`components/dashboard/ResilienceChart.tsx`):

- Library: Recharts `AreaChart`
- Data: Array of `{drill_number, score, date}` from `GET /drill/score/{user_id}`
- X-axis: Drill number or date
- Y-axis: Score 0–100
- Area fill: gradient from `blue-500/30` to transparent
- Line: `blue-400`, 2px width
- Reference line at y=50: dashed gray, labeled "Minimum Safe"
- Tooltip: shows score and date on hover
- Animation: line draws from left to right on mount

**ScamWeatherWidget Component** (`components/dashboard/ScamWeatherWidget.tsx`):

- A mini version of the full map from Phase 5
- Shows only the top 3 cities + user's city
- No interactive Leaflet — just a static styled list with colored dots
- "View Full Map →" link to `/graph`

**RecentActivity Component** (`components/dashboard/RecentActivity.tsx`):

- List of the 5 most recent events (drills, scam reports, family alerts)
- Each item: icon + description + timestamp
- Color-coded by type:
  - Drill completed: green
  - Scam detected: red
  - Family alert: amber
  - Guardian session: blue
- "View All →" link (stretch goal: `/activity` page)

**QuickActions Component** (`components/dashboard/QuickActions.tsx`):

- Grid of 4–5 action buttons
- Each: icon + label + one-line description
- Primary action (Fire Drill) is larger and blue
- Others are outline/ghost style

### Data Fetching

**On page load, fetch in parallel:**
1. `GET /drill/score/{user_id}` → Resilience score + history
2. `GET /drill/history/{user_id}?limit=5` → Recent drills
3. `GET /analyze/recent?limit=5` → Recent scam reports
4. `GET /family/status/{user_id}` → Family member count + recent alerts
5. `GET /map/heatmap` → Scam weather data (top 3 cities only)

**Loading state:** Show skeleton placeholders for each card while data loads. Use `next/dynamic` or React Suspense for streaming.

**Error state:** If an API call fails, show the card with "Data unavailable" and a retry button. Don't block the entire page.

### Edge Cases

| Edge Case | Behavior |
|-----------|----------|
| New user (no data) | Show empty states: "No drills yet — start your first one!" Score card shows 0 with "Beginner" label. Activity feed shows "No activity yet." |
| User has done 50+ drills | Chart shows last 10 drills only. Add a "View Full History" link. |
| API is slow | Show skeletons for 3 seconds. If still loading, show "Loading..." with a spinner. |
| User is on mobile | Stat cards go to 2×2 grid. Chart and map stack vertically. Quick actions become a horizontal scroll. |

---

## 6.3 · Drill Page

### File Location
`frontend/app/drill/page.tsx`

### Purpose
The full Fire Drill experience. This page integrates all the components built in Phase 3 into a seamless multi-step flow.

### Page Structure

The drill page is a **state machine** with 5 states:

```
SETUP → GENERATING → ACTIVE → DEBRIEF → SCORE
```

**State: SETUP**
- Shows the `DrillSetup` component (profile form + scam type selector)
- User fills in details and clicks "Start Fire Drill"
- Transition: `SETUP → GENERATING`

**State: GENERATING**
- Shows a loading screen: "🔥 Generating your personalized scam call..."
- Animated spinner + progress steps:
  1. "Analyzing your profile..." (1s)
  2. "Crafting the scam script..." (2s)
  3. "Cloning the voice..." (3s)
  4. "Preparing the call..." (1s)
- Behind the scenes: calls `POST /drill/generate-script` and `POST /drill/synthesize-voice`
- For demo: use pre-generated audio, so this takes < 2 seconds
- Transition: `GENERATING → ACTIVE` (when audio is ready)

**State: ACTIVE**
- Shows the `DrillPlayer` component (phone call UI)
- Plays the scam audio, tracks timer, waits for user input
- Transition: `ACTIVE → DEBRIEF` (when user clicks a button or audio ends)

**State: DEBRIEF**
- Shows the `DrillDebrief` component
- Displays the personalized debrief with stages caught/missed
- "Continue to Score →" button
- Transition: `DEBRIEF → SCORE`

**State: SCORE**
- Shows the `ScoreCard` and `ScoreChart` components
- Animated score update
- "Try Another Drill" and "Back to Dashboard" buttons
- Transition: `SCORE → SETUP` (if user wants another drill)

### State Management

Use React `useState` for the current state and `useReducer` for the drill data:

```
DrillState:
  phase: "setup" | "generating" | "active" | "debrief" | "score"
  profile: UserProfile | null
  scamType: string | null
  difficulty: string | null
  scriptId: string | null
  audioUrl: string | null
  userAction: string | null
  reactionTime: number | null
  debrief: DebriefResult | null
  scoreBefore: number | null
  scoreAfter: number | null
```

### Mobile Considerations

- The drill player must work on mobile (judges will try it)
- Audio autoplay is blocked on mobile until first user interaction — the "Start Fire Drill" button counts
- Buttons must be at least 48px tall for touch targets
- The phone call UI should look like a real mobile call screen (full-width, centered)

---

## 6.4 · Guardian Page

### File Location
`frontend/app/guardian/page.tsx`

### Purpose
The live call monitoring dashboard. Integrates all components from Phase 4.

### Page Structure

**Before starting (idle state):**

```
┌─────────────────────────────────────────────────────────┐
│  🛡️ Live Call Guardian                                  │
│                                                         │
│  Real-time scam detection for your phone calls.         │
│                                                         │
│  How it works:                                          │
│  1. Click "Start Listening"                             │
│  2. Put your phone call on speaker                      │
│  3. Mirage listens and alerts you if it detects a scam  │
│                                                         │
│  ⚠️ Your audio is processed in real-time and never      │
│  stored. All analysis happens on-device + secure API.   │
│                                                         │
│  [🎙️ Start Listening]                                   │
│                                                         │
│  💡 Tip: Works best in a quiet room with the phone      │
│  on speakerphone near your laptop microphone.           │
└─────────────────────────────────────────────────────────┘
```

**During active monitoring:**
- Full Guardian dashboard as described in Phase 4 (4.3)
- The layout uses CSS Grid:
  - Desktop: 2-column layout (transcript left, stages + alerts right)
  - Mobile: single column, stages at top (sticky), transcript below

**After stopping (summary state):**

```
┌─────────────────────────────────────────────────────────┐
│  📋 Call Summary                                        │
│                                                         │
│  Duration: 2:34                                         │
│  Highest Stage: Urgency ⚠️                              │
│  Voice Authenticity: 72% (Likely AI) 🟥                 │
│  Verdict: Likely Scam                                   │
│                                                         │
│  Stages Detected:                                       │
│  ✅ Hook (0:02)                                         │
│  ✅ Authority (0:08)                                    │
│  ✅ Isolation (0:22)                                    │
│  ✅ Urgency (0:40)                                      │
│  ❌ Payment (not reached)                               │
│                                                         │
│  [📄 Generate Report]  [🏠 Dashboard]  [🔄 New Call]    │
└─────────────────────────────────────────────────────────┘
```

### State Management

```
GuardianState:
  status: "idle" | "requesting_mic" | "listening" | "reconnecting" | "stopped"
  transcript: Array<{timestamp, text}>
  currentStage: string
  alertLevel: string
  alertMessage: string | null
  voiceScore: number | null
  callDuration: number
  stageTimestamps: Record<string, number>
  memoryHandshakeTriggered: boolean
```

---

## 6.5 · Graph Page

### File Location
`frontend/app/graph/page.tsx`

### Purpose
Displays the Scam Graph and Weather Map side by side. Integrates components from Phase 5.

### Page Layout

**Desktop (≥ 1024px):**

```
┌─────────────────────────────────────────────────────────┐
│  📊 Scam Intelligence                                   │
│                                                         │
│  ┌──────────────────────────┐ ┌──────────────────────┐  │
│  │                          │ │                      │  │
│  │   SCAM GRAPH             │ │  SCAM WEATHER MAP    │  │
│  │   (60% width)            │ │  (40% width)         │  │
│  │                          │ │                      │  │
│  │   [Force-directed graph  │ │  [Leaflet map of     │  │
│  │    with colored nodes    │ │   India with heat    │  │
│  │    and edges]            │ │   markers]           │  │
│  │                          │ │                      │  │
│  │   Stats:                 │ │  Top cities:         │  │
│  │   156 numbers tracked    │ │  🔴 Delhi: 47        │  │
│  │   23 UPI IDs             │ │  🟠 Mumbai: 38       │  │
│  │   8 rings detected       │ │  🔵 Bangalore: 29    │  │
│  │                          │ │                      │  │
│  └──────────────────────────┘ └──────────────────────┘  │
│                                                         │
│  ┌──────────────────────────────────────────────────┐   │
│  │  📋 IOC Table                                     │   │
│  │                                                   │   │
│  │  Type    │ Value           │ First Seen │ Risk    │   │
│  │  Phone   │ 98765-43210     │ 10 Jan     │ 🔴 High │   │
│  │  UPI     │ sbi-safe@ybl    │ 12 Jan     │ 🔴 High │   │
│  │  Domain  │ sbi-kyc-verify  │ 11 Jan     │ 🟠 Med  │   │
│  │  ...     │ ...             │ ...        │ ...     │   │
│  └──────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────┘
```

**Mobile (< 768px):**
- Tabs at the top: "Graph" | "Map" | "Table"
- Show one view at a time
- Graph is simplified (fewer nodes, no force simulation — static layout)

### Tab System (for mobile)

Use shadcn/ui `Tabs` component:
```
<Tabs defaultValue="graph">
  <TabsList>
    <TabsTrigger value="graph">🕸️ Graph</TabsTrigger>
    <TabsTrigger value="map">🗺️ Map</TabsTrigger>
    <TabsTrigger value="table">📋 Data</TabsTrigger>
  </TabsList>
  <TabsContent value="graph"><ScamGraph /></TabsContent>
  <TabsContent value="map"><ScamWeatherMap /></TabsContent>
  <TabsContent value="table"><IOCTable /></TabsContent>
</Tabs>
```

### Data Fetching

- `GET /graph/data?limit=200` → nodes and edges for the graph
- `GET /graph/stats` → aggregate numbers
- `GET /map/heatmap` → city data for the map
- Fetch on mount, cache for 5 minutes (scam data doesn't change rapidly)

---

## 6.6 · Family Network Page

### File Location
`frontend/app/family/page.tsx` + `frontend/components/family/`

### Purpose
Manage family protection settings — add members, set up Memory Handshake secrets, view alert history.

### Page Layout

```
┌─────────────────────────────────────────────────────────┐
│  👨‍👩‍👧‍👦 Family Protection Network                         │
│                                                         │
│  ┌─────────────────────────┐ ┌───────────────────────┐  │
│  │  👥 Family Group        │ │  🔐 Memory Handshake  │  │
│  │                         │ │                       │  │
│  │  Group: Sharma Family   │ │  Challenge Questions: │  │
│  │  Code: A7X-9K2 [Copy]   │ │                       │  │
│  │                         │ │  1. What's our dog's  │  │
│  │  Members:               │ │     name? ✅ Set      │  │
│  │  • Priya (you) 👑 Admin │ │  2. What street did   │  │
│  │  • Dad (Ramesh) ✅      │ │     we grow up on?    │  │
│  │  • Mom (Sunita) ✅      │ │     ✅ Set            │  │
│  │  • Brother (Rahul) ⏳   │ │  3. Mom's middle      │  │
│  │    (pending invite)     │ │     name? ❌ Not set  │  │
│  │                         │ │                       │  │
│  │  [Invite Member]        │ │  [Edit Questions]     │  │
│  └─────────────────────────┘ │                       │  │
│                              │  Family Code:         │  │
│  ┌─────────────────────────┐ │  4 8 2 9 1 7          │  │
│  │  📢 Recent Alerts       │ │  Refreshes in: 3:42   │  │
│  │                         │ │                       │  │
│  │  🚨 Dad received bank   │ └───────────────────────┘  │
│  │     KYC scam            │                           │
│  │     2 hours ago         │                           │
│  │     Confidence: 92%     │                           │
│  │     Action: Alerted ✅  │                           │
│  │                         │                           │
│  │  ⚠️ Mom received        │                           │
│  │     lottery scam        │                           │
│  │     Yesterday           │                           │
│  │     Confidence: 78%     │                           │
│  │     Action: Alerted ✅  │                           │
│  │                         │                           │
│  │  [View All Alerts]      │                           │
│  └─────────────────────────┘                           │
└─────────────────────────────────────────────────────────┘
```

### Components

**FamilyGroupCard:**
- Shows group name, invite code, member list
- Each member: avatar + name + status (active/pending) + role badge
- "Invite Member" button opens a dialog with the invite code and instructions
- Admin can remove members or change roles

**MemoryHandshakeSetup:**
- List of 3 challenge questions with status (set/not set)
- "Edit Questions" opens a dialog with the form from Phase 4 (4.5)
- TOTP code display with countdown timer
- "Share Code" button copies the current TOTP to clipboard

**AlertHistory:**
- Chronological list of family scam alerts
- Each alert: severity icon + who received it + scam type + timestamp + confidence
- Click an alert to expand: shows full verdict and evidence
- Filter by member or scam type (stretch goal)

### Data Fetching

- `GET /family/group/{user_id}` → group details + members
- `GET /memory/secrets/{group_id}` → question status (not the answers!)
- `GET /memory/totp/{group_id}` → current TOTP code
- `GET /family/alerts/{group_id}?limit=10` → recent alerts

### Edge Cases

| Edge Case | Behavior |
|-----------|----------|
| User hasn't created a family group | Show onboarding: "Create a family group to protect your loved ones." with a setup wizard. |
| No family members have joined | Show: "Share this invite code with your family. They can join by opening Mirage and entering the code." |
| Memory Handshake not set up | Show a prominent CTA: "🔐 Set up Memory Handshake to verify caller identity during suspicious calls." |
| User is the only member | All features work, but alerts have nowhere to go. Prompt to add members. |

---

## 6.7 · Responsive + Dark Mode

### File Location
`frontend/app/layout.tsx` + `frontend/tailwind.config.ts` + `frontend/app/globals.css`

### Dark Mode Configuration

**Strategy:** Dark mode by default (not toggle-based). This is a cybersecurity tool — dark theme is expected.

**Implementation:**
- Add `dark` class to `<html>` tag in `layout.tsx`
- Set `darkMode: "class"` in `tailwind.config.ts`
- All components use dark-first colors:
  - Backgrounds: `bg-gray-950`, `bg-gray-900`
  - Text: `text-white`, `text-gray-400`
  - Borders: `border-gray-800`
- No light mode toggle needed for the hackathon

**CSS Variables (globals.css):**
```css
:root {
  --background: 0 0% 2%;      /* gray-950 */
  --foreground: 0 0% 98%;     /* gray-50 */
  --card: 0 0% 7%;            /* gray-900 */
  --card-foreground: 0 0% 98%;
  --primary: 217 91% 60%;     /* blue-500 */
  --destructive: 0 84% 60%;   /* red-500 */
  --muted: 0 0% 15%;          /* gray-800 */
  --accent: 217 91% 60%;
  --border: 0 0% 22%;         /* gray-700 */
  --ring: 217 91% 60%;
}
```

### Responsive Breakpoints

| Breakpoint | Width | Layout Changes |
|-----------|-------|---------------|
| Mobile | < 640px | Single column. Hamburger nav. Stacked cards. Full-width buttons. |
| Tablet | 640–1023px | 2-column grids. Side nav collapses to icons. |
| Desktop | ≥ 1024px | Full layout. 3–4 column grids. Side-by-side panels. |

### Mobile Navigation

**Desktop:** Horizontal nav bar at the top with text links.

**Mobile:** Hamburger menu (shadcn/ui `Sheet` component):
```
☰  🛡️ Mirage              [67]
─────────────────────
  📊 Dashboard
  🔥 Fire Drill
  🛡️ Guardian
  🕸️ Scam Graph
  👨‍👩‍👧‍👦 Family
─────────────────────
  📱 Telegram Bot
  📞 Report: 1930
```

### Responsive Grid Patterns

**Stat cards:**
- Mobile: 2×2 grid (`grid-cols-2`)
- Tablet: 4×1 grid (`grid-cols-4`)
- Desktop: 4×1 grid (`grid-cols-4`)

**Dashboard main content:**
- Mobile: single column (`grid-cols-1`)
- Desktop: 2 columns (`grid-cols-2`), chart takes 60%, map takes 40%

**Drill page:**
- Mobile: full-width, stacked
- Desktop: centered, max-width 600px

**Guardian page:**
- Mobile: stages at top (sticky), transcript below, alerts overlay
- Desktop: 2-column grid

**Graph page:**
- Mobile: tabs (Graph | Map | Table)
- Desktop: side-by-side (60/40 split)

### Performance Optimizations

| Optimization | How |
|-------------|-----|
| Image optimization | Use Next.js `<Image>` component with `loading="lazy"` |
| Font loading | Use `next/font` for Inter and JetBrains Mono (self-hosted, no FOUT) |
| Bundle splitting | Dynamic imports for heavy components: `dynamic(() => import('./ScamGraph'))` |
| Leaflet | Only load on the `/graph` page, not globally |
| Recharts | Only load on `/dashboard` and `/drill` |
| Animations | Use CSS animations where possible (Framer Motion is JS-heavy) |
| API caching | Use SWR or React Query for client-side caching |

### Accessibility

| Requirement | Implementation |
|-------------|---------------|
| Color contrast | All text meets WCAG AA (4.5:1 ratio). Gray-400 on gray-950 = 7.2:1 ✅ |
| Focus indicators | Visible focus rings on all interactive elements (`focus:ring-2 focus:ring-blue-500`) |
| Keyboard navigation | All buttons and links accessible via Tab. Drill player has keyboard shortcuts. |
| Screen readers | ARIA labels on icons, alt text on images, `role="alert"` on scam warnings |
| Reduced motion | `@media (prefers-reduced-motion: reduce)` disables all animations |

---

## Navigation Structure

### Navbar Component (`components/Navbar.tsx`)

**Desktop:**
```
┌─────────────────────────────────────────────────────────┐
│  🛡️ Mirage    Dashboard  Fire Drill  Guardian  Graph    │
│                                          Family   [67] │
└─────────────────────────────────────────────────────────┘
```

**Styling:**
- Background: `bg-gray-950/80 backdrop-blur-md border-b border-gray-800`
- Sticky at top (`sticky top-0 z-50`)
- Active page: `text-blue-400 border-b-2 border-blue-400`
- Inactive: `text-gray-400 hover:text-white`
- Score badge: `bg-blue-500/20 text-blue-400 px-3 py-1 rounded-full text-sm font-mono`

### Page Transitions

Use Framer Motion `AnimatePresence` for page transitions:
- Fade + slight slide up on enter (`initial={{ opacity: 0, y: 10 }}` → `animate={{ opacity: 1, y: 0 }}`)
- Duration: 200ms
- This makes the app feel polished without being distracting

---

## Global Components

### Loading Skeleton (`components/Skeleton.tsx`)

Use shadcn/ui `Skeleton` for all loading states:
```
┌─────────────────────┐
│  ░░░░░░░░░░░░░░░░  │  ← pulsing gray rectangle
│  ░░░░░░░░░░        │
│  ░░░░░░░░░░░░░░    │
└─────────────────────┘
```

### Toast Notifications (`lib/toast.ts`)

Use `sonner` (lightweight toast library, works with shadcn):
- Success: "✅ Drill completed! Score: 67" (green)
- Error: "❌ Analysis failed. Try again." (red)
- Warning: "⚠️ High-risk scam detected!" (amber)
- Info: "🔄 Guardian reconnected." (blue)

### Error Boundary (`components/ErrorBoundary.tsx`)

Wrap each page in an error boundary:
- If a component crashes, show: "Something went wrong. [Retry] [Go to Dashboard]"
- Log the error to console for debugging
- Never show a white screen of death

---

## File Summary for Phase 6

| File | Purpose | Lines (estimate) |
|------|---------|-----------------|
| `frontend/app/layout.tsx` | Root layout, nav, dark mode | ~80 |
| `frontend/app/globals.css` | CSS variables, global styles | ~60 |
| `frontend/tailwind.config.ts` | Custom colors, fonts | ~40 |
| `frontend/app/page.tsx` | Landing page | ~200 |
| `frontend/components/landing/Hero.tsx` | Hero section | ~100 |
| `frontend/components/landing/ProblemStats.tsx` | Problem statistics | ~80 |
| `frontend/components/landing/HowItWorks.tsx` | 3-step explanation | ~80 |
| `frontend/components/landing/Comparison.tsx` | Comparison table | ~60 |
| `frontend/app/dashboard/page.tsx` | Dashboard page | ~120 |
| `frontend/components/dashboard/StatCard.tsx` | Stat card component | ~50 |
| `frontend/components/dashboard/ResilienceChart.tsx` | Score trend chart | ~80 |
| `frontend/components/dashboard/RecentActivity.tsx` | Activity feed | ~80 |
| `frontend/components/dashboard/QuickActions.tsx` | Action buttons | ~60 |
| `frontend/app/drill/page.tsx` | Drill page (state machine) | ~150 |
| `frontend/app/guardian/page.tsx` | Guardian page | ~120 |
| `frontend/app/graph/page.tsx` | Graph + Map page | ~80 |
| `frontend/app/family/page.tsx` | Family network page | ~120 |
| `frontend/components/family/FamilyGroup.tsx` | Group management | ~100 |
| `frontend/components/family/AlertHistory.tsx` | Alert list | ~80 |
| `frontend/components/Navbar.tsx` | Navigation bar | ~80 |
| `frontend/components/MobileNav.tsx` | Mobile hamburger menu | ~60 |
| `frontend/lib/api.ts` | API client (enhanced) | ~80 |
| `frontend/lib/auth.ts` | Simple user context | ~60 |

**Total estimated:** ~1,950 lines of TypeScript/React

---

## Phase 6 Completion Checklist

```
□ Landing page hero loads with animations
□ Landing page problem stats count up on scroll
□ Landing page "How It Works" cards animate in
□ Landing page comparison table highlights Mirage column
□ Landing page CTAs link to /drill and Telegram bot
□ Landing page is responsive on mobile
□ Dashboard shows 4 stat cards with real data
□ Dashboard resilience chart renders with Recharts
□ Dashboard scam weather widget shows top 3 cities
□ Dashboard recent activity feed shows last 5 events
□ Dashboard quick actions navigate to correct pages
□ Dashboard shows empty states for new users
□ Drill page flows through all 5 states (setup → score)
□ Drill page loading screen shows progress steps
□ Drill page works on mobile with touch targets
□ Guardian page shows idle → active → summary states
□ Guardian page mic permission flow works
□ Guardian page WebSocket connects and streams
□ Graph page shows force-directed graph with colored nodes
□ Graph page shows Leaflet map with heat markers
□ Graph page shows IOC table with sortable columns
□ Graph page mobile tabs switch between views
□ Family page shows group details and member list
□ Family page shows Memory Handshake setup status
□ Family page shows TOTP code with countdown
□ Family page shows alert history
□ Family page shows onboarding for new users
□ Navbar is sticky with active page indicator
□ Mobile hamburger menu works
□ Dark mode is applied globally (no white flashes)
□ All pages are responsive (mobile, tablet, desktop)
□ Loading skeletons show during data fetching
□ Toast notifications appear for success/error events
□ Error boundaries catch crashes gracefully
□ Page transitions are smooth (fade + slide)
□ All interactive elements have focus indicators
□ All icons have ARIA labels
□ Font loading uses next/font (no FOUT)
□ Heavy components are dynamically imported
□ Full app navigation works end-to-end without errors
```

**When every box is checked, Phase 6 is done. Your app is polished and cohesive. Move to Phase 7 (Demo & Pitch) to prepare for the presentation.**

---

Ready for the final phase — Phase 7 (Demo Polish & Pitch)? This is where you rehearse, prepare backups, and craft the winning presentation. Say the word.