"""Convert the agent's Markdown into Slack mrkdwn (D-037).

Line based on purpose: it covers what the agent writes (headings, emphasis, links, lists,
tables, code) and leaves anything else as escaped text.
"""

import re

_FENCE = re.compile(r"^\s*```")
_HEADING = re.compile(r"^#{1,6}\s+(.*)$")
_BULLET = re.compile(r"^(\s*)[-*+]\s+(.*)$")
_TABLE_ROW = re.compile(r"^\s*\|.*\|\s*$")
_TABLE_SEPARATOR = re.compile(r"^\s*\|?\s*:?-{3,}")
_INLINE_CODE = re.compile(r"(`[^`]*`)")
_LINK = re.compile(r"\[([^\]]+)\]\(([^)\s]+)\)")
_BOLD = re.compile(r"\*\*(.+?)\*\*")
_ITALIC = re.compile(r"(?<![\w*])\*(?!\s)(.+?)(?<!\s)\*(?![\w*])")
_BOLD_MARK = "\x00"


def to_mrkdwn(markdown: str) -> str:
    out: list[str] = []
    lines = markdown.split("\n")
    in_code = False
    i = 0
    while i < len(lines):
        line = lines[i]
        if _FENCE.match(line):
            in_code = not in_code
            out.append(line)
        elif in_code:
            out.append(line)
        elif _TABLE_ROW.match(line):
            end = i
            while end < len(lines) and _TABLE_ROW.match(lines[end]):
                end += 1
            out.extend(_table(lines[i:end]))
            i = end
            continue
        else:
            out.append(_line(line))
        i += 1
    return "\n".join(out)


def _line(line: str) -> str:
    if heading := _HEADING.match(line):
        return f"*{_inline(_BOLD.sub(r'\1', heading.group(1)))}*"
    if bullet := _BULLET.match(line):
        return f"{bullet.group(1)}• {_inline(bullet.group(2))}"
    return _inline(line)


def _table(rows: list[str]) -> list[str]:
    cells = [_cells(row) for row in rows]
    if len(rows) >= 2 and _TABLE_SEPARATOR.match(rows[1]):
        headers, body = cells[0], cells[2:]
    else:
        headers, body = [], cells
    out = []
    for row in body:
        if not row:
            continue
        parts = [f"• *{_inline(row[0])}*"]
        for index, cell in enumerate(row[1:], start=1):
            if not cell:
                continue
            label = f"{headers[index]}：" if index < len(headers) and headers[index] else ""
            parts.append(f"{label}{_inline(cell)}")
        out.append("｜".join(parts))
    return out


def _cells(row: str) -> list[str]:
    return [cell.strip() for cell in row.strip().strip("|").split("|")]


def _inline(text: str) -> str:
    pieces = _INLINE_CODE.split(text)
    return "".join(piece if index % 2 else _format(piece) for index, piece in enumerate(pieces))


def _format(text: str) -> str:
    text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    text = _LINK.sub(r"<\2|\1>", text)
    text = _BOLD.sub(rf"{_BOLD_MARK}\1{_BOLD_MARK}", text)
    text = _ITALIC.sub(r"_\1_", text)
    return text.replace(_BOLD_MARK, "*")
