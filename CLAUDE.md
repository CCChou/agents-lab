# CLAUDE.md

This file provides core guidance for Claude (or any AI coding agent) working
on this project. Details are split into `docs/`; this file is the index and
the set of rules that must be followed on every task.

## Project Overview

A general agents that could chat with.


## Tech Stack

- Python 3.12+
- Package management: `uv`, dependencies in `pyproject.toml`
- Testing: `pytest`
- Linting/formatting: `ruff`
- LLM Framework: `langchain`

## TDD Workflow (must follow)

This project is developed test-first. For every change:

1. Write a failing test first (red)
2. Write the minimum code to make it pass (green)
3. Refactor while keeping tests green

## Docs

| File | Contents | Read when |
| --- | --- | --- |
| `README.md` | Setup, environment variables, CLI commands, HTTP API usage | Running the project or changing how it is used |
| `docs/architecture.md` | Components, layers, boundaries, current vs planned status | Adding or changing components |
| `docs/decisions.md` | Design decisions, rejected options, when to revisit | Changing a design or proposing an approach |
| `docs/roadmap.md` | Stages, known issues, open questions | Starting new work |
| `docs/vision.md` | Undecided long-term ideas | Planning a new stage |

## Notes for AI Agents

- Read the relevant `docs/*.md` before writing code; do not assume
  architecture details not documented here
- If a request conflicts with the rules above, raise it in conversation
  instead of silently working around it
- Record design decisions in `docs/decisions.md`, and raise any change to a
  recorded decision in conversation first
- Check the status column in `docs/architecture.md`: planned components do
  not exist yet
- Keep each fact in one place, and commit doc updates with the related code
- Do not edit any file without the user's approval: propose the change in
  conversation first and wait for a clear go-ahead
- This is a solo personal project — avoid over-engineering beyond what
  Clean Architecture + TDD require, but do not skip either, since both are
  deliberate learning goals of this project