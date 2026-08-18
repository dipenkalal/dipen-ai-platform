# Phase 13 — Owner Decision Record

The owner delegated the post-Phase-12 decision after the Phase 12J live benchmark returned `provider-specific-activation`.

Decision executed by DAP engineering workflow:

1. Merge the sealed Phase 12 milestone into `main` unchanged.
2. Implement provider-specific activation as a separate post-Phase-12 branch.
3. Use a stricter first activation than the maximum benchmark recommendation:
   - manual Research Agent only;
   - explicit bounded search query only;
   - fixed local SearXNG provider only;
   - no smart-routing search discovery;
   - no generic model-callable search tool;
   - all selected URLs continue through the sealed Phase 12 retrieval/evidence path.
4. Require full CI and live Acer proof before merging the activation branch.

This decision does not authorize arbitrary browsing, private/internal network access, credentials, automatic Knowledge/task mutation, Guardian/root/systemd actions, Docker privilege, or autonomous deployment authority.
