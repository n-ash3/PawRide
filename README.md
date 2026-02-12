# PawRide Backend (Phase 1 Foundation)

Backend API for **PawRide**, a dog-only rideshare platform that supports one iOS app with three switchable roles:

- `dog_parent`
- `driver`
- `admin`

This implementation is a FastAPI monolith with SQLModel persistence and websocket realtime channels.

## What is implemented

### Auth & Role Switching
- Phone OTP auth (`/auth/request-otp`, `/auth/verify-otp`)
- Access + refresh JWT token flow
- Multi-role user model (`user_roles`)
- Active-role switching (`/auth/switch-role`)

### Dog Parent Data
- Dogs CRUD (`/dogs`)
- Trusted receivers CRUD with 6-digit PIN (`/trusted-receivers`)
- Saved destinations CRUD (`/saved-destinations`)

### Rides
- Ride request + fare estimate + lifecycle status transitions
- Cancellation policy:
  - Free in first 2 minutes
  - `$5` en route
  - `$15` once dog is onboard
- Scheduled rides (up to 7 days)
- Recurring rule field support
- Trusted person dropoff verification:
  - PIN + photo-match flag
  - 3 failed attempts trigger lockout
- Facility dropoff verification photo flow
- Ride event timeline (`/rides/{ride_id}/events`)

### Driver
- Become-driver endpoint + onboarding profile shell (`/drivers/become-driver`, `/drivers/me/profile`)
- Online/offline state
- Available-driver query (size + rating + approval aware)
- Earnings summary

### Payments
- Saved payment methods
- Ride charge flow (promo + tip + configurable driver commission split)
- Refund endpoint
- Promo code create endpoint (admin)

### Ratings
- 1–5 star ratings with dog comfort score, comments, and tags

### Admin
- User list + role assignment/removal
- Ride list
- Driver approval queue + decision endpoint
- Basic analytics dashboard stats
- Promo code list

### Camera + Realtime
- Camera stream start/join/end endpoints
- Snapshot + camera alert events
- Websocket channels:
  - `/ws/rides/{ride_id}` for ride status/camera event fan-out
  - `/ws/drivers/{driver_user_id}/location` for location updates

---

## Tech stack

- **FastAPI**
- **SQLModel / SQLAlchemy**
- **SQLite** by default (swap `DATABASE_URL` for Postgres)
- **python-jose** JWT auth

---

## Quick start

### 1) Install dependencies

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

### 2) Configure environment

```bash
cp .env.example .env
```

### 3) Run API

```bash
uvicorn app.main:app --reload
```

Open:
- Swagger UI: `http://127.0.0.1:8000/docs`
- Health: `http://127.0.0.1:8000/health`

---

## Notes for development

- OTP endpoint returns `dev_code` when `ENVIRONMENT != production`.
- New users always get `dog_parent`.
- Additional roles can be attached during OTP verification via `requested_roles`.
- Database tables auto-create on startup.

---

## Ride lifecycle states

`requested -> accepted -> driver_en_route -> arrived_at_pickup -> dog_picked_up -> in_transit -> arrived_at_dropoff -> verifying_receiver -> dog_delivered -> completed`

Cancellation is allowed where appropriate and tracked with reason/fee/timestamp.

---

## Next phase ideas

- Add dispatch engine with driver offer timeouts and expanding search radius
- Real Stripe + Connect integration
- Real media storage + stream orchestration (WebRTC/TURN)
- Push notifications and background jobs
- Production auth hardening and permission granularity
