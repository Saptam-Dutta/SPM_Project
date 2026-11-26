"""
charter_builder.py
-------------------
Two responsibilities:
  1. generate_charter_content()  -> calls the selected AI provider and returns a dict
     of AI-drafted charter content (objective, success criteria, deliverables,
     milestones, requirements, risks).
  2. build_charter_xlsx()        -> writes that content into a copy of the
     original Project_Charter_Template.xlsx, using the exact same cell
     layout the template already has (nothing about the template's design
     is changed, only the placeholder text is replaced with real content).
"""

import shutil
from copy import copy

import openpyxl

from .llm_client import call_llm, parse_json_reply


# ---------------------------------------------------------------------------
# 1. AI content generation
# ---------------------------------------------------------------------------

SCHEMA_INSTRUCTIONS = """
You are a senior project management consultant. Draft the content for a
project charter based on the information supplied by the user.

Return ONLY a single valid JSON object (no markdown fences, no commentary)
with exactly these keys:

{
  "objective": "1-2 sentence clear statement of the project's purpose",
  "success_criteria": "1-3 sentence measurable definition of success",
  "key_deliverables": "short bullet-style list as a single string, items separated by newlines, no numbering",
  "high_level_requirements": ["requirement 1", "requirement 2", "..."],
  "milestones": [
    {"milestone": "name of milestone", "deadline": "date or relative timeframe"},
    "... 3 to 5 milestones, in chronological order"
  ],
  "risks": ["risk 1", "risk 2", "..."],
  "stakeholders": [
    {"name": "stakeholder name or role placeholder", "role": "their role on the project"},
    "... 2 to 5 stakeholders. If the user did not name specific people, infer sensible stakeholder ROLES (e.g. 'Sponsor', 'End Users') rather than inventing fake names."
  ]
}

Keep every field concise and professional - this text goes directly onto a
one-page project charter document. Do not add any keys other than the ones
listed above.
"""


def _build_user_prompt(inputs: dict) -> str:
    lines = [
        f"Project Name: {inputs.get('project_name', '')}",
        f"Project Description / Purpose: {inputs.get('description', '')}",
        f"Project Manager(s): {inputs.get('project_manager', '')}",
        f"Budget: {inputs.get('budget', '') or 'Not specified'}",
        f"Team Members: {inputs.get('team_members', '') or 'Not specified'}",
        f"Known Stakeholders: {inputs.get('stakeholders_raw', '') or 'None given - please suggest sensible ones'}",
        f"Target Timeframe: {inputs.get('timeframe', '') or 'Not specified'}",
    ]
    return "\n".join(lines)


def generate_charter_content(inputs: dict, provider: str, api_key: str, model: str, base_url: str = "") -> dict:
    """Asks the selected AI provider to draft the charter and returns the
    parsed JSON dict described in SCHEMA_INSTRUCTIONS. Raises RuntimeError
    with a readable message on any failure."""
    prompt = SCHEMA_INSTRUCTIONS + "\n\nProject information:\n" + _build_user_prompt(inputs)
    raw = call_llm(provider, model, api_key, prompt, base_url)
    return parse_json_reply(raw)


# ---------------------------------------------------------------------------
# 2. Writing content into the template's exact layout
# ---------------------------------------------------------------------------

TEMPLATE_CELLS = {
    "project_name": "B2",
    "objective": "B3",
    "success_criteria": "B4",
    "key_deliverables": "B5",
    "milestones_names": "B6",
    "milestones_deadlines": "C6",
    "requirements": "B7",
    "resource": "B8",
    "risks": "B9",
    "stakeholder_names": "B10",
    "stakeholder_roles": "C10",
    "project_manager": "B11",
    "approval_name": "B13",
    "approval_title_date": "C13",
}


def _numbered_list(items: list[str]) -> str:
    return "\n".join(f"{i + 1}. {item}" for i, item in enumerate(items))


def build_charter_xlsx(data: dict, template_path: str, output_path: str) -> str:
    """Fills a copy of the template with `data` and saves it to output_path.

    `data` is expected to have the keys produced by the Streamlit form,
    which mirror TEMPLATE_CELLS above (see app.py for exactly how it's
    assembled). Only the designated placeholder cells are written - every
    other cell (headers, formatting, column widths, merges) is left
    untouched, per the template's existing design.
    """
    shutil.copyfile(template_path, output_path)

    wb = openpyxl.load_workbook(output_path)
    ws = wb.active

    def set_cell(key, value, wrap=True):
        coord = TEMPLATE_CELLS[key]
        cell = ws[coord]
        cell.value = value
        if wrap:
            existing = cell.alignment
            cell.alignment = openpyxl.styles.Alignment(
                wrap_text=True,
                vertical=existing.vertical or "top",
                horizontal=existing.horizontal,
            )

    set_cell("project_name", data.get("project_name", ""))
    set_cell("objective", data.get("objective", ""))
    set_cell("success_criteria", data.get("success_criteria", ""))
    set_cell("key_deliverables", data.get("key_deliverables", ""))

    milestones = data.get("milestones", [])
    set_cell(
        "milestones_names",
        "Milestones\n\n" + _numbered_list([m.get("milestone", "") for m in milestones]),
    )
    set_cell(
        "milestones_deadlines",
        "Deadlines\n\n" + _numbered_list([m.get("deadline", "") for m in milestones]),
    )

    set_cell(
        "requirements",
        _numbered_list(data.get("high_level_requirements", [])),
    )

    set_cell(
        "resource",
        f"Budget:\n{data.get('budget', '')}\n\nTeam members:\n{data.get('team_members', '')}",
    )

    set_cell("risks", _numbered_list(data.get("risks", [])))

    stakeholders = data.get("stakeholders", [])
    set_cell(
        "stakeholder_names",
        "Name\n" + _numbered_list([s.get("name", "") for s in stakeholders]),
    )
    set_cell(
        "stakeholder_roles",
        "Role\n" + _numbered_list([s.get("role", "") for s in stakeholders]),
    )

    set_cell("project_manager", data.get("project_manager", ""))

    set_cell(
        "approval_name",
        f"Name: {data.get('approval_name', '')}\n\nSignature:",
    )
    set_cell(
        "approval_title_date",
        f"Title: {data.get('approval_title', '')}\n\nDate: {data.get('approval_date', '')}",
    )

    # Give the taller content rows a bit more room so wrapped text is visible
    # when the file is opened (this mirrors what a person would do manually).
    for row in (2, 3, 4, 5, 6, 7, 8, 9, 10, 13):
        current = ws.row_dimensions[row].height
        min_height = 60 if row not in (2,) else 20
        if current is None or current < min_height:
            ws.row_dimensions[row].height = min_height

    wb.save(output_path)
    return output_path
