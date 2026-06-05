# Stockie AI — Frontend

Next.js 14 app for the Stockie AI dashboard — charts, analysis views, and recommendations UI.

> See the root [`README.md`](../README.md) for full-stack quick-start instructions.

---

## Stack

- **Next.js 14** (App Router) + **TypeScript**
- **Tailwind CSS** v3 — utility-first styling
- **shadcn/ui** — accessible component library (base-ui primitives + CVA)
- **openapi-fetch** — typed HTTP client generated from the FastAPI OpenAPI spec
- **ESLint** + **Prettier** — lint and formatting

---

## Setup

```bash
# From the frontend/ directory
npm install

# Copy env file (backend URL)
cp .env.example .env.local
```

---

## Running the dev server

```bash
npm run dev   # →  http://localhost:3000
```

The backend must be running for the landing page health card to show live data.

---

## Environment variables

| Variable              | Default                 | Description                     |
| --------------------- | ----------------------- | ------------------------------- |
| `NEXT_PUBLIC_API_URL` | `http://localhost:8000` | Base URL of the FastAPI backend |

---

## Available scripts

| Script                 | What it does                                         |
| ---------------------- | ---------------------------------------------------- |
| `npm run dev`          | Start dev server with hot reload                     |
| `npm run build`        | Production build                                     |
| `npm run start`        | Serve the production build                           |
| `npm run lint`         | ESLint across all files                              |
| `npm run format`       | Prettier — auto-fix all files                        |
| `npm run format:check` | Prettier — check without writing                     |
| `npm run generate`     | Regenerate TypeScript types from `GET /openapi.json` |

---

## Typed API client

The API client lives in `lib/api/` and is generated from the live backend spec.

```bash
# Regenerate after the backend adds or changes endpoints (backend must be running)
npm run generate
```

Usage anywhere in the app:

```ts
import { apiClient } from "@/lib/api";

const { data, error } = await apiClient.GET("/health");
// data is fully typed as { status: string; version: string; ... }
```

`lib/api/schema.d.ts` is auto-generated — never edit it by hand.

---

## Adding shadcn/ui components

```bash
# Example: add a Card component
npx shadcn@latest add card
```

Components are installed into `components/ui/`. Add the file header (per `CLAUDE.md`) after installation.

---

## Linting and type-checking

```bash
npm run lint           # ESLint
npm run format:check   # Prettier
npx tsc --noEmit       # TypeScript
```

All three must pass before opening a PR — CI enforces this automatically.

---

## Project layout

```
frontend/
├── app/
│   ├── globals.css          # Tailwind + shadcn CSS custom properties
│   ├── layout.tsx           # Root layout — fonts, metadata
│   └── page.tsx             # Sprint 0 landing page (calls /health)
├── components/
│   ├── health-status.tsx    # Async server component — backend status card
│   └── ui/
│       └── button.tsx       # shadcn/ui Button (CVA variants)
├── lib/
│   ├── api/
│   │   ├── schema.d.ts      # AUTO-GENERATED — do not edit
│   │   ├── client.ts        # apiClient singleton
│   │   └── index.ts         # Public barrel export
│   └── utils.ts             # cn() Tailwind merge helper
├── types/
│   └── css.d.ts             # Ambient CSS module declaration
├── .env.example
├── .eslintrc.json
├── .prettierrc
└── tailwind.config.ts
```
