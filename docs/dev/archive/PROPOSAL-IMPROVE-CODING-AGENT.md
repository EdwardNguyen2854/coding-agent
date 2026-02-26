# Proposal: Enhancing Coding Agent Workflow System

## Executive Summary

This proposal outlines improvements to the Coding Agent's workflow system. We studied external workflow systems (like BMAD) to understand their strengths, and this proposal outlines how we can implement similar patterns under our own architecture to enhance extensibility, user experience, and workflow richness.

**Note**: This is a native implementation - we are NOT integrating any external systems. All features will be built from scratch with our own naming conventions.

## Current State

The Coding Agent uses a minimal state-machine workflow:
- `IDLE → PLAN_CREATED → AWAITING_APPROVAL → EXECUTING → COMPLETED`
- Single `Workflow` class handling all logic
- Plan → Approve → Execute pattern
- No continuation support, limited workflow types

## Proposed Improvements

### Phase 1: Foundation Enhancements (Low Risk)

#### 1.1 Workflow Registry System

**Problem**: Currently, adding workflows requires code changes.

**Solution**: Implement a YAML-based workflow registry.

```yaml
# config/workflows.yaml
workflows:
  - name: default
    description: Standard plan → approve → execute
    type: python
    entry: workflow_impl.py::Workflow

  - name: agile
    description: Sprint-based agile workflow
    type: python
    entry: workflow_impl.py::AgileWorkflow

  - name: stepped
    description: Multi-step workflow with explicit checkpoints
    type: stepped
    steps:
      - name: analyze
        description: Analyze requirements
        prompt: tasks/analyze.md
      - name: plan
        description: Create implementation plan
        prompt: tasks/plan.md
      - name: implement
        description: Execute implementation
        prompt: tasks/implement.md
```

**Benefit**: Add new workflows by creating config entries and step files.

#### 1.2 Session Continuation Support

**Problem**: No way to resume interrupted sessions.

**Solution**: Add session state persistence.

```python
# Add to Workflow class
def save_session(self, session_path: Path) -> None:
    """Save current workflow state for continuation."""
    state = {
        "type": self.type.value,
        "state": self.state.value,
        "plan": self.current_plan.to_markdown() if self.current_plan else None,
        "todos": self.todo_list.to_dict(),
        "timestamp": datetime.now().isoformat(),
    }
    session_path.write_text(yaml.dump(state))

def load_session(self, session_path: Path) -> bool:
    """Load and resume previous session."""
    if not session_path.exists():
        return False
    # ... restore state
```

**Benefit**: Users can resume work after interruption.

#### 1.3 Step-Based Execution

**Problem**: All plan execution happens in one go.

**Solution**: Allow breaking execution into explicit steps.

```python
class WorkflowStep:
    name: str
    description: str
    prompt: str  # Path to prompt template
    execute: Callable[[], StepResult]
    next_step: str | None
    
class SteppedWorkflow(Workflow):
    steps: list[WorkflowStep]
    current_step_index: int = 0
    
    def next_step(self) -> StepResult:
        """Execute next step."""
        result = self.steps[self.current_step_index].execute()
        self.current_step_index += 1
        return result
```

**Benefit**: Better user control, clearer progress, easier debugging.

---

### Phase 2: Enhanced Workflow System (Medium Risk)

#### 2.1 Native Workflow Loader

**Problem**: Only 2 workflow types available.

**Solution**: Implement a native workflow loader with pluggable step files.

```
workflows/
├── registry.yaml           # Workflow definitions
├── default/
│   ├── workflow.yaml
│   └── steps/
├── agile/
│   ├── workflow.yaml
│   └── steps/
├── brainstorming/
│   ├── workflow.yaml
│   ├── steps/
│   │   ├── step-01-setup.md
│   │   └── step-02-ideate.md
│   └── templates/
│       └── session.md
└── code-review/
    ├── workflow.yaml
    └── steps/
```

```python
class WorkflowLoader:
    """Load and execute native workflows."""
    
    def __init__(self, workflows_dir: Path):
        self.workflows_dir = workflows_dir
        
    def load_workflow(self, name: str) -> SteppedWorkflow:
        """Load workflow from YAML config."""
        config = self.workflows_dir / name / "workflow.yaml"
        steps_dir = self.workflows_dir / name / "steps"
        
        # Parse workflow.yaml
        # Load each step-*.md file
        # Return SteppedWorkflow
        
    def get_available_workflows(self) -> list[WorkflowInfo]:
        """List all available workflows."""
        # Parse registry.yaml
```

#### 2.2 Agent Persona System

**Problem**: No agent differentiation.

**Solution**: Implement agent manifest and persona system.

```yaml
# config/agents.yaml
agents:
  - name: dev
    displayName: Amelia
    title: Senior Developer
    icon: 💻
    communication_style: |
      Ultra-succinct. Speaks in file paths and AC IDs.
      No fluff, all precision.
    principles:
      - All tests must pass 100% before ready for review
      - Every task covered by unit tests
      
  - name: pm
    displayName: John
    title: Product Manager
    icon: 📋
    communication_style: |
      Asks 'WHY?' relentlessly like a detective.
      Direct and data-sharp, cuts through fluff.
```

```python
class AgentPersona:
    name: str
    display_name: str
    icon: str
    communication_style: str
    principles: list[str]
    
    def format_message(self, content: str) -> str:
        """Format message according to persona."""
        
class AgentSystem:
    personas: dict[str, AgentPersona]
    current_agent: AgentPersona
    
    def switch_agent(self, name: str) -> None:
        """Switch to different agent persona."""
```

**Benefit**: Distinct, consistent agent interactions.

---

### Phase 3: Advanced Features (Higher Risk)

#### 3.1 Multi-Agent Collaboration

**Problem**: Only single-agent interactions.

**Solution**: Implement multi-agent orchestration.

```python
class AgentRoundtable:
    """Run discussions between multiple agents."""
    
    agents: list[AgentPersona]
    topic: str
    
    async def discuss(self, rounds: int = 3) -> list[ChatMessage]:
        """Run multi-agent discussion."""
        messages = []
        for round in range(rounds):
            for agent in self.agents:
                response = await agent.respond(messages)
                messages.append(response)
        return messages
```

**Benefit**: Leverage multiple specialized agents.

#### 3.2 Creative Workflows

Implement our own creative workflows:

| Workflow | Description |
|----------|-------------|
| brainstorming | Structured ideation sessions with techniques |
| problem-solving | Systematic problem solving frameworks |
| design-thinking | Human-centered design process |
| storytelling | Narrative crafting for documentation |

#### 3.3 Test Architecture Workflows

Implement test-focused workflows:

| Workflow | Description |
|----------|-------------|
| tdd | Test-driven development red-green-refactor |
| test-review | Comprehensive test quality review |
| test-trace | Requirements-to-tests traceability |

---

## Implementation Plan

### Timeline Estimate

| Phase | Duration | Scope |
|-------|----------|-------|
| Phase 1 | 1-2 weeks | Foundation (registry, continuation, steps) |
| Phase 2 | 2-3 weeks | Enhanced workflow loader + agent system |
| Phase 3 | 3-4 weeks | Advanced features (multi-agent, creative) |

### Priority Recommendations

1. **High Impact, Low Risk**
   - Session continuation
   - Workflow registry

2. **High Impact, Medium Risk**
   - Native workflow loader
   - Agent persona system

3. **Medium Impact, Higher Risk**
   - Multi-agent collaboration
   - Full creative workflow support

---

## Backward Compatibility

- Current `Workflow` class remains as default workflow
- New features behind feature flags
- All workflows are native implementations (no external dependencies)

---

## Success Metrics

- Users can resume interrupted sessions
- New workflows can be added via config/files
- At least 5 native workflows available
- Agent personas provide consistent communication
- No regression in existing functionality

---

## Risks and Mitigations

| Risk | Mitigation |
|------|------------|
| Performance impact | Lazy loading of workflows |
| Complexity increase | Phased rollout, clear documentation |
| Breaking existing users | Feature flags, opt-in defaults |

---

## Conclusion

Implementing these improvements would significantly enhance the Coding Agent's capabilities while maintaining its simplicity. The phased approach allows incremental value delivery with manageable risk.

Recommended starting point: **Phase 1.1 (Workflow Registry)** and **Phase 1.2 (Session Continuation)** as they provide immediate user value with minimal complexity.
