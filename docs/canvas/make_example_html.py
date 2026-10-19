"""Generate Canvas-ready HTML versions of the Python files in examples/.

Each examples/NN_name.py becomes docs/canvas/examples/NN_name.html: a single
<pre> block with VS Code "Dark+" (code-server default dark) syntax colors.
Canvas strips <style> tags, so every color is an inline style — paste the
file contents into the Canvas HTML editor.

Usage:  python3 docs/canvas/make_example_html.py
"""

import builtins
import html
import io
import keyword
import re
import token
import tokenize
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC_DIR = ROOT / "examples"
OUT_DIR = Path(__file__).resolve().parent / "examples"

PRE_STYLE = (
    "background:#1E1E1E;color:#D4D4D4;border-radius:6px;padding:12px 14px;"
    "font-family:Consolas,Menlo,Monaco,'Courier New',monospace;font-size:14px;"
    "line-height:1.5;overflow-x:auto;"
)

# Dark+ theme colors
CONTROL = "#C586C0"    # import, if, for, return, ...
STORAGE = "#569CD6"    # def, class, True, None, and/or/not, self
FUNCTION = "#DCDCAA"
CLASS = "#4EC9B0"      # classes, modules, builtin types
VARIABLE = "#9CDCFE"
CONSTANT = "#4FC1FF"   # ALL_CAPS names
STRING = "#CE9178"
ESCAPE = "#D7BA7D"
NUMBER = "#B5CEA8"
COMMENT = "#6A9955"

CONTROL_KW = {
    "import", "from", "as", "if", "elif", "else", "for", "while", "return",
    "break", "continue", "try", "except", "finally", "raise", "with", "pass",
    "yield", "await", "async", "assert", "match", "case",
}
BUILTIN_TYPES = {
    name for name in dir(builtins)
    if isinstance(getattr(builtins, name), type)
}
CONST_RE = re.compile(r"^[A-Z][A-Z0-9_]*$")
ESCAPE_RE = re.compile(r"\\(?:x[0-9a-fA-F]{2}|u[0-9a-fA-F]{4}|N\{[^}]*\}|.)")
FSTRING_START = getattr(token, "FSTRING_START", None)
FSTRING_MIDDLE = getattr(token, "FSTRING_MIDDLE", None)
FSTRING_END = getattr(token, "FSTRING_END", None)


def span(text, color):
    return f'<span style="color:{color}">{html.escape(text, quote=False)}</span>'


def string_html(text, color=STRING):
    """Color a string literal, highlighting escape sequences."""
    out, pos = [], 0
    for m in ESCAPE_RE.finditer(text):
        if m.start() > pos:
            out.append(span(text[pos:m.start()], color))
        out.append(span(m.group(), ESCAPE))
        pos = m.end()
    if pos < len(text):
        out.append(span(text[pos:], color))
    return "".join(out)


def name_color(name, prev, nxt, modules, in_import):
    """Pick a Dark+ color for an identifier from its neighbors."""
    if name in ("True", "False", "None", "self", "cls"):
        return STORAGE
    if keyword.iskeyword(name) or (name in ("match", "case") and prev is None
                                   and nxt not in ("=", "(", ".")):
        return CONTROL if name in CONTROL_KW else STORAGE
    if prev == "class":
        return CLASS
    if prev == "def" or prev == "@":
        return FUNCTION
    if in_import:
        if CONST_RE.match(name):
            return CONSTANT
        if name[0].isupper():
            return CLASS
        return FUNCTION if in_import == "names" else CLASS
    if name in modules:
        return CLASS
    if CONST_RE.match(name):
        return CONSTANT
    if name in BUILTIN_TYPES or (name[0].isupper() and nxt == "("):
        return CLASS
    if nxt == "(":
        return FUNCTION
    return VARIABLE


def highlight(source):
    lines = source.splitlines(keepends=True)
    offsets = [0]
    for line in lines:
        offsets.append(offsets[-1] + len(line))

    def pos(rc):
        return offsets[rc[0] - 1] + rc[1]

    toks = [
        t for t in tokenize.generate_tokens(io.StringIO(source).readline)
        if t.type not in (token.INDENT, token.DEDENT, token.ENDMARKER)
    ]
    # Significant tokens only, for looking at neighbors
    sig = [t for t in toks if t.type not in (token.NL, token.COMMENT)]
    index = {id(t): i for i, t in enumerate(sig)}

    # Names bound by "import x" / "import x as y" are modules
    modules = set()
    for i, t in enumerate(sig):
        if t.string == "import" and (i == 0 or sig[i - 1].type == token.NEWLINE):
            j = i + 1
            while j < len(sig) and sig[j].type != token.NEWLINE:
                if sig[j].type == token.NAME and sig[j].string != "as":
                    nxt = sig[j + 1].string if j + 1 < len(sig) else ""
                    if nxt in (",", "as") or sig[j + 1].type == token.NEWLINE:
                        modules.add(sig[j].string)
                j += 1

    out, cursor, in_import = [], 0, None
    for t in toks:
        start, end = pos(t.start), pos(t.end)
        if start < cursor:
            start = cursor
        if end <= start:
            continue
        if start > cursor:
            out.append(html.escape(source[cursor:start], quote=False))
        text = source[start:end]
        cursor = end

        i = index.get(id(t))
        prev = sig[i - 1].string if i and sig[i - 1].type != token.NEWLINE else None
        nxt = sig[i + 1].string if i is not None and i + 1 < len(sig) else ""

        if t.type == token.NEWLINE:
            in_import = None
        if t.type == token.NAME:
            if text == "from" and prev is None:
                in_import = "module"
            elif text == "import":
                in_import = "names" if in_import == "module" else "module"
                out.append(span(text, CONTROL))
                continue
            color = name_color(text, prev, nxt, modules,
                               in_import if text != "as" else None)
            out.append(span(text, color))
        elif t.type == token.COMMENT:
            out.append(span(text, COMMENT))
        elif t.type == token.NUMBER:
            out.append(span(text, NUMBER))
        elif t.type == token.STRING:
            prefix = re.match(r"[A-Za-z]*", text).group()
            if prefix:
                out.append(span(prefix, STORAGE))
            body = text[len(prefix):]
            if "r" in prefix.lower():
                out.append(span(body, STRING))
            else:
                out.append(string_html(body))
        elif t.type == FSTRING_START:
            prefix = re.match(r"[A-Za-z]*", text).group()
            out.append(span(prefix, STORAGE) + span(text[len(prefix):], STRING))
        elif t.type in (FSTRING_MIDDLE, FSTRING_END):
            out.append(string_html(text))
        elif t.type == token.OP and text in "{}" and _in_fstring(t, toks):
            out.append(span(text, STORAGE))
        elif t.type == token.OP and text == "@" and prev is None:
            out.append(span(text, FUNCTION))
        else:
            out.append(html.escape(text, quote=False))
    out.append(html.escape(source[cursor:], quote=False))
    return "".join(out).rstrip()


def _in_fstring(tok, toks):
    """True if an OP brace token sits inside an f-string replacement field."""
    depth = 0
    for t in toks:
        if t is tok:
            return depth > 0
        if t.type == FSTRING_START:
            depth += 1
        elif t.type == FSTRING_END:
            depth -= 1
    return False


def main():
    OUT_DIR.mkdir(exist_ok=True)
    for src in sorted(SRC_DIR.glob("*.py")):
        body = highlight(src.read_text())
        dest = OUT_DIR / (src.stem + ".html")
        dest.write_text(f'<pre style="{PRE_STYLE}">{body}</pre>\n')
        print(f"wrote {dest.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
