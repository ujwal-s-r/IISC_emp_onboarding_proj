# AdaptIQ frontend

Next.js (App Router) UI for employer setup, live WebSocket streaming, and resume upload.

## Run

1. Start the FastAPI backend (default `http://127.0.0.1:8000`).
2. Copy `.env.example` to `.env.local` if your API is not on that host.
3. `npm install` then `npm run dev` → [http://localhost:3000](http://localhost:3000)

## Pages

- **/** — Split employer (JD + team context) / resume workspace, multipart `setup-role`, and live phase tree from `/ws/employer/setup/{role_id}`.
- **/dashboard** — Lists roles via `GET /api/v1/employer/roles`.

Backend CORS is enabled for `localhost:3000` in `app/main.py`.

## Note on `vite-legacy/`

An older Vite + `src/pages` prototype was moved to `vite-legacy/` because **Next.js treats `src/pages` as the Pages Router** and was bundling it by mistake. The active UI lives under `app/` only.
