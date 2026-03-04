# Implementation Plan - Interactive Workflow Progress

> **Status**: ✅ Implemented

## Phase 1: Core Infrastructure

### 1.1 Progress Types & Interfaces
- [x] Create `src/coding_agent/ui/progress/types.py` - Define `Progress` interface and `WorkflowProgress` struct
- [x] Create `src/coding_agent/ui/progress/progress.py` - Base progress implementation
- [x] Create `src/coding_agent/ui/progress/workflow.py` - Multi-step workflow progress (included in progress.py)
- [x] Create `src/coding_agent/ui/progress/spinner.py` - Spinner for indeterminate operations (included in render.py)

### 1.2 Terminal Detection
- [x] Create `src/coding_agent/ui/progress/terminal.py` - Terminal capability detection
- [x] Implement TTY detection
- [x] Implement width/height detection
- [ ] Handle terminal resize events

### 1.3 Configuration
- [x] Add progress config to `src/coding_agent/ui/progress/config.py` - Add `ProgressConfig` with enabled, style, refreshRate, showTime, showStep options
- [x] Add CLI flags: `--progress/--no-progress`, `--progress-style`

## Phase 2: Progress Rendering

### 2.1 Progress Bar Renderer
- [x] Implement `RenderBar()` - ASCII progress bar with percentage
- [x] Add color support (when terminal supports it)
- [x] Implement in-place update (ANSI escape sequences via Rich)

### 2.2 Step Indicator Renderer
- [x] Implement `RenderStep()` - Current step / total steps
- [x] Add step description rendering
- [ ] Support nested steps

### 2.3 Spinner Renderer
- [x] Implement multiple spinner styles (dots, line, bouncing ball)
- [x] Add status text support
- [x] Animation frame management

### 2.4 Composite Renderer
- [x] Combine bar, step, and time into single line output
- [ ] Implement smart truncation for narrow terminals

## Phase 3: Integration

### 3.1 Context Integration
- [ ] Add progress to CLI context (`context.Context` with progress value)
- [ ] Create `WithProgress(ctx, progress)` helper

### 3.2 Command Integration Points
- [x] Identify long-running commands (workflow execution)
- [x] Add progress wrappers to workflow executor
- [x] Preserve existing output for verbose mode

### 3.3 Logging Integration
- [x] Ensure progress bar doesn't interfere with log output (via Rich)
- [x] Handle concurrent progress and log messages
- [x] Clear progress on completion before showing final output

## Phase 4: Testing & Polish

### 4.1 Unit Tests
- [ ] Test progress calculation accuracy
- [ ] Test terminal detection
- [ ] Test configuration parsing

### 4.2 Integration Tests
- [ ] Test with various terminal sizes
- [x] Test with piped output (disable progress)
- [ ] Test with verbose mode

### 4.3 Edge Cases
- [x] Handle rapid step changes
- [ ] Handle very long step descriptions
- [ ] Handle terminal disconnect during progress
- [ ] Handle Ctrl+C during progress

## File Structure

```
src/coding_agent/ui/progress/
├── __init__.py     # Public API exports
├── types.py        # Interfaces and structs
├── progress.py     # Main implementations (Progress, WorkflowProgress, SimpleProgress)
├── render.py       # Custom rendering logic
├── terminal.py     # Terminal detection
└── config.py       # Configuration management
```

## Usage

```python
from coding_agent.ui.progress import create_progress, create_workflow_progress

# Simple progress bar
with create_progress("Processing", total=100) as p:
    for i in range(100):
        p.increment()
        time.sleep(0.01)

# Workflow progress
with create_workflow_progress(["Step 1", "Step 2", "Step 3"]) as wf:
    do_step_1()
    wf.next_step()
    do_step_2()
    wf.next_step()
    do_step_3()
```

CLI options:
- `--progress/--no-progress` - Enable/disable progress display
- `--progress-style [bar|dots|minimal]` - Progress bar style
