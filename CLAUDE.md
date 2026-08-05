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
- HTTP client (for adapters): `httpx`

## TDD Workflow (must follow)

This project is developed test-first. For every change:

1. Write a failing test first (red)
2. Write the minimum code to make it pass (green)
3. Refactor while keeping tests green

## Notes for AI Agents

- Read the relevant `docs/*.md` before writing code; do not assume
  architecture details not documented here
- If a request conflicts with the rules above, raise it in conversation
  instead of silently working around it
- This is a solo personal project — avoid over-engineering beyond what
  Clean Architecture + TDD require, but do not skip either, since both are
  deliberate learning goals of this project