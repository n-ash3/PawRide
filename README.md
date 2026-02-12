# PawRide (All Phases Scaffolded)

PawRide is an Uber-style platform focused on safe dog transportation, with:

- **One app** and **three roles** (`dog_parent`, `driver`, `admin`)
- Live in-car camera flow
- Verified dog handoff workflows
- Payments + payouts + promo + subscription hooks
- Real-time dispatch and status updates

---

## ✅ What is implemented (labeled by phase)

## Phase 1 — Backend Foundation

- FastAPI + SQLModel backend
- OTP auth (`/auth/request-otp`, `/auth/verify-otp`)
- Access/refresh token support
- Multi-role users + active role switching
- CRUD: dogs, trusted receivers, saved destinations
- Core ride model and ride lifecycle

## Phase 2 — Ride Matching & Dog Logic

- Dispatch engine with dog-specific matching:
  - max dog size compatibility
  - crate requirement checks from dog profile
  - driver approval/online/rating checks
  - max dogs per ride checks
- Closest-driver offer ordering using latest driver locations
- 15-second driver offer windows
- Radius expansion when no driver accepts
- Scheduled matching lead-time support
- Recurring ride plan generation
- Cancellation fee policy implemented

## Phase 3 — iOS App Shell, Auth, Role Switching

- SwiftUI source scaffold in `ios/PawRide`
- Auth flow + role picker + role switching
- Role-based root routing
- Parent/Driver/Admin tab shells

## Phase 4 — Dog Parent Mode (build scaffold)

- Parent home + ride request form
- Dog list, ride history, payment shell, settings
- Active ride tracking screen with camera/realtime placeholders

## Phase 5 — Driver Mode (build scaffold)

- Driver home with online toggle
- Incoming offer list + accept action
- Earnings, documents, ride history, onboarding, settings screens

## Phase 6 — Live Camera System (backend)

- Stream start/join/end endpoints
- Camera session table with reconnect tracking
- Snapshot + alert events
- Auto snapshot background worker
- Auto stream end on ride completion

## Phase 7 — Payments & Tipping

- Payment methods + charge + refund
- Promo code management
- Driver payout records (weekly + instant payout flow)
- Subscription plan + user subscription endpoints (PawRide Pass)
- Subscription discount applied at charge

## Phase 8 — Admin Mode

- Admin user/role management
- Driver approval workflows
- Ride and dispute management
- Platform settings storage
- Analytics endpoints:
  - overview
  - rides by type
  - peak hours
  - driver utilization
  - rating trends
- Alerts endpoint

## Phase 9 — Notifications & Polish (backend side)

- Notification event queue model
- User notification feed + mark-read endpoints
- Status/camera/dispatch notification creation hooks
- Scheduled ride reminder background task

---

## Project layout

- `app/` → backend API
- `ios/PawRide/` → SwiftUI source scaffold
- `Dockerfile` → containerized backend run/deploy

---

## Run locally (backend)

### 1) Install

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

### 2) Configure

```bash
cp .env.example .env
```

### 3) Start server

```bash
uvicorn app.main:app --reload
```

Open:

- Swagger: `http://127.0.0.1:8000/docs`
- Health: `http://127.0.0.1:8000/health`

---

## Run with Docker

```bash
docker build -t pawride-api .
docker run -p 8000:8000 pawride-api
```

---

## Free online deployment (easy path)

You can run this backend online for free-tier usage with **Render**:

1. Push this repo to GitHub.
2. In Render: **New + → Web Service → connect repo**
3. Runtime: **Docker**
4. Start command is already in `Dockerfile`.
5. Set env vars from `.env.example` (at minimum set `JWT_SECRET`).
6. Deploy and use your Render URL in the iOS app `APIClient.baseURL`.

---

## iOS source usage

1. Open Xcode and create an iOS App project.
2. Copy files from `ios/PawRide/` into project.
3. Point `APIClient.baseURL` to local/online backend URL.
4. Run on simulator/device.

More details: `ios/PawRide/README.md`

---

## Notes

- OTP endpoint returns `dev_code` in non-production for quick testing.
- SQLite is default; set `DATABASE_URL` to Postgres for production.
- Background worker handles dispatch loops, reminders, snapshots, and payout processing.
