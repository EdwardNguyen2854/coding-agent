# Interactive Workflow Progress - Proposal

## Overview

Add interactive workflow progress visualization to the CLI tool, providing users with real-time feedback on long-running tasks and multi-step operations.

## Motivation

Currently, the CLI executes workflows without providing visual progress feedback. Users have no indication of:
- Current step being executed
- Overall progress percentage
- Time elapsed/estimated
- What operations are pending

This leads to poor user experience during long-running operations.

## Proposed Solution

### 1. Progress Display Components

**Progress Bar**
- Single-line progress indicator showing percentage
- Updates in-place without flooding output
- Configurable refresh rate (default: 100ms)

**Step Indicator**
- Shows current step and total steps
- Step name/description
- Nested step support for complex workflows

**Spinner**
- For indeterminate operations
- Multiple styles (dots, line, bouncing ball)
- Combines with status text

### 2. UI States

```
[████████████░░░░░░░░] 60% | Step 3/5: Processing files | 00:12 / 00:20
```

```
[⠋] Connecting to server...
```

```
[✓] Complete! (in 2.3s)
```

### 3. Configuration Options

| Option | Default | Description |
|--------|---------|-------------|
| `progress.enabled` | `true` | Enable/disable progress display |
| `progress.style` | `bar` | Progress style: bar, dots, minimal |
| `progress.refreshRate` | `100` | Update interval in ms |
| `progress.showTime` | `true` | Show elapsed/estimated time |
| `progress.showStep` | `true` | Show current step info |

### 4. Implementation

**Core API:**
```go
type Progress interface {
    Start(total int, description string)
    Increment(n int)
    SetStep(step int, description string)
    Stop()
}

type WorkflowProgress struct {
    steps []Step
    current int
    // ...
}
```

**Usage Example:**
```go
progress := NewWorkflowProgress(ctx, 5, "Deploying application")
defer progress.Stop()

progress.SetStep(1, "Building binaries")
build()

progress.SetStep(2, "Uploading assets")
upload()

progress.SetStep(3, "Configuring services")
configure()
```

### 5. Terminal Compatibility

- Auto-detect terminal capabilities
- Fallback to simple output for non-TTY
- Support for 256-color and truecolor terminals
- Handle terminal resize events

## Alternatives Considered

1. **External libraries** - Use existing progress libraries but they don't integrate well with custom CLI UX
2. **Simple printf** - Too basic, doesn't provide good UX
3. **Full TUI** - Overkill for this use case, better to keep it lightweight

## Compatibility

- Backward compatible: progress display can be disabled
- Works with existing logging output
- Preserves output for scripting (disable flag)
