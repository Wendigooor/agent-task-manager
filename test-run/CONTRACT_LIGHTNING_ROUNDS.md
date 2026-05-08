# Lightning Rounds — Timed Tournament Boost Feature Contract

Version: 2026-05-08
Mode: Demo
Run id: lightning-rounds

## Mission

Deliver `Lightning Rounds` — randomly spawning 5-minute tournaments where all scores are multiplied by 3x. Player sees a countdown, joins, plays spins with boosted scoring, and sees the multiplier impact on rank.

## Product Story

> A player is playing normally when a notification appears: "⚡ LIGHTNING ROUND — 3x SCORE BOOST — 4:59 remaining". They join, play spins during the window, their points are tripled, and they climb the leaderboard before the round ends.

## Core Loop

1. Lightning Round spawns automatically (or via seed for demo)
2. Player sees countdown + 3x multiplier banner
3. Player joins through UI
4. Player plays spins — each spin scores 3x normal points
5. Timer counts down
6. Round ends — final rank is locked
7. Player sees boost impact on score

## Backend

- `lightning_rounds` table: id, status (active/ended), starts_at, ends_at, multiplier (3), created_at
- `lightning_round_entries`: id, round_id, user_id, joined_at, score
- Auto-end: timer expiry sets status = 'ended'
- Scoring: points = (wagered + won*2 + spins*10) * multiplier
- API: GET /api/v1/lightning/active, POST /api/v1/lightning/:id/join, GET /api/v1/lightning/:id/leaderboard

## Frontend

- New route: `/lightning` or integrated into `/tournaments`
- Banner: "⚡ LIGHTNING ROUND — 3x SCORE — 4:59 left"
- Join CTA, countdown, live leaderboard, multiplier badge
- data-page="lightning", data-state="active|joined|boosted|ended"

## E2E

7 screenshots:
1. Lightning round active (banner, countdown, join CTA)
2. Joined state (multiplier badge, initial rank)
3. Spins during round (score boosted 3x)
4. Timer below 1 minute (urgency)
5. Round ended (final rank, score)
6. Comparison: normal score vs boosted score
7. Mobile view

## Scoring

Minimum: 84/100
