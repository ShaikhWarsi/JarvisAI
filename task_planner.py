import asyncio
import logging
import json
import time
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any, Callable
from enum import Enum
from abc import ABC, abstractmethod
import ai_engine
import desktop_state


class TaskStatus(Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    BLOCKED = "blocked"


@dataclass
class SubTask:
    id: str
    description: str
    action: str
    target: Optional[str] = None
    parameters: Dict[str, Any] = field(default_factory=dict)
    status: TaskStatus = TaskStatus.PENDING
    verification: Optional[str] = None
    result: Optional[str] = None
    retry_count: int = 0
    max_retries: int = 3
    dependencies: List[str] = field(default_factory=list)

    def can_execute(self, completed_ids: List[str]) -> bool:
        if self.status != TaskStatus.PENDING:
            return False
        for dep_id in self.dependencies:
            if dep_id not in completed_ids:
                return False
        return True

    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "description": self.description,
            "action": self.action,
            "target": self.target,
            "status": self.status.value,
            "result": self.result
        }


class Tool(ABC):
    @abstractmethod
    def get_schema(self) -> Dict:
        pass

    @abstractmethod
    async def execute(self, **kwargs) -> str:
        pass

    @abstractmethod
    def can_handle(self, action: str) -> bool:
        pass


class TaskPlanner:
    def __init__(self, llm_provider: str = "groq"):
        self.llm_provider = llm_provider
        self.current_task_id = 0
        self.subtask_registry: Dict[str, SubTask] = {}
        self.execution_history: List[Dict] = []
        self._tools: Dict[str, Callable] = {}
        self._register_default_tools()
        self._desktop_state = desktop_state.get_desktop_state()

    def _register_default_tools(self):
        self._tools = {
            "open_application": self._tool_open_application,
            "click_element": self._tool_click_element,
            "type_text": self._tool_type_text,
            "press_key": self._tool_press_key,
            "take_screenshot": self._tool_take_screenshot,
            "read_screen": self._tool_read_screen,
            "find_element": self._tool_find_element,
            "execute_script": self._tool_execute_script,
            "wait": self._tool_wait,
            "navigate_web": self._tool_navigate_web,
        }

    def register_tool(self, name: str, func: Callable):
        self._tools[name] = func

    async def decompose(self, goal: str, context: Optional[Dict] = None) -> List[SubTask]:
        prompt = self._build_decomposition_prompt(goal, context)
        try:
            if self.llm_provider == "groq":
                messages = [
                    {"role": "system", "content": self._get_system_prompt()},
                    {"role": "user", "content": prompt}
                ]
                response = await ai_engine._get_groq_response(messages)
                if hasattr(response, 'choices'):
                    response_text = response.choices[0].message.content
                else:
                    response_text = str(response)
            else:
                response = await asyncio.to_thread(
                    ai_engine.model.generate_content,
                    prompt
                )
                response_text = response.text

            tasks = self._parse_task_response(response_text)
            for task in tasks:
                self.subtask_registry[task.id] = task
            return tasks

        except Exception as e:
            logging.error(f"Task decomposition failed: {e}")
            return self._fallback_decomposition(goal)

    def _build_decomposition_prompt(self, goal: str, context: Optional[Dict]) -> str:
        available_tools = list(self._tools.keys())
        context_str = ""
        if context:
            state = self._desktop_state.get_state_summary()
            context_str = f"\nCurrent Desktop State:\n{state}\n"

        prompt = f"""Break down this task into atomic steps that can be executed by an AI agent.

GOAL: {goal}
{context_str}

AVAILABLE TOOLS: {available_tools}

OUTPUT FORMAT: Return a JSON array of subtasks. Each subtask must have:
- "id": unique identifier (e.g., "step_1", "step_2")
- "action": the tool/action to use (must be from AVAILABLE TOOLS)
- "target": specific target (e.g., "notepad", "Save button", "https://github.com")
- "description": human-readable description of what this step does
- "verification": how to verify this step succeeded (e.g., "window with title 'Notepad' is open")
- "parameters": any additional parameters needed

RULES:
1. Each step must be verifiable
2. Max 15 steps total
3. Order matters - dependencies must come first
4. Use the most specific tool for each action
5. For clicks, include the element name in target

Example output:
[
  {{"id": "step_1", "action": "open_application", "target": "notepad", "description": "Open Notepad", "verification": "Notepad window is visible", "parameters": {{}}}},
  {{"id": "step_2", "action": "type_text", "target": "main_edit", "description": "Type Hello World", "verification": "Text visible in editor", "parameters": {{"text": "Hello World"}}}}
]

Return ONLY the JSON array, no markdown formatting or explanation.
"""
        return prompt

    def _get_system_prompt(self) -> str:
        return """You are a task decomposition engine for a desktop AI agent.
Your role is to break down complex user goals into atomic, verifiable subtasks.
Be precise and concrete. Every action must be clearly defined.
Prioritize reliability over cleverness."""

    def _parse_task_response(self, response_text: str) -> List[SubTask]:
        import re
        json_str = response_text.strip()

        match = re.search(r'\[.*\]', json_str, re.DOTALL)
        if match:
            json_str = match.group(0)

        try:
            data = json.loads(json_str)
            tasks = []
            for item in data:
                task = SubTask(
                    id=item.get("id", f"step_{len(tasks) + 1}"),
                    description=item.get("description", ""),
                    action=item.get("action", ""),
                    target=item.get("target"),
                    parameters=item.get("parameters", {}),
                    verification=item.get("verification"),
                    dependencies=item.get("dependencies", [])
                )
                tasks.append(task)
            return tasks
        except json.JSONDecodeError as e:
            logging.error(f"Failed to parse tasks: {e}\nResponse: {response_text}")
            return []

    def _fallback_decomposition(self, goal: str) -> List[SubTask]:
        goal_lower = goal.lower()
        tasks = []

        if "open" in goal_lower and ("notepad" in goal_lower or "editor" in goal_lower):
            tasks.append(SubTask(
                id="step_1",
                action="open_application",
                target="notepad",
                description="Open Notepad application",
                verification="Notepad window is visible"
            ))

        if "create" in goal_lower and "file" in goal_lower:
            tasks.append(SubTask(
                id="step_1",
                action="find_element",
                target="File",
                description="Navigate to File menu",
                verification="File menu is open"
            ))
            tasks.append(SubTask(
                id="step_2",
                action="click_element",
                target="New",
                description="Click New",
                verification="New document created"
            ))

        return tasks

    async def execute_subtask(self, task: SubTask) -> bool:
        logging.info(f"Executing: {task.id} - {task.description}")
        task.status = TaskStatus.IN_PROGRESS

        try:
            tool = self._tools.get(task.action)
            if not tool:
                task.result = f"No tool found for action: {task.action}"
                task.status = TaskStatus.FAILED
                return False

            params = task.parameters.copy()
            if task.target:
                params["target"] = task.target

            if asyncio.iscoroutinefunction(tool):
                result = await tool(**params)
            else:
                result = await asyncio.to_thread(tool, **params)

            task.result = str(result)

            if self._verify_task(task):
                task.status = TaskStatus.COMPLETED
                return True
            else:
                task.retry_count += 1
                if task.retry_count < task.max_retries:
                    task.status = TaskStatus.PENDING
                    logging.warning(f"Verification failed for {task.id}, retry {task.retry_count}/{task.max_retries}")
                    return False
                else:
                    task.status = TaskStatus.FAILED
                    return False

        except Exception as e:
            task.result = f"Execution error: {str(e)}"
            task.status = TaskStatus.FAILED
            logging.error(f"Subtask {task.id} failed: {e}")
            return False

    def _verify_task(self, task: SubTask) -> bool:
        if not task.verification:
            return True

        verification_lower = task.verification.lower()

        if "window" in verification_lower and "visible" in verification_lower:
            if task.target:
                win = self._desktop_state.get_window_by_title(task.target, fuzzy=True)
                return win is not None

        if "element" in verification_lower or "button" in verification_lower or "menu" in verification_lower:
            if task.target:
                elem = self._desktop_state.find_element(task.target)
                return elem is not None

        if "text" in verification_lower or "typed" in verification_lower:
            return "Error" not in task.result and task.result is not None

        return True

    async def execute_plan(self, tasks: List[SubTask], stop_on_failure: bool = True) -> Dict:
        completed = []
        failed = []
        results = {"completed": [], "failed": [], "summary": ""}

        for task in tasks:
            while task.can_execute(completed):
                success = await self.execute_subtask(task)
                if success:
                    completed.append(task.id)
                    results["completed"].append(task.to_dict())
                    break
                elif task.status == TaskStatus.FAILED:
                    if stop_on_failure:
                        results["failed"].append(task.to_dict())
                        results["summary"] = f"Failed at {task.id}: {task.result}"
                        return results
                    failed.append(task.id)
                    break
                else:
                    await asyncio.sleep(1)

            if task.status != TaskStatus.COMPLETED and task.id not in completed:
                if task.status == TaskStatus.FAILED:
                    failed.append(task.id)
                    results["failed"].append(task.to_dict())

        results["summary"] = f"Completed {len(completed)}/{len(tasks)} tasks"
        self.execution_history.append({
            "timestamp": time.time(),
            "tasks": [t.to_dict() for t in tasks],
            "completed": completed,
            "failed": failed
        })
        return results

    async def react_loop(self, goal: str, max_iterations: int = 10) -> Dict:
        context = {"desktop_state": self._desktop_state.get_state_summary()}
        tasks = await self.decompose(goal, context)

        if not tasks:
            return {"status": "failed", "reason": "Could not decompose task"}

        iteration = 0
        completed_ids = []

        while iteration < max_iterations:
            iteration += 1
            executable = [t for t in tasks if t.can_execute(completed_ids)]

            if not executable:
                if len(completed_ids) == len([t for t in tasks if t.status == TaskStatus.COMPLETED]):
                    break
                else:
                    return {"status": "failed", "reason": "Blocked tasks with unmet dependencies"}

            task = executable[0]
            success = await self.execute_subtask(task)

            if success:
                completed_ids.append(task.id)
            else:
                if task.retry_count >= task.max_retries:
                    return {
                        "status": "failed",
                        "reason": f"Task {task.id} failed after max retries",
                        "result": task.result,
                        "completed": completed_ids
                    }

            await asyncio.sleep(0.3)

        return {
            "status": "completed" if len(completed_ids) == len(tasks) else "partial",
            "completed": completed_ids,
            "total": len(tasks),
            "iterations": iteration
        }

    async def _tool_open_application(self, target: str, **kwargs) -> str:
        import task_manager
        return task_manager.open_application(target)

    async def _tool_click_element(self, target: str, **kwargs) -> str:
        import task_manager
        elem = self._desktop_state.find_element(target)
        if elem:
            if self._desktop_state.click_element(elem):
                return f"Clicked {target} at {elem.center}"
            return f"Failed to click {target}"
        return f"Element '{target}' not found"

    async def _tool_type_text(self, target: str, text: str, **kwargs) -> str:
        import task_manager
        self._desktop_state.update(force=True)
        elem = self._desktop_state.find_element(target)
        if elem:
            import pyautogui
            pyautogui.click(elem.center_x, elem.center_y)
            await asyncio.sleep(0.1)
        pyautogui.write(text)
        return f"Typed: {text}"

    async def _tool_press_key(self, target: str = None, key: str = None, **kwargs) -> str:
        import pyautogui
        if key:
            pyautogui.press(key)
            return f"Pressed: {key}"
        return "No key specified"

    async def _tool_take_screenshot(self, **kwargs) -> str:
        import task_manager
        return task_manager.take_screenshot()

    async def _tool_read_screen(self, target: str = None, **kwargs) -> str:
        self._desktop_state.update(force=True)
        if target:
            elem = self._desktop_state.find_element(target)
            if elem:
                return f"Found: {elem.title} at {elem.center}"
        return self._desktop_state.get_state_summary()

    async def _tool_find_element(self, target: str, element_type: str = None, **kwargs) -> str:
        self._desktop_state.update(force=True)
        elem = self._desktop_state.find_element(target)
        if elem:
            return f"Found {elem.element_type.value}: '{elem.title}' at ({elem.center_x}, {elem.center_y})"
        return f"Element '{target}' not found"

    async def _tool_execute_script(self, target: str, **kwargs) -> str:
        import task_manager
        return await task_manager.run_python_script(target)

    async def _tool_wait(self, seconds: int = 1, **kwargs) -> str:
        await asyncio.sleep(seconds)
        return f"Waited {seconds}s"

    async def _tool_navigate_web(self, target: str, **kwargs) -> str:
        import web_automation
        return await web_automation.browse_web(target)


_task_planner_instance: Optional[TaskPlanner] = None


def get_task_planner() -> TaskPlanner:
    global _task_planner_instance
    if _task_planner_instance is None:
        _task_planner_instance = TaskPlanner()
    return _task_planner_instance