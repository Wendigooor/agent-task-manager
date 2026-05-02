# Twitter Digest — Project Plan

Fetch tweets from your subscriptions via browser cookies (no API key), filter noise, summarize with LLM, deliver to terminal or Telegram.

## Milestones

| Key | Phase | Status | Tasks |
|-----|-------|--------|-------|
| phase1-core | Core Engine | active | 3 |
| phase2-delivery | Delivery & Summarization | planned | 1 |
| phase3-output | Output Channels | planned | 2 |

## Tasks

### Phase 1: Core Engine
- **TW-001**: Browser cookie extractor — read auth_token from Chrome/Firefox profile
- **TW-002**: Timeline fetcher — pull tweets via Twitter internal GraphQL
- **TW-003**: Noise filter — drop engagement-bait, ads, reply-only tweets

### Phase 2: Delivery & Summarization
- **TW-004**: LLM summarizer — cluster by topic, generate 3-sentence digest per topic

### Phase 3: Output Channels
- **TW-005**: Terminal output — rich-formatted digest with clickable links
- **TW-006**: Telegram bot — scheduled delivery, /now and /schedule commands
