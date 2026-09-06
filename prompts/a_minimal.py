"""A-1.0 minimal-instruction baseline for the PE6202 evaluation.

The application must append the same OUTPUT_SCHEMA used for B-1.0 and C-1.3.
The A user payload contains only ``mode`` and ``inputs``.
"""

VERSION = "A-1.0"

CONTRACT = """The user message is JSON containing inputs.
Return exactly one valid JSON object matching the appended OUTPUT_SCHEMA.
Do not use Markdown fences or text outside the JSON.
"""

LEARNING = """Answer the student's learning question clearly and concisely."""
NEXT = """Tell the student what to do next in the exercise."""
DEBUG = """Suggest likely causes, checks, fixes, and a way to verify the result."""
GEN = """Generate one multiple-choice practice question with four options and one correct answer."""
EXPLAIN = """Explain the correct answer and why the other options are wrong."""

TASKS = {
    "learning": LEARNING,
    "next_step": NEXT,
    "debug": DEBUG,
    "generate": GEN,
    "explain": EXPLAIN,
}

