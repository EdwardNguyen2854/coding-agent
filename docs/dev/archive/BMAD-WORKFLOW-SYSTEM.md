# External Workflow System Reference

> **Note**: This document describes an external workflow system (BMAD) that was studied for reference purposes. This is NOT our implementation - it documents the external system we learned from.

This document describes an external modular plugin system for AI-assisted development and creative workflows.

## Overview

BMAD is a modular plugin system that provides AI-assisted development and creative workflows. It consists of pluggable modules that offer specialized agents and workflows for different tasks.

## Modules

| Module | Version | Purpose |
|--------|---------|---------|
| **core** | 6.0.0-Beta.8 | Core workflows (brainstorming, party-mode) |
| **bmm** | 6.0.0-Beta.8 | Built-in module manager (PM, Dev, QA, Architect, etc.) |
| **bmb** | 0.1.6 | BMAD Builder (create/edit/validate agents, modules, workflows) |
| **cis** | 0.1.6 | Creative Intelligence Suite (storytelling, design-thinking, innovation) |
| **tea** | 1.1.0 | Test Architecture Enterprise (test frameworks, ATDD, CI/CD) |

### Module Sources

- **built-in**: Core modules bundled with the system
- **external**: NPM packages installed separately (e.g., `bmad-builder`, `bmad-creative-intelligence-suite`)

## Directory Structure

```
_bmad/
├── _config/                 # Configuration and manifests
│   ├── manifest.yaml        # Module installation metadata
│   ├── agent-manifest.csv   # Agent definitions
│   ├── workflow-manifest.csv
│   ├── tool-manifest.csv
│   ├── task-manifest.csv
│   └── agents/             # Agent customizations
├── core/                    # Core module
│   ├── agents/
│   ├── workflows/
│   │   ├── brainstorming/
│   │   │   ├── workflow.md
│   │   │   ├── steps/
│   │   │   ├── template.md
│   │   │   └── brain-methods.csv
│   │   └── party-mode/
│   └── config.yaml
├── bmm/                     # Built-in module manager
├── bmb/                     # BMAD Builder module
├── cis/                     # Creative Intelligence Suite
├── tea/                     # Test Architecture Enterprise
└── _memory/                 # Persistent memory for agents
    ├── tech-writer-sidecar/
    └── storyteller-sidecar/
```

## Workflow Architecture

BMAD uses a **micro-file architecture** for disciplined workflow execution:

### File Structure

Each workflow consists of:

```
workflow-name/
├── workflow.md          # Main entry point with metadata
├── steps/               # Sequential step files
│   ├── step-01-xxx.md
│   ├── step-02-xxx.md
│   └── step-03-xxx.md
├── template.md          # Output document template
├── README.md            # Workflow documentation
├── instructions.md      # Detailed instructions
├── *.csv                # Reference data (techniques, methods)
└── data/                # Additional data files
```

### Frontmatter

Workflow metadata in YAML frontmatter:

```yaml
---
name: workflow-name
description: What this workflow does
context_file: ''  # Optional project-specific context
---
```

### Step State Tracking

State is tracked via frontmatter in the output document:

```yaml
---
stepsCompleted: [1, 2]
inputDocuments: []
session_topic: '...'
selected_approach: '...'
techniques_used: []
ideas_generated: []
---
```

### Execution Model

1. **Entry Point**: `workflow.md` is loaded first
2. **Step Loading**: Each step explicitly loads the next step after completion
3. **User Control**: User controls continuation at each step
4. **Append-Only**: Documents grow via append, no overwrite
5. **Continuation Detection**: Steps check for existing state before initializing

### Example: Brainstorming Workflow

```
workflow.md
    ↓
step-01-session-setup.md (creates document, gathers context)
    ↓
step-01b-continue.md (detects existing session)
    ↓
step-02a-user-selected.md OR
step-02b-ai-recommended.md OR
step-02c-random-selection.md OR
step-02d-progressive-flow.md
    ↓
step-03-technique-execution.md
    ↓
step-04-idea-organization.md
```

## Agents

### Agent Definition (agent-manifest.csv)

| Field | Description |
|-------|-------------|
| name | Internal identifier |
| displayName | Human-readable name |
| title | Role title |
| icon | Emoji icon |
| capabilities | Comma-separated capabilities |
| role | Role description |
| identity | Persona and background |
| communicationStyle | How the agent speaks |
| principles | Core guiding principles |
| module | Parent module |
| path | Path to agent definition file |

### Agent Personas

Each agent has a distinct persona:

- **Mary (Analyst)**: "Treasure hunter" - excited by discovery, structures insights with precision
- **Winston (Architect)**: Calm, pragmatic - balances "what could be" with "what should be"
- **Amelia (Dev)**: Ultra-succinct - speaks in file paths and AC IDs
- **John (PM)**: Asks "WHY?" relentlessly - direct and data-sharp
- **Quinn (QA)**: Practical, "ship it and iterate" mentality
- **Barry (Quick Flow Solo Dev)**: Direct, confident, implementation-focused
- **Bob (SM)**: Crisp, checklist-driven, zero tolerance for ambiguity
- **Paige (Tech Writer)**: Patient educator - uses analogies to make complex simple
- **Sally (UX Designer)**: Paints pictures with words, empathetic advocate

### BMB Agent Builders

- **Bond (Agent Builder)**: Precise, technical, focuses on structure and compliance
- **Morgan (Module Builder)**: Strategic, holistic, thinks in ecosystems
- **Wendy (Workflow Builder)**: Methodical, process-oriented

### CIS Creative Agents

- **Carson (Brainstorming Coach)**: Enthusiastic improv coach, "YES AND" energy
- **Dr. Quinn (Creative Problem Solver)**: Sherlock Holmes mixed with scientist
- **Maya (Design Thinking Coach)**: Jazz musician - improvises, uses metaphors
- **Victor (Innovation Strategist)**: Chess grandmaster - bold declarations
- **Caravaggio (Presentation Master)**: Energetic creative director
- **Sophia (Storyteller)**: Bard weaving epic tales

### TEA

- **Murat (Tea)**: Master Test Architect - "strong opinions, weakly held"

## Workflows by Module

### Core (brainstorming, party-mode)

| Workflow | Description |
|----------|-------------|
| brainstorming | Facilitate interactive brainstorming using diverse creative techniques |
| party-mode | Orchestrate group discussions between all installed BMAD agents |

### BMM (Development Lifecycle)

| Phase | Workflows |
|-------|-----------|
| Analysis | create-product-brief, domain-research, market-research, technical-research |
| Planning | create-prd, edit-prd, validate-prd, create-ux-design |
| Solutioning | check-implementation-readiness, create-architecture, create-epics-and-stories |
| Implementation | code-review, correct-course, create-story, dev-story, retrospective, sprint-planning, sprint-status |
| Quick Flow | quick-dev, quick-spec |
| Documentation | document-project, generate-project-context |
| QA | qa-automate |

### BMB (Module Building)

| Workflow | Description |
|----------|-------------|
| create-agent | Create new BMAD agent with best practices |
| edit-agent | Edit existing BMAD agents |
| validate-agent | Validate and improve agent deficiencies |
| create-module-brief | Create product brief for module development |
| create-module | Create complete module with agents, workflows, infrastructure |
| edit-module | Edit existing modules |
| validate-module | Compliance check against best practices |
| create-workflow | Create new workflow with proper structure |
| edit-workflow | Edit existing workflows |
| validate-workflow | Run validation checks |

### CIS (Creative Intelligence)

| Workflow | Description |
|----------|-------------|
| design-thinking | Guide human-centered design processes |
| innovation-strategy | Identify disruption opportunities |
| problem-solving | Apply systematic problem-solving methodologies |
| storytelling | Craft compelling narratives using story frameworks |

### TEA (Test Architecture)

| Workflow | Description |
|----------|-------------|
| testarch-atdd | Generate failing acceptance tests (TDD) |
| testarch-automate | Expand test automation coverage |
| testarch-ci | Scaffold CI/CD quality pipeline |
| testarch-framework | Initialize test framework architecture |
| testarch-nfr | Assess non-functional requirements |
| teach-me-testing | Multi-session testing learning companion |
| testarch-test-design | System-level or epic-level test planning |
| testarch-test-review | Review test quality |
| testarch-trace | Requirements-to-tests traceability matrix |

## Configuration

### Global Config (`core/config.yaml`)

```yaml
project_name: ...
output_folder: ...
user_name: ...
communication_language: en
document_output_language: en
user_skill_level: ...
```

### Agent Customization (`_config/agents/`)

Agent-specific customizations in YAML files (e.g., `bmm-pm.customize.yaml`).

## IDE Support

BMAD supports multiple IDEs:
- claude-code
- opencode
- antigravity
- codex
- cursor
