# Implementation Plan - Interactive Workflow Progress

## Phase 1: Core Infrastructure

### 1.1 Progress Types & Interfaces
- [ ] Create `internal/progress/types.go` - Define `Progress` interface and `WorkflowProgress` struct
- [ ] Create `internal/progress/progress.go` - Base progress implementation
- [ ] Create `internal/progress/workflow.go` - Multi-step workflow progress
- [ ] Create `internal/progress/spinner.go` - Spinner for indeterminate operations

### 1.2 Terminal Detection
- [ ] Create `internal/progress/terminal.go` - Terminal capability detection
- [ ] Implement TTY detection
- [ ] Implement width/height detection
- [ ] Handle terminal resize events

### 1.3 Configuration
- [ ] Add progress config to `config/` - Add `Progress` struct with enabled, style, refreshRate, showTime, showStep options
- [ ] Add CLI flags: `--progress`, `--progress-style`, `--no-progress`

## Phase 2: Progress Rendering

### 2.1 Progress Bar Renderer
- [ ] Implement `RenderBar()` - ASCII progress bar with percentage
- [ ] Add color support (when terminal supports it)
- [ ] Implement in-place update (ANSI escape sequences)

### 2.2 Step Indicator Renderer
- [ ] Implement `RenderStep()` - Current step / total steps
- [ ] Add step description rendering
- [ ] Support nested steps

### 2.3 Spinner Renderer
- [ ] Implement multiple spinner styles (dots, line, bouncing ball)
- [ ] Add status text support
- [ ] Animation frame management

### 2.4 Composite Renderer
- [ ] Combine bar, step, and time into single line output
- [ ] Implement smart truncation for narrow terminals

## Phase 3: Integration

### 3.1 Context Integration
- [ ] Add progress to CLI context (`context.Context` with progress value)
- [ ] Create `WithProgress(ctx, progress)` helper

### 3.2 Command Integration Points
- [ ] Identify long-running commands (deploy, build, test, etc.)
- [ ] Add progress wrappers to existing commands
- [ ] Preserve existing output for verbose mode

### 3.3 Logging Integration
- [ ] Ensure progress bar doesn't interfere with log output
- [ ] Handle concurrent progress and log messages
- [ ] Clear progress on completion before showing final output

## Phase 4: Testing & Polish

### 4.1 Unit Tests
- [ ] Test progress calculation accuracy
- [ ] Test terminal detection
- [ ] Test configuration parsing

### 4.2 Integration Tests
- [ ] Test with various terminal sizes
- [ ] Test with piped output (disable progress)
- [ ] Test with verbose mode

### 4.3 Edge Cases
- [ ] Handle rapid step changes
- [ ] Handle very long step descriptions
- [ ] Handle terminal disconnect during progress
- [ ] Handle Ctrl+C during progress

## File Structure

```
internal/
└── progress/
    ├── types.go      # Interfaces and structs
    ├── progress.go   # Base progress implementation
    ├── workflow.go   # Multi-step workflow
    ├── spinner.go    # Spinner implementation
    ├── terminal.go   # Terminal detection
    ├── render.go     # Rendering logic
    └── config.go     # Configuration

cmd/
└── (update existing commands with progress)

config/
└── (add progress config)
```

## Dependencies

- Standard library only (no external dependencies)
- Uses ANSI escape codes for terminal control

## Timeline Estimate

- Phase 1: 1-2 hours
- Phase 2: 2-3 hours
- Phase 3: 2-3 hours
- Phase 4: 1-2 hours

Total: ~8-10 hours
