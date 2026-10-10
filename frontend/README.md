# Mirage Frontend

Next.js 16 (App Router) web app for Mirage — landing, Scam Fire Drills, Live Call Guardian, Scammer Hunter graph, and the dashboard.

Part of the [Mirage monorepo](../README.md).

## Run it

```bash
npm install
echo "NEXT_PUBLIC_API_URL=http://localhost:8000" > .env.local
npm run dev
# verify: http://localhost:3000
```

The backend must be running (or reachable at `NEXT_PUBLIC_API_URL`) for analysis, drill, guardian, and graph pages. The landing page works standalone.

## Routes

| Route | What it does |
|-------|--------------|
| `/` | Landing — layers overview |
| `/drill` | Scam Fire Drill: pick a scenario, run the simulation, get debriefed + Resilience Score |
| `/guardian` | Live Call Guardian: WebSocket pipeline stages, Memory Handshake, alerts |
| `/graph` | Scammer Hunter: Neo4j-powered weather map of active fraud |
| `/dashboard` | History of drills, scores, evidence |

## Layout

```
src/
├── app/               # App Router pages (all client components)
├── components/
│   ├── ui/            # shadcn/ui primitives
│   ├── hunter/        # Graph weather-map components
│   └── navbar.tsx
└── lib/
    └── api.ts         # typed client for the FastAPI backend
```

## Scripts

```bash
npm run dev    # next dev (Turbopack)
npm run build  # next build
npm run lint   # eslint (flat config, eslint-config-next)
npm run start  # next start
```

## Style

- Tailwind CSS 4; brand emerald is `emerald-400` (`#34d399`), scam red is `destructive`.
- Dark theme by default (`dark` class on `<html>`).
- Extend `components/ui/` primitives rather than forking one-offs.
- Social preview image: `public/og-image.png` (wired via `openGraph`/`twitter` metadata in `src/app/layout.tsx`).

## Deploy

Deployed as a Node web service on Render via the repo-root [`render.yaml`](../render.yaml) blueprint (`npm ci && npm run build` → `npm run start`).
