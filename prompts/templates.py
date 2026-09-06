"""Versioned A/B/C prompt routing for the controlled evaluation."""
from prompts import a_minimal, b_structured, c_full_system


PROMPT_MODULES = {
    'A': a_minimal,
    'B': b_structured,
    'C': c_full_system,
}


def system_prompt(task, mode):
    try:
        prompt_module = PROMPT_MODULES[mode]
        task_prompt = prompt_module.TASKS[task]
    except KeyError as exc:
        raise ValueError(f'Unknown prompt task or variant: {task}/{mode}') from exc
    return prompt_module.CONTRACT + '\n' + task_prompt


def prompt_version(mode):
    try:
        return PROMPT_MODULES[mode].VERSION
    except KeyError as exc:
        raise ValueError(f'Unknown prompt variant: {mode}') from exc
