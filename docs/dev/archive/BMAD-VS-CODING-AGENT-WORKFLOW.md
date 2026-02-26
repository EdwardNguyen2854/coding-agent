# External Workflow vs Coding Agent Workflow Comparison

> **Note**: This document compared Coding Agent with an external workflow system (BMAD). The external system was studied to understand patterns, but we do NOT integrate it. Our improvements are implemented natively with our own naming conventions.

This document compares the workflow systems: an external reference system vs the Coding Agent's native workflow.

## Overview

| Aspect | BMAD Workflow | Coding Agent Workflow |
|--------|---------------|----------------------|
| **Architecture** | Micro-file (multi-file steps) | Single class with state machine |
| **Workflows** | 50+ specialized workflows | 2 types (default, agile) |
| **State Tracking** | Frontmatter in output documents | Enum-based state machine |
| **Steps** | Separate `.md` files per step | Implicit in code logic |
| **Extensibility** | Add YAML/MD files | Modify Python code |

## Architecture Comparison

### BMAD: Micro-File Architecture

```
workflow-name/
├── workflow.md          # Entry point + metadata
├── steps/
│   ├── step-01-xxx.md  # Each step is a separate file
│   ├── step-02-xxx.md
│   └── step-03-xxx.md
├── template.md          # Output template
└── *.csv               # Reference data
```

- Each step is self-contained with its own rules
- Steps explicitly load next step after completion
- Frontmatter tracks state: `stepsCompleted: [1, 2]`
- Continuation detection: checks for existing output document

### Coding Agent: State Machine Architecture

```python
class WorkflowState(str, Enum):
    IDLE = "idle"
    AWAITING_PLAN = "awaiting_plan"
    PLAN_CREATED = "plan_created"
    AWAITING_APPROVAL = "awaiting_approval"
    EXECUTING = "executing"
    COMPLETED = "completed"
```

- State managed in Python class
- Transitions via method calls (`approve_plan()`, `reject_plan()`)
- Tasks managed via `TodoList` class
- Plan saved to `docs/implementation-plan.md`

## Workflow Lifecycle

### BMAD Lifecycle

```
workflow.md → step-01 → step-02 → step-03 → ... → complete
                  ↓          ↓         ↓
            frontmatter frontmatter frontmatter
            updates     updates     updates
```

1. Load `workflow.md` entry point
2. Execute step-01, update frontmatter
3. Step-01 explicitly loads step-02
4. Repeat until complete
5. User controls continuation at each step

### Coding Agent Lifecycle

```
IDLE → create_plan() → PLAN_CREATED → approve_plan() → AWAITING_APPROVAL
                                                            ↓
                                                      start executing
                                                            ↓
                                                      EXECUTING → COMPLETED
```

1. `create_plan()` - LLM generates plan, saved to markdown
2. `approve_plan()` - User approves, converts to todos
3. Execute tasks via `TodoList`
4. `complete_task()` marks done

## State Management

### BMAD: Document-Based State

```yaml
---
stepsCompleted: [1, 2, 3]
inputDocuments: []
session_topic: '...'
selected_approach: '...'
techniques_used: []
ideas_generated: []
---
```

- State lives in output document frontmatter
- Append-only document growth
- Each step reads previous state
- Supports workflow continuation

### Coding Agent: In-Memory State

```python
class Workflow:
    def __init__(self):
        self.state = WorkflowState.IDLE
        self.current_plan: Plan | None = None
        self.todo_list = TodoList()
```

- State in Python memory
- Plan serialized to markdown on creation
- TodoList persisted to disk via `TodoStore`
- No built-in continuation detection

## Extensibility

### Adding a BMAD Workflow

1. Create folder: `_bmad/{module}/workflows/{workflow-name}/`
2. Add `workflow.md` with frontmatter metadata
3. Add step files in `steps/` subfolder
4. Add `workflow-name` to `workflow-manifest.csv`
5. No code changes required

### Adding a Coding Agent Workflow

1. Modify `workflow_impl.py`
2. Add new `WorkflowState` enum values if needed
3. Add new `WorkflowType` enum value
4. Implement logic in `Workflow` class
5. Requires code changes

## Feature Comparison

| Feature | BMAD | Coding Agent |
|---------|------|--------------|
| Multiple workflow types | 50+ workflows | 2 types |
| User pause/continue at each step | ✅ | ❌ |
| Continuation detection | ✅ | ❌ |
| Document-based output | ✅ | Partial |
| Agent personas | ✅ 20+ agents | ❌ |
| Built-in creative workflows | ✅ | ❌ |
| Agile/sprint support | Via BMM module | Via AGILE type |
| Test architecture workflows | Via TEA module | ❌ |
| Module/plugin system | ✅ | ❌ |

## Strengths

### BMAD Strengths

- **Highly extensible**: Add workflows via file creation
- **Rich workflows**: 50+ pre-built for various tasks
- **Agent ecosystem**: 20+ specialized agents with personas
- **Creative workflows**: Brainstorming, storytelling, design-thinking
- **Test architecture**: TEA module for testing workflows
- **Continuation support**: Resume interrupted sessions

### Coding Agent Strengths

- **Simple**: Lightweight, easy to understand
- **Minimal overhead**: No complex file structure
- **Direct integration**: Tight coupling with agent loop
- **Todo-centric**: Familiar task management

## Weaknesses

### BMAD Weaknesses

- **Complex**: Requires understanding micro-file pattern
- **Heavy**: Many files per workflow
- **Overkill for simple tasks**: Full workflow for trivial operations
- **Documentation-dependent**: Steps rely on Markdown instructions

### Coding Agent Weaknesses

- **Limited workflows**: Only plan→approve→execute
- **Not extensible**: Requires code changes
- **No creative workflows**: Missing brainstorming, design-thinking
- **No agent system**: Lacks persona-based agents
- **No continuation**: Cannot resume interrupted sessions
- **No test workflows**: Missing TEA module equivalent

## Potential Improvements for Coding Agent

Based on BMAD patterns, the Coding Agent could benefit from:

1. **Continuation detection** - Check for existing session state on startup
2. **Step-based UI** - Break complex operations into explicit steps
3. **Agent persona system** - Define distinct communication styles
4. **Workflow registry** - Make workflows discoverable via config
5. **Document templates** - Standardized output formats
6. **Multi-agent support** - Party-mode for agent collaboration
7. **Specialized workflows** - Add creative, test, and analysis workflows

## Conclusion

BMAD is a **comprehensive, plugin-based system** designed for diverse AI-assisted workflows with strong emphasis on extensibility, agent personas, and creative/cognitive tasks.

The Coding Agent's workflow is **minimal and direct** - optimized for quick plan→execute cycles without ceremony.

The two systems could complement each other: the Coding Agent could leverage BMAD workflows for complex tasks while maintaining its lightweight core for simple operations.
