from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from coding_agent.workflow.models import Workflow, WorkflowStep
from coding_agent.workflow.resolver import VariableResolver
from coding_agent.workflow.skills import SkillResolver
from coding_agent.workflow.state import StateManager

if TYPE_CHECKING:
    from coding_agent.agent import Agent


@dataclass
class StepResult:
    success: bool
    output: str | None = None
    error: str | None = None


class WorkflowExecutor:
    """Execute workflow steps."""

    def __init__(self, workflow: Workflow, agent: "Agent"):
        self.workflow = workflow
        self.agent = agent
        self.resolver = VariableResolver(workflow)
        self.skill_resolver = SkillResolver()
        self.state_manager = StateManager()
        self._current_skill_context: str | None = None

    async def execute_step(self, step: WorkflowStep) -> StepResult:
        """Execute a single workflow step."""
        if step.condition:
            if not self.resolver.evaluate_condition(step.condition):
                return StepResult(success=True, output="Skipped (condition not met)")

        skill = self.skill_resolver.resolve_skill_for_step(
            step.skill, self.workflow.skill
        )

        if skill:
            self._current_skill_context = f"## {skill.name} Skill\n{skill.instructions}"
            self.agent.conversation.add_message("system", self._current_skill_context)

        try:
            outputs = []
            for action in step.actions:
                result = await self._execute_action(action)
                outputs.append(result)

                if "output_var" in action:
                    self.resolver.set(action["output_var"], result)

            return StepResult(
                success=True,
                output="\n".join(str(o) for o in outputs if o)
            )
        finally:
            if skill:
                self.agent.conversation.remove_message(self._current_skill_context)
                self._current_skill_context = None

    async def _execute_action(self, action: dict) -> str:
        """Execute a single action."""
        task = self.resolver.resolve(action.get("task", ""))
        run_cmd = self.resolver.resolve(action.get("run", ""))

        if task:
            response = self.agent.run(task)
            return response
        elif run_cmd:
            return await self._run_command(run_cmd)

        return ""

    async def _run_command(self, command: str) -> str:
        """Run a shell command."""
        import asyncio
        proc = await asyncio.create_subprocess_shell(
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        result = stdout.decode() if stdout else ""
        if stderr:
            result += "\n" + stderr.decode()
        return result

    async def run(self) -> None:
        """Run all workflow steps."""
        for i, step in enumerate(self.workflow.steps):
            if step.id in self.workflow.completed_steps:
                continue

            self.workflow.current_step = i

            result = await self.execute_step(step)

            if not result.success:
                if step.on_failure and step.on_failure.get("retry"):
                    pass
                raise RuntimeError(f"Step {step.id} failed: {result.error}")

            self.workflow.completed_steps.append(step.id)

            if step.checkpoint:
                await self._save_checkpoint(step, result)

                if step.confirm:
                    await self._wait_confirmation(step)

    async def run_single_step(self) -> StepResult | None:
        """Execute a single step and return result.
        
        This method is for step-by-step execution where the caller
        controls when to proceed to the next step.
        
        Returns:
            StepResult if a step was executed, None if no more steps
        """
        step = self.workflow.get_next_step()
        if step is None:
            return None

        self.workflow.current_step = self.workflow.steps.index(step)

        result = await self.execute_step(step)

        if not result.success:
            if step.on_failure and step.on_failure.get("retry"):
                pass
            raise RuntimeError(f"Step {step.id} failed: {result.error}")

        self.workflow.completed_steps.append(step.id)

        if step.checkpoint:
            await self._save_checkpoint(step, result)

            if step.confirm:
                await self._wait_confirmation(step)

        return result

    async def run_until_step(self, target_step_id: str) -> list[StepResult]:
        """Execute steps until a specific step is reached.
        
        Args:
            target_step_id: The step ID to run until (exclusive)
            
        Returns:
            List of StepResults for all executed steps
        """
        results = []
        for step in self.workflow.steps:
            if step.id in self.workflow.completed_steps:
                continue
            if step.id == target_step_id:
                break

            self.workflow.current_step = self.workflow.steps.index(step)

            result = await self.execute_step(step)

            if not result.success:
                if step.on_failure and step.on_failure.get("retry"):
                    pass
                raise RuntimeError(f"Step {step.id} failed: {result.error}")

            self.workflow.completed_steps.append(step.id)
            results.append(result)

            if step.checkpoint:
                await self._save_checkpoint(step, result)

                if step.confirm:
                    await self._wait_confirmation(step)

        return results

    async def save_state(self, output_dir: str | None = None, session_id: str | None = None) -> None:
        """Save current workflow state.
        
        Args:
            output_dir: Optional output directory for artifacts
            session_id: Optional session ID for continuation
        """
        from pathlib import Path
        self.state_manager.save_state(
            self.workflow,
            Path(output_dir) if output_dir else None,
            session_id,
        )

    def load_state(self) -> bool:
        """Load and restore workflow state.
        
        Returns:
            True if state was loaded successfully
        """
        state = self.state_manager.load_state(self.workflow.name)
        if state:
            self.workflow.restore_state(state)
            return True
        return False

    async def _save_checkpoint(self, step: WorkflowStep, result: StepResult) -> None:
        """Save checkpoint after step completion."""
        pass

    async def _wait_confirmation(self, step: WorkflowStep) -> None:
        """Wait for user confirmation before continuing."""
        pass
