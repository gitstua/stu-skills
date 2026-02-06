# Design decisions in this project

Thanks to Michael Nygard’s blog post “Documenting Architecture Decisions” (2011)

## 2026-02-06: Per-skill secret files with hidden runtime loading

### Status
Accepted

### Context
Skills need secrets (tokens, private calendar URLs) but secrets should not be pasted into prompts or command arguments where they can be exposed to the LLM context or leaked.

### Decision
Each skill defines a `.env-path` file at the skill root that points to a user-local dotenv file, using this default convention:

- `~/.config/stu-skills/<skill-name>/.env`

Skill scripts load values from that dotenv file at runtime as defaults, while allowing explicit CLI arguments and existing environment variables to override those defaults.

### Consequences
- Secret values stay outside the repo and outside normal prompt/tool argument text.
- Skills have a consistent, discoverable secret location per skill.
- Scripts remain configurable for one-off overrides without changing secret files.

## 2026-02-06: Minimize external binaries for higher-risk operations

### Status
Accepted

### Context
Some skills perform higher-risk activities (for example messaging/notification delivery) where third-party binaries can increase supply-chain and credential-handling risk.

### Decision
Prefer minimal dependencies and avoid introducing external binaries/tools for higher-risk operations unless they are:

- Official tools from the service vendor, or
- High-trust open source dependencies with strong maintenance and reputation.

When possible, use standard platform tooling (for example shell + `curl` + HTTP APIs) and keep the dependency surface small.

### Consequences
- Reduced supply-chain risk for sensitive operations.
- Easier auditing and review of how credentials are used.
- Potentially fewer convenience features compared with larger third-party CLIs.
