import asyncio
import logging
import pyautogui
import time
from typing import Dict, List, Optional, Any
import desktop_state
import task_planner
import cv_ui_integration


_desktop_state = None
_enhanced_planner = None
_robust_clicker = None


def initialize_enhanced_system():
    global _desktop_state, _enhanced_planner, _robust_clicker

    _desktop_state = desktop_state.get_desktop_state()
    _desktop_state.update(force=True)

    _enhanced_planner = task_planner.get_task_planner()

    _robust_clicker = cv_ui_integration.get_robust_clicker()
    _robust_clicker.initialize(use_local_cv=False)
    _robust_clicker.detector.initialize(use_local_cv=False)

    _desktop_state.start_monitoring(interval=0.5)

    logging.info("Enhanced system initialized")


async def execute_complex_task(goal: str) -> Dict[str, Any]:
    if not _enhanced_planner:
        initialize_enhanced_system()

    _desktop_state.update(force=True)
    context = {"desktop_state": _desktop_state.get_state_summary()}

    result = await _enhanced_planner.react_loop(goal, max_iterations=20)

    return result


async def robust_desktop_click(description: str, max_retries: int = 3) -> Dict[str, Any]:
    if not _robust_clicker:
        initialize_enhanced_system()

    result = await _robust_clicker.find_and_click(description)

    _desktop_state.update(force=True)

    return result


async def execute_planned_steps(goal: str, context: Optional[Dict] = None) -> Dict[str, Any]:
    if not _enhanced_planner:
        initialize_enhanced_system()

    _desktop_state.update(force=True)

    tasks = await _enhanced_planner.decompose(goal, context)

    if not tasks:
        return {
            "status": "failed",
            "reason": "Could not decompose task",
            "completed": [],
            "failed": []
        }

    result = await _enhanced_planner.execute_plan(tasks, stop_on_failure=True)

    return result


def get_desktop_snapshot() -> Dict[str, Any]:
    if not _desktop_state:
        initialize_enhanced_system()

    _desktop_state.update(force=True)

    snapshot = {
        "active_window": None,
        "windows": [],
        "buttons": [],
        "inputs": [],
        "summary": ""
    }

    if _desktop_state.active_window:
        snapshot["active_window"] = {
            "title": _desktop_state.active_window.title,
            "process": _desktop_state.active_window.process_name,
            "rect": _desktop_state.active_window.rect
        }

        buttons = _desktop_state.get_buttons()
        inputs = _desktop_state.get_inputs()

        snapshot["buttons"] = [
            {"title": b.title, "center": b.center, "rect": b.rect}
            for b in buttons[:10]
        ]
        snapshot["inputs"] = [
            {"title": i.title, "center": i.center, "rect": i.rect}
            for i in inputs[:10]
        ]

    for win_title, win_info in _desktop_state.windows.items():
        snapshot["windows"].append({
            "title": win_title,
            "process": win_info.process_name
        })

    snapshot["summary"] = _desktop_state.get_state_summary()

    return snapshot


async def enhanced_element_find(description: str) -> Optional[Dict[str, Any]]:
    if not _desktop_state:
        initialize_enhanced_system()

    _desktop_state.update(force=True)

    elem = _desktop_state.find_element(description, fuzzy=True)

    if elem:
        return {
            "found": True,
            "title": elem.title,
            "type": elem.element_type.value,
            "center": elem.center,
            "rect": elem.rect,
            "automation_id": elem.automation_id
        }

    return {"found": False, "description": description}


async def robust_drag_and_drop(source: str, target: str) -> Dict[str, Any]:
    if not _robust_clicker:
        initialize_enhanced_system()

    result = await _robust_clicker.find_and_drag(source, target)
    _desktop_state.update(force=True)

    return result


async def wait_for_element(description: str, timeout: float = 10.0) -> Dict[str, Any]:
    if not _robust_clicker:
        initialize_enhanced_system()

    result = await _robust_clicker.wait_for_element(description, timeout=timeout)
    return result


async def wait_for_state_change(expected: str, timeout: float = 10.0) -> Dict[str, Any]:
    if not _robust_clicker:
        initialize_enhanced_system()

    result = await _robust_clicker.wait_for_state_change(expected, timeout=timeout)
    return result


def press_keyboard_shortcut(shortcut: str) -> bool:
    if not _robust_clicker:
        _robust_clicker = cv_ui_integration.get_robust_clicker()

    return _robust_clicker._keyboard.press(shortcut)


def type_text_async(text: str, delay: float = 0.05) -> bool:
    if not _robust_clicker:
        _robust_clicker = cv_ui_integration.get_robust_clicker()

    return _robust_clicker._keyboard.type_text(text, delay=delay)


def activate_window(title: str, fuzzy: bool = True) -> bool:
    if not _desktop_state:
        initialize_enhanced_system()

    return _desktop_state.activate_window(title, fuzzy=fuzzy)


def minimize_window(title: str = None) -> bool:
    if not _desktop_state:
        initialize_enhanced_system()

    return _desktop_state.minimize_window(title)


def maximize_window(title: str = None) -> bool:
    if not _desktop_state:
        initialize_enhanced_system()

    return _desktop_state.maximize_window(title)


def close_window(title: str = None) -> bool:
    if not _desktop_state:
        initialize_enhanced_system()

    return _desktop_state.close_window(title)


def get_window_stack_order() -> List[str]:
    if not _desktop_state:
        initialize_enhanced_system()

    return _desktop_state.get_window_stack_order()


def get_app_windows(app_name: str) -> List[Dict[str, Any]]:
    if not _desktop_state:
        initialize_enhanced_system()

    windows = _desktop_state.get_app_windows(app_name)
    return [
        {"title": w.title, "process": w.process_name, "rect": w.rect}
        for w in windows
    ]


async def verify_ui_state(expected_state: str) -> bool:
    if not _desktop_state:
        initialize_enhanced_system()

    _desktop_state.update(force=True)

    expected_lower = expected_state.lower()

    if _desktop_state.active_window:
        title_lower = _desktop_state.active_window.title.lower()
        if expected_lower in title_lower:
            return True

    for win_title in _desktop_state.windows.keys():
        if expected_lower in win_title.lower():
            return True

    return False


class StateChangeDetector:
    def __init__(self):
        self._desktop_state = None
        self._previous_summary = None

    def initialize(self):
        global _desktop_state
        if not _desktop_state:
            _desktop_state = desktop_state.get_desktop_state()
        self._desktop_state = _desktop_state
        self._desktop_state.update(force=True)
        self._previous_summary = self._desktop_state.get_state_summary()

    def detect_change(self) -> Dict[str, Any]:
        if not self._desktop_state:
            self.initialize()

        current_summary = self._desktop_state.get_state_summary()

        if current_summary != self._previous_summary:
            change = {
                "changed": True,
                "previous": self._previous_summary,
                "current": current_summary
            }
            self._previous_summary = current_summary
            return change

        return {"changed": False}


_state_detector = None


def get_state_detector() -> StateChangeDetector:
    global _state_detector
    if _state_detector is None:
        _state_detector = StateChangeDetector()
        _state_detector.initialize()
    return _state_detector