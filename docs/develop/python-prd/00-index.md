# OpenGame Python Version — Product Requirements Document

**Version**: 1.0  
**Date**: 2026-05-28  
**Status**: Draft  
**Target**: OpenGame v0.6.0 parity (TypeScript → Python port)

---

## Document Index

This PRD is organized as a collection of self-contained documents. Each file contains all necessary context, data structures, and interface definitions without requiring cross-referencing.

| # | File | Description |
|---|------|-------------|
| 1 | [01-overview.md](./01-overview.md) | Project goals, scope, success criteria |
| 2 | [02-architecture.md](./02-architecture.md) | System architecture, package layout, tech stack |
| 3 | [03-data-models.md](./03-data-models.md) | All Pydantic data models — completely self-contained |
| 4 | [04-agent-runtime.md](./04-agent-runtime.md) | Turn loop, tool system, LLM clients |
| 5 | [05-template-skill.md](./05-template-skill.md) | Template Skill: classify, extract, abstract, merge, evolve |
| 6 | [06-debug-skill.md](./06-debug-skill.md) | Debug Skill: Algorithm 1, diagnose, repair, evolve protocol |
| 7 | [07-game-skill-orchestrator.md](./07-game-skill-orchestrator.md) | 6-phase game generation orchestrator |
| 8 | [08-asset-pipeline.md](./08-asset-pipeline.md) | Image, audio, video asset generation |
| 9 | [09-bench.md](./09-bench.md) | OpenGame-Bench evaluation pipeline |
| 10 | [10-tools-reference.md](./10-tools-reference.md) | Complete tool catalog with schemas and behaviors |
| 11 | [11-configuration.md](./11-configuration.md) | Settings, environment variables, config loading |
| 12 | [12-implementation-plan.md](./12-implementation-plan.md) | 10-week phased roadmap with milestones |
| 13 | [13-appendix-prompts.md](./13-appendix-prompts.md) | Complete system prompt templates |
| 14 | [14-appendix-templates.md](./14-appendix-templates.md) | Game archetype template structure |
| 15 | [15-testing-strategy.md](./15-testing-strategy.md) | Test structure, scenarios, fixtures |

## Quick Navigation by Role

- **Project Manager / Decision Maker**: Read [01-overview.md](./01-overview.md), [12-implementation-plan.md](./12-implementation-plan.md)
- **Architect**: Read [02-architecture.md](./02-architecture.md), [03-data-models.md](./03-data-models.md)
- **Backend Developer**: Read [04-agent-runtime.md](./04-agent-runtime.md), [10-tools-reference.md](./10-tools-reference.md)
- **Game Skill Developer**: Read [05-template-skill.md](./05-template-skill.md), [06-debug-skill.md](./06-debug-skill.md), [07-game-skill-orchestrator.md](./07-game-skill-orchestrator.md)
- **Asset Developer**: Read [08-asset-pipeline.md](./08-asset-pipeline.md)
- **QA / Test Engineer**: Read [09-bench.md](./09-bench.md), [15-testing-strategy.md](./15-testing-strategy.md)
- **DevOps / Config**: Read [11-configuration.md](./11-configuration.md)
- **Prompt Engineer**: Read [13-appendix-prompts.md](./13-appendix-prompts.md)
