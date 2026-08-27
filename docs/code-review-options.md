# Code-Review-Optionen (ROADMAP Open #4)

Recherche-Stand 2026-08-21 (aus idun-sdk ROADMAP). KEINE Entscheidung — User-Wahl.

## Optionen (Pro/Contra, Termux/self-host priorisiert)

### Qodo Merge (pr-agent, OSS, self-host)
- + OSS, selbst hostbar, PR-Chat-Commands, Auto-Labels.
- + Passt zu "kein SaaS-Zwang".
- - Eigenes Hosting/Token-Management nötig.

### Greptile (SaaS, deep context)
- + Tiefe Repo-Context, gute Reviews.
- - SaaS (Daten verlassen Infra), Kosten.

### Ellipsis (YAML pipeline, self-host-in-VPC)
- + Self-host-in-VPC, Pipeline-as-Code.
- - Setup-Aufwand, VPC nötig.

### Bito (SaaS, agentic)
- + Agentic, viele Integrations.
- - SaaS.

### Codacy (quality+security+AI)
- + Qualität + Security + AI in einem.
- - SaaS, kann teuer werden.

### Self-built CLI LLM review (idun-multi als Engine)
- + Nutzt eigene idun-multi (17 Provider), volle Kontrolle, keine Fremd-Abhängigkeit.
- + Passt zum Projekt (Multi-LLM-Console schon da).
- - Eigenbau-Aufwand, keine fertige PR-UI.
- EMPFEHLUNG: da idun-multi schon alle Provider abdeckt, ist ein self-built
  CLI-Reviewer am synergiereichsten (kein neuer SaaS-Vertrag).

## Empfehlung
Self-built CLI LLM review auf Basis von idun-multi (Kosten: nur LLM-API,
kein neues Tooling). Alternative falls schnell fertig: Qodo Merge (self-host).
User-Entscheidung ausstehend.
