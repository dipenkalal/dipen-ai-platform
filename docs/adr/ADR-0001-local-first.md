# ADR-0001 — Local First Architecture

## Status

Accepted

---

## Context

Dipen AI Platform (DAP) is designed to provide an AI operating environment that prioritizes user privacy, transparency, and long-term maintainability.

Many modern AI platforms require users to send prompts and private data to cloud-hosted services by default.

DAP takes the opposite approach.

---

## Decision

DAP SHALL use locally hosted AI models as the default execution path.

Cloud AI providers such as OpenAI, Anthropic, or Google MAY be used only after explicit user approval.

No private documents, conversations, or knowledge packs shall be transmitted externally without user confirmation.

---

## Consequences

### Advantages

- Better privacy
- Lower recurring costs
- Offline capability
- User ownership of data

### Disadvantages

- Local models are less capable than frontier cloud models.
- Hardware limitations affect performance.
- Large models may require future upgrades.

---

## Alternatives Considered

Cloud-first architecture

Rejected because it conflicts with the platform's privacy philosophy.

---

## Decision Owner

Dipen Patel

---

Version

1.0