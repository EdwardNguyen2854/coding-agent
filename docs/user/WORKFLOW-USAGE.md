# Workflow Usage

Workflows are YAML-defined automation sequences that guide you through multi-step tasks. They define variables, conditions, and actions that the agent executes step by step.

## Workflow File Location

Workflows are loaded from:
1. `./workflows/` - Project workflows directory
2. `~/.coding-agent/workflows/` - Global workflows directory
3. `workflows/examples/` - Example workflows in either location
4. Built-in workflows (included with the package)

## Creating a Workflow

Create a `.yaml` file in your workflows directory:

```yaml
# workflows/my-feature.yaml
name: my-feature
description: Implement a new feature end-to-end
version: "1.0"

# Define variables that will be prompted or passed
variables:
  feature_name:
    required: true
    description: "Name of the feature to implement"
  type:
    required: true
    enum: ["api", "ui", "both"]
  output_dir:
    default: "src/features"

# Workflow-level skill (optional)
skill: xlsx

steps:
  - id: analyze
    title: Analyze Requirements
    description: Review the feature requirements
    actions:
      - task: "Analyze the requirements for {feature_name}. Focus on {type} components."
      - run: "mkdir -p {output_dir}/{feature_name}"

  - id: implement
    title: Implement Feature
    description: Write the implementation
    # Only run if type is api or both
    if: "{type} == 'api' or {type} == 'both'"
    skill: xlsx
    actions:
      - task: "Implement the {feature_name} feature in {output_dir}/{feature_name}"
      - output_var: implementation_result

  - id: test
    title: Write Tests
    actions:
      - task: "Write tests for the {feature_name} implementation"
      - run: "npm test -- --coverage"

  - id: checkpoint
    title: Save Progress
    checkpoint: "checkpoints/{feature_name}-v1.md"
    confirm: true
    actions:
      - task: "Summarize the current state of {feature_name}"
```

## Workflow Structure

### Variables

Define inputs that the workflow requires:

```yaml
variables:
  name:                    # Short form - just marks as required
    required: true
  
  output_dir:             # With default value
    default: "output"
  
  type:                   # With enum constraint
    required: true
    enum: ["api", "ui"]
```

### Steps

Each step can contain:

| Field | Type | Description |
|-------|------|-------------|
| `id` | string | Unique identifier |
| `title` | string | Display name |
| `description` | string | Optional description |
| `if` | string | Condition to skip step |
| `skill` | string | Skill to load for this step |
| `actions` | list | Actions to execute |
| `checkpoint` | string | File path to save checkpoint |
| `confirm` | bool | Wait for user confirmation |
| `on_failure` | dict | Failure handling |

### Actions

Each action in a step can be one of:

```yaml
actions:
  # Send task to agent
  - task: "Do something with {variable}"
  
  # Run shell command
  - run: "echo hello"
  
  # Both
  - task: "Analyze code"
    run: "npm test"
    output_var: test_result  # Store output in variable
```

## Running a Workflow

### Interactive Mode

Start the agent and run a workflow:

```bash
coding-agent
/workflow run my-feature
```

The agent will prompt for required variables.

### Resume Incomplete Workflow

If a workflow was interrupted, resume from where it stopped:

```bash
coding-agent workflow run my-feature --resume
```

### Skip Confirmations

Run without stopping for confirmations:

```bash
coding-agent workflow run my-feature --yolo
```

## CLI Commands

```bash
# List all available workflows
coding-agent workflow list

# Run a workflow
coding-agent workflow run <name> [--resume] [--yolo]

# Check incomplete workflows
coding-agent workflow status
```

## Variable Syntax

Use `{variable_name}` in any string to reference variables:

```yaml
task: "Implement {feature_name} in {output_dir}"
run: "echo {greeting}"
```

### Built-in Variables

| Variable | Description |
|----------|-------------|
| `{project-root}` | Current project root directory |
| `{env:VAR_NAME}` | Environment variable value |

### Conditions

The `if` field supports simple comparisons:

```yaml
if: "{type} == 'api'"
if: "{count} != 0"
if: "{enabled}"  # Truthy check
```

## Checkpoints

Save progress to a file:

```yaml
steps:
  - id: save
    checkpoint: "checkpoints/progress.md"
    confirm: true  # Wait for user to continue
    actions:
      - task: "Summarize current state"
```

The checkpoint content is saved before confirmation, allowing you to review and continue.

## Skills Integration

Workflows can use skills at two levels:

1. **Workflow-level**: Apply skill to all steps
   ```yaml
   skill: xlsx
   steps:
     - ...
   ```

2. **Step-level**: Apply skill to specific step
   ```yaml
   steps:
     - id: process
       skill: xlsx
       actions:
         - ...
   ```

The step-level skill takes precedence.

## State Persistence

Workflow state is automatically saved to `~/.coding-agent/workflows/.state/`. This includes:
- Current step index
- Completed steps
- Variable values

Use `--resume` to continue from where you left off.
