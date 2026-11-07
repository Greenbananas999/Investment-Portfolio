"""A tiny Markdown-to-HTML converter for the plan documents (tables, lists, bold, code).

Only what research/plan/*.md uses: headings, pipe tables, bullet and numbered
lists, block quotes, fenced code, paragraphs, **bold**, `code`, [text](url).
Everything is HTML-escaped first.
"""

import html
import re

_INLINE = [
    (re.compile(r"\*\*(.+?)\*\*"), r"<strong>\1</strong>"),
    (re.compile(r"`([^`]+)`"), r"<code>\1</code>"),
    (re.compile(r"\[([^\]]+)\]\(([^)\s]+)\)"), r'<a href="\2" target="_blank" rel="noopener">\1</a>'),
]


def inline(text):
    s = html.escape(text, quote=False)
    for rx, rep in _INLINE:
        s = rx.sub(rep, s)
    return s


def _cells(line):
    line = line.strip()
    if line.startswith("|"):
        line = line[1:]
    if line.endswith("|"):
        line = line[:-1]
    return [c.strip() for c in re.split(r"(?<!\\)\|", line)]


def _is_sep(line):
    return bool(re.match(r"^\s*\|?\s*:?-{2,}:?\s*(\|\s*:?-{2,}:?\s*)*\|?\s*$", line)) and "-" in line


def md_to_html(text, heading_shift=0):
    lines = text.splitlines()
    out, i, n = [], 0, len(lines)
    while i < n:
        line = lines[i]
        if not line.strip():
            i += 1
            continue
        if line.strip().startswith("```"):
            buf = []
            i += 1
            while i < n and not lines[i].strip().startswith("```"):
                buf.append(lines[i])
                i += 1
            i += 1
            out.append("<pre>" + html.escape("\n".join(buf)) + "</pre>")
            continue
        m = re.match(r"^(#{1,6})\s+(.*)$", line)
        if m:
            lvl = min(6, len(m.group(1)) + heading_shift)
            out.append(f"<h{lvl}>{inline(m.group(2))}</h{lvl}>")
            i += 1
            continue
        if line.lstrip().startswith("|") and i + 1 < n and _is_sep(lines[i + 1]):
            head = _cells(line)
            i += 2
            rows = []
            while i < n and lines[i].lstrip().startswith("|"):
                rows.append(_cells(lines[i]))
                i += 1
            t = ["<div class=\"tablewrap\"><table class=\"md\"><thead><tr>"]
            t += [f"<th>{inline(c)}</th>" for c in head]
            t.append("</tr></thead><tbody>")
            for r in rows:
                t.append("<tr>" + "".join(f"<td>{inline(c)}</td>" for c in r) + "</tr>")
            t.append("</tbody></table></div>")
            out.append("".join(t))
            continue
        if re.match(r"^\s*([-*]|\d+\.)\s+", line):
            ordered = bool(re.match(r"^\s*\d+\.", line))
            items = []
            while i < n and re.match(r"^\s*([-*]|\d+\.)\s+", lines[i]):
                item = re.sub(r"^\s*([-*]|\d+\.)\s+", "", lines[i])
                i += 1
                while i < n and lines[i].strip() and not re.match(r"^\s*([-*]|\d+\.)\s+", lines[i]) \
                        and not lines[i].lstrip().startswith(("|", "#", ">")):
                    item += " " + lines[i].strip()
                    i += 1
                items.append(item)
            tag = "ol" if ordered else "ul"
            out.append(f"<{tag}>" + "".join(f"<li>{inline(x)}</li>" for x in items) + f"</{tag}>")
            continue
        if line.lstrip().startswith(">"):
            buf = []
            while i < n and lines[i].lstrip().startswith(">"):
                buf.append(re.sub(r"^\s*>\s?", "", lines[i]))
                i += 1
            out.append("<blockquote>" + md_to_html("\n".join(buf)) + "</blockquote>")
            continue
        buf = [line.strip()]
        i += 1
        while i < n and lines[i].strip() and not re.match(r"^(#{1,6}\s|\s*\||\s*([-*]|\d+\.)\s+|\s*>|```)", lines[i]):
            buf.append(lines[i].strip())
            i += 1
        out.append("<p>" + inline(" ".join(buf)) + "</p>")
    return "\n".join(out)


def sections(text, level=2):
    """Split a document at headings of `level`; returns [(title, body)] (text before the first is dropped)."""
    marker = "#" * level + " "
    res, cur_t, cur = [], None, []
    for ln in text.splitlines():
        if ln.startswith(marker) and not ln.startswith(marker + "#"):
            if cur_t is not None:
                res.append((cur_t, "\n".join(cur).strip("\n")))
            cur_t, cur = ln[len(marker):].strip(), []
        elif cur_t is not None:
            cur.append(ln)
    if cur_t is not None:
        res.append((cur_t, "\n".join(cur).strip("\n")))
    return res
