# Mirage Documentation

Everything worth reading about why Mirage exists, how it's built, and how to run it. Start with the [root README](../README.md) for the quick start.

## Idea & strategy

- [`idea/idea.md`](idea/idea.md) — the problem, the insight, why "vaccine" not "detector"
- [`idea/tech_stack.md`](idea/tech_stack.md) — strategic technology choices and trade-offs

## Plans & roadmap

- [`plans/master_plan.md`](plans/master_plan.md) — Phase 0–7 roadmap and dependency tree
- [`plans/phase_0.md`](plans/phase_0.md) — foundation phase design
- [`plans/phase_0_checklist.md`](plans/phase_0_checklist.md) — known gaps and verification log

## Engineering

- [`api_contracts.md`](api_contracts.md) — HTTP/WS contracts with request/response JSON examples
- [`deploy.md`](deploy.md) — production deploy: Supabase → Neo4j → LLM keys → Render

## Assets

| Path | Contents |
|------|----------|
| [`assets/brand/`](assets/brand/) | `logo.svg`, `logo.png`, `banner.jpg` |
| [`assets/diagrams/`](assets/diagrams/) | Architecture, guardian pipeline, hunter flow — Mermaid sources (`.mmd`) + rendered PNGs |
| [`assets/screenshots/`](assets/screenshots/) | Product screenshots (landing, drill, guardian, graph, dashboard) |

Diagrams are authored in Mermaid. To edit one, change the `.mmd` and re-render:

```bash
npx @mermaid-js/mermaid-cli \
  -i docs/assets/diagrams/<name>.mmd \
  -o docs/assets/diagrams/<name>.png \
  -b "#0a0a0a" --size 1400 -s 2
```

## Related

- [CONTRIBUTING.md](../CONTRIBUTING.md) — setup, style, PR guidelines
- [SECURITY.md](../SECURITY.md) — private vulnerability reporting
- [CHANGELOG.md](../CHANGELOG.md) — what shipped
