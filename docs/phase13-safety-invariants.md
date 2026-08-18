# Phase 13 Safety Invariants

1. Search discovery is owner-triggered through manual Research Agent mode only.
2. Smart routing cannot activate search discovery.
3. The only search provider is fixed local `searxng-local-v1` on loopback.
4. Search results are URL candidates only, never evidence.
5. At most three candidate URLs proceed to retrieval.
6. Every candidate URL is re-admitted through the complete sealed public retrieval policy.
7. Provider titles/snippets never enter model evidence.
8. No generic model-callable search/HTTP/socket/browser tool is registered.
9. Remote content cannot expand URL scope or select tools.
10. Retrieval does not automatically mutate Knowledge or task truth.
11. Guardian/root/systemd/Docker privilege remains outside Research Agent authority.
12. Credentials, cookies, and browser sessions are not forwarded.
