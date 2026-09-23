# Policy & Weather Agent — Extended Demo

## Agent Registry + Agent Identity + Auth Manager + Semantic Governance

An extended reference implementation of a **Google Agent Development Kit (ADK)**
agent that demonstrates **eight** Google Agent Platform capabilities in a single
end-to-end walkthrough:

1. **Agent Registry** — register endpoints, agents, and auth bindings as managed resources
2. **Agent Identity: SPIFFE Identity** — per-agent principal minted at deploy time
3. **Agent Identity: Agent Credentials** — (documented, not live-demoed — mTLS/DPoP is transport-layer)
4. **Agent Identity: Auth Manager** — API key stored centrally, transparently injected by ADK
5. **Managed Agent Runtime** — deploy to Vertex AI Agent Engine + register in Gemini Enterprise
6. **Agent Platform Policies: IAM** — 403 failure → IAM binding → success
7. **Agent Platform Policies: Semantic Governance** — NLC rules via Agent Gateway
8. **Agent Observability** — audit logs filtered by SPIFFE principal

---

## What's new vs. the original `agent-identity` demo

| Capability | Original Demo | Extended Demo |
|---|---|---|
| Agent Registry | ❌ Not shown | ✅ Register endpoint + agent + binding |
| Auth Manager | ❌ Not shown | ✅ API Key provider + transparent injection |
| External API | ❌ GCS only | ✅ OpenWeatherMap via AuthenticatedFunctionTool |
| Semantic Governance | ❌ Not shown | ✅ NLC rules via Agent Gateway (Console) |
| Gemini Enterprise | ✅ Shown | ✅ Retained |

---

## Architecture

```
                           ┌──────────────────────────────┐
                           │     Gemini Enterprise app     │
                           │  (Discovery Engine assistant) │
                           └──────────────┬───────────────┘
                                          │ invokes (A2A)
                                          ▼
   ┌───────────────────────────────────────────────────────────────┐
   │                Vertex AI Agent Engine                         │
   │   Reasoning Engine running ADK app (AdkApp)                   │
   │   identity_type = AGENT_IDENTITY  →  per-agent principal      │
   └──────────────┬──────────────────────────┬────────────────────┘
                  │ ADC (auto-signed)        │ Gemini API
                  ▼                          ▼
       ┌──────────────────────┐     ┌──────────────────┐
       │  Google Cloud Storage│     │  gemini-2.5-flash│
       │  gs://<policy-bucket>│     │  (Vertex)        │
       │  policies/*.md       │     └──────────────────┘
       └──────────────────────┘
                  │
                  │  Auth Manager transparently injects API Key
                  ▼
       ┌──────────────────────┐
       │   OpenWeatherMap API │
       │   (external, API Key)│
       └──────────────────────┘

  ┌──────────────────────────────────────────────────────────────────┐
  │  Agent Gateway (egress)                                          │
  │  ┌─────────────────┐  ┌──────────────────┐  ┌────────────────┐  │
  │  │ Agent Registry  │  │ Semantic Gov PEP │  │ Observability │  │
  │  │ (resource lookup)│  │ (NLC evaluation) │  │ (telemetry)   │  │
  │  └─────────────────┘  └──────────────────┘  └────────────────┘  │
  └──────────────────────────────────────────────────────────────────┘
```

---

## Repository layout

```
agent-identity-extended/
├── policy_agent/
│   ├── __init__.py
│   ├── agent.py              # ADK Agent definition (policy + weather tools)
│   ├── gcs_tools.py           # list / search / get policy tools (ADC-backed)
│   ├── external_tools.py     # OpenWeatherMap tool (Auth Manager transparent injection)
│   └── config.py             # env-driven settings + external API config
├── sample_policies/          # 3 markdown policies to seed the bucket
│   ├── acceptable-use.md
│   ├── data-retention.md
│   └── remote-work.md
├── deploy.py                 # deploy to Agent Engine with Agent Identity + Auth Provider
├── register_gemini_enterprise.py  # register as Gemini Enterprise add-on agent
├── local_run.py              # local smoke test (uses your ADC)
├── remote_test.py            # live test against deployed reasoning engine
├── notebooks/
│   └── extended_walkthrough.ipynb  # 4-part extended walkthrough
├── pyproject.toml
├── .env.example
├── .gitignore
└── README.md
```

---

## Quick start

> **Use the notebook:** [`notebooks/extended_walkthrough.ipynb`](notebooks/extended_walkthrough.ipynb)

The notebook runs the full 4-part flow in Google Colab:

- **Part 1** (Steps 1–5): Core demo — SPIFFE identity + IAM (403 → bind → success)
- **Part 2** (Steps 6–12): Agent Registry + Auth Manager — external API with transparent credential injection
- **Part 3** (Steps 13–18): Semantic Governance — NLC rules via Agent Gateway (Console + Colab)
- **Part 4** (Steps 19–21): Observability + cleanup

---

## Prerequisites

- **Google Colab** (recommended) or Python 3.10+ with gcloud SDK
- A Google Cloud project with billing enabled
- An **OpenWeatherMap API key** (free at https://openweathermap.org/api)
- Google Cloud Console access for Semantic Governance NLC configuration

---

## License

MIT — see [LICENSE](LICENSE).
