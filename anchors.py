"""anchors — what in a file can be named, how far it reaches, and what it reads.

One rule for every kind of file, so that a new language is a scanner and nothing else:

  declaration  a named thing at the file's top level — a function, a class, a constant, a heading, a config key.
               Its name is the anchor's key (`file:name`, `file#heading`). Methods, nested functions and object members
               are part of the declaration that holds them, not anchors of their own.
  extent       the declaration's own text, from its first *attachment* to its end. An attachment sits outside the body
               but changes what the body does — a decorator, `export`/`async`/`declare`, a type annotation, the comment
               lines above an env key. A fingerprint that skipped them read "@require_admin" out as nothing.
  reads        the free names the declaration uses that resolve, in the same file, to another declaration or to an
               import binding. An anchor's fingerprint covers its extent *and, transitively, what it reads*: change
               `LIMIT = 10` and every function that compares against LIMIT is stale, change `from auth import guard`
               to `from noauth import guard` and every function guarded by it is stale. The reading is lexical — a
               name that appears — so it over-includes (a local shadowing a module name) and never under-includes.
  file         the anchor `""` is the whole file: side effects, unnamed statements, anything the scanner cannot name.
  content      fingerprints hash content, not formatting: a token stream for code (comments and blank lines out), a
               canonical value for JSON, comment-free stripped lines for YAML/TOML/INI/env, the raw text for prose —
               in prose the wording *is* the content.

What stops at the file: a declaration that reads another *file* (an import's target, a config value, a subclass in
another module) is not followed — `seen` must be reproducible from what the confirmer had open, and a fingerprint that
reached across files would tie a relation to text nobody read. Across files, the net itself is the mechanism: register
the other file, and relate the anchor that is read (`file:key` of a config, `module.py:symbol`) — see the README.

A scanner returns `Scan(texts, deps, hidden)`: `texts` {key: own text} with `""` for the file, `deps` {key: set of
free names}, `hidden` {name: text} for import bindings that are read but are nobody's anchor. `parts` builds the
closure, `normalize` turns text into what is hashed. Everything else in mangsang sees only those three functions.
"""
import ast
import io
import json
import os
import re

JS_EXT = (".js", ".mjs", ".cjs", ".jsx", ".ts", ".tsx", ".mts", ".cts")
LINE_CONFIG_EXT = (".yaml", ".yml", ".toml", ".ini", ".cfg")


class Scan:
    def __init__(self, texts, deps=None, hidden=None):
        self.texts, self.deps, self.hidden = texts, deps or {}, hidden or {}


def kind_of(path):
    """Which scanner a path gets, by extension (and by the `.env` naming rule: `.env`, `.env.example`, `prod.env`)."""
    base = os.path.basename(path).lower()
    ext = os.path.splitext(base)[1]
    if ext == ".py":
        return "python"
    if ext in JS_EXT:
        return "js"
    if ext in (".md", ".markdown"):
        return "markdown"
    if ext == ".json":
        return "json"
    if ext in (".yaml", ".yml"):
        return "yaml"
    if ext == ".toml":
        return "toml"
    if ext in (".ini", ".cfg"):
        return "ini"
    if base == ".env" or base.startswith(".env.") or base.endswith(".env"):
        return "env"
    return "text"


def scan(path, text):
    """The declarations of one file. Never raises: a file that will not parse is a file with one anchor."""
    text = text.replace("\r\n", "\n")
    kind = kind_of(path)
    fn = {"python": scan_python, "js": scan_js, "markdown": scan_markdown, "json": scan_json, "yaml": scan_yaml,
          "toml": scan_toml, "ini": scan_ini, "env": scan_env}.get(kind)
    return fn(text) if fn else Scan({"": text})


def parts(path, text):
    """{key: [(label, text), ...]} — each anchor's extent first, then, transitively, the same-file declarations and
    import bindings it reads, in a deterministic order. A key with nothing to read has one part, so its fingerprint
    is the fingerprint of its own text (a constant, a heading, a file)."""
    sc = scan(path, text)
    out = {}
    for key, own in sc.texts.items():
        order, seen, todo = [(key, own)], {key}, sorted(sc.deps.get(key, ()))
        while todo:
            name = todo.pop(0)
            k = ":" + name
            if k in sc.texts and k != "":
                if k not in seen:
                    seen.add(k)
                    order.append((k, sc.texts[k]))
                    todo += sorted(n for n in sc.deps.get(k, ()) if ":" + n not in seen and ("import", n) not in seen)
            elif name in sc.hidden and ("import", name) not in seen:
                seen.add(("import", name))
                order.append(("import " + name, sc.hidden[name]))
        out[key] = order
    return out


def normalize(path, text):
    """What is hashed for a fingerprint: the content of `text` with its formatting taken out, by the file's kind."""
    text = text.replace("\r\n", "\n")
    kind = kind_of(path)
    if kind == "python":
        toks = python_tokens(text)
        return "\x01".join(toks) if toks is not None else text
    if kind == "js":
        return "\x01".join("%s\x00%s" % (t.type, t.value) for t in js_tokens(text))
    if kind == "json":
        for candidate in (text, "{" + text + "}"):
            try:
                return json.dumps(json.loads(candidate), sort_keys=True, separators=(",", ":"), ensure_ascii=False)
            except ValueError:
                pass
        return text
    if kind in ("yaml", "toml", "ini", "env"):
        comment = ("#", ";") if kind == "ini" else ("#",)
        return "\n".join(l.rstrip() for l in text.split("\n") if l.strip() and not l.lstrip().startswith(comment))
    return text


# ---------------------------------------------------------------- Markdown

def scan_markdown(text):
    out = {"": text}
    heads = [(m.start(), len(m.group(1)), m.group(2).strip()) for m in re.finditer(r"^(#{1,6}) +(.+?)\s*$", text, re.M)]
    for i, (start, level, title) in enumerate(heads):
        # a section runs to the next heading of its level or higher — except the title (level 1), which runs only to
        # the next heading of any level: as a section it would be the whole file, a duplicate of the file anchor "",
        # and every relation on it went stale on every edit anywhere in the file
        end = next((s for s, l, _ in heads[i + 1:] if l <= level or level == 1), len(text))
        out["#" + title] = text[start:end]
    return Scan(out)


# ---------------------------------------------------------------- Python

def python_tokens(text):
    """The token stream by token *name* (tok_name), comments, blank lines and newlines out — or None when the text will not
    tokenize. Names, not numbers: 3.12 renumbered the token table (OP 54->55) and every numeric fingerprint changed with
    it — a machine on 3.12 disagreed with the same tree on 3.11."""
    import tokenize, token as tok
    try:
        return ["%s\x00%s" % (tok.tok_name[t.type], t.string) for t in tokenize.generate_tokens(io.StringIO(text).readline)
                if t.type not in (tokenize.COMMENT, tokenize.NL, tok.NEWLINE, tokenize.ENCODING, tok.ENDMARKER)]
    except (tokenize.TokenError, IndentationError, SyntaxError):
        return None


def _py_statements(body):
    """Top-level statements, looking through the blocks that only choose between definitions (`if TYPE_CHECKING:`,
    `try: import x except ImportError:`, platform `if`s) — a function defined there is a top-level function."""
    for node in body:
        if isinstance(node, (ast.If, ast.Try, ast.With, ast.AsyncWith)) or type(node).__name__ == "TryStar":
            for field in ("body", "orelse", "finalbody"):
                yield from _py_statements(getattr(node, field, None) or [])
            for h in getattr(node, "handlers", None) or []:
                yield from _py_statements(h.body)
        else:
            yield node


def _py_targets(node):
    if isinstance(node, ast.Name):
        return [node.id]
    if isinstance(node, (ast.Tuple, ast.List)):
        return [n for e in node.elts for n in _py_targets(e)]
    if isinstance(node, ast.Starred):
        return _py_targets(node.value)
    return []


def scan_python(text):
    try:
        tree = ast.parse(text)
    except (SyntaxError, ValueError):
        return Scan({"": text})
    lines = text.split("\n")
    texts, deps, hidden = {}, {}, {}

    def src(node):
        # the extent starts at the first decorator: `@require_admin` is what the function does, before its body does anything
        start = min([node.lineno] + [d.lineno for d in getattr(node, "decorator_list", [])])
        return "\n".join(lines[start - 1:node.end_lineno])

    for node in _py_statements(tree.body):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            for a in node.names:
                if a.name == "*":
                    continue
                bound = a.asname or a.name.split(".")[0]
                hidden[bound] = (hidden[bound] + "\n" + src(node)) if bound in hidden else src(node)
            continue
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names = [node.name]
        elif isinstance(node, ast.Assign):
            names = [n for t in node.targets for n in _py_targets(t)]
        elif isinstance(node, ast.AnnAssign):
            names = _py_targets(node.target)
        else:
            names = []
        if not names:
            continue
        s = src(node)
        free = {n.id for n in ast.walk(node) if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load)}
        for name in names:
            key = ":" + name
            # the same name defined twice (an `if`/`else` pair, a redefinition) is one anchor holding both texts — the first
            # used to be overwritten by the second, and a change to it was invisible
            texts[key] = (texts[key] + "\n" + s) if key in texts else s
            deps[key] = deps.get(key, set()) | (free - {name})
    return Scan({"": text, **texts}, deps, hidden)


# ---------------------------------------------------------------- JavaScript / TypeScript

class Tok:
    __slots__ = ("type", "value", "line", "start", "end")

    def __init__(self, type_, value, line, start, end):
        self.type, self.value, self.line, self.start, self.end = type_, value, line, start, end

    def __repr__(self):
        return "%s(%r)" % (self.type, self.value)


_JS_PUNCT = sorted([">>>=", "...", "===", "!==", "**=", "<<=", ">>=", ">>>", "&&=", "||=", "??=", "==", "!=", "<=", ">=", "&&", "||",
                    "??", "?.", "++", "--", "+=", "-=", "*=", "/=", "%=", "&=", "|=", "^=", "**", "<<", ">>", "=>", "{", "}", "(",
                    ")", "[", "]", ";", ",", "<", ">", "+", "-", "*", "/", "%", "&", "|", "^", "!", "~", "?", ":", "=", ".", "@"],
                   key=len, reverse=True)
_JS_ID = re.compile(r"[#$A-Za-z_\u0080-￿][$\w\u0080-￿]*")
_JS_NUM = re.compile(r"0[xXbBoO][0-9A-Fa-f_]+n?|\d[\d_]*(?:\.\d*)?(?:[eE][+-]?\d+)?n?|\.\d+(?:[eE][+-]?\d+)?")
_REGEX_AFTER_WORD = {"return", "typeof", "instanceof", "in", "of", "new", "delete", "void", "throw", "case", "do", "else", "yield", "await"}
JS_KEYWORDS = set("""break case catch class const continue debugger default delete do else export extends finally for function if import
in instanceof new return super switch this throw try typeof var void while with yield let static enum await async of as from get set
implements interface package private protected public type readonly declare namespace module abstract keyof infer is unique satisfies
never unknown any string number boolean object symbol bigint null undefined true false NaN Infinity constructor require""".split())


def _read_js_string(text, i):
    """i at the opening quote; returns the index after the closing quote, or None when the line ends first (JSX text
    like `Don't`, where the quote is no string at all)."""
    q, j, n = text[i], i + 1, len(text)
    while j < n:
        c = text[j]
        if c == "\\":
            j += 2
            continue
        if c == q:
            return j + 1
        if c == "\n":
            return None
        j += 1
    return None


def js_tokens(text):
    """Tokens with their offsets — comments dropped, template literals as chunks around `${ }`, a `/` read as a regular
    expression where one can stand (statement start, after an operator or a keyword like `return`) and as division
    elsewhere; after `<` it is a JSX closing tag. Never raises: what is not a string, regex or comment is punctuation."""
    toks, i, n, line = [], 0, len(text), 1
    tpl_marks, brace = [], 0   # brace depths at which a template literal resumes after its `${ ... }`

    def emit(type_, start, end):
        toks.append(Tok(type_, text[start:end], line, start, end))

    def read_template(j):
        """j just after a backtick or a resuming `}`; emits the chunk; returns the new i (after ` or after `${`)."""
        nonlocal line, brace
        start = j
        while j < n:
            c = text[j]
            if c == "\\":
                j += 2
                continue
            if c == "`":
                emit("tpl", start, j)
                line += text.count("\n", start, j)
                return j + 1
            if c == "$" and text.startswith("${", j):
                emit("tpl", start, j)
                line += text.count("\n", start, j)
                emit("punct", j, j + 2)
                tpl_marks.append(brace)
                brace += 1
                return j + 2
            j += 1
        emit("tpl", start, n)   # unterminated: the rest of the file is the template
        return n

    while i < n:
        c = text[i]
        if c == "\n":
            line += 1
            i += 1
            continue
        if c in " \t\r\f\v":
            i += 1
            continue
        if text.startswith("//", i):
            j = text.find("\n", i)
            i = n if j < 0 else j
            continue
        if text.startswith("/*", i):
            j = text.find("*/", i + 2)
            j = n if j < 0 else j + 2
            line += text.count("\n", i, j)
            i = j
            continue
        if c in "\"'":
            j = _read_js_string(text, i)
            if j is not None:
                emit("str", i, j)
                i = j
                continue
            emit("punct", i, i + 1)
            i += 1
            continue
        if c == "`":
            i = read_template(i + 1)
            continue
        if c == "}" and tpl_marks and brace == tpl_marks[-1] + 1:
            tpl_marks.pop()
            brace -= 1
            emit("punct", i, i + 1)
            i = read_template(i + 1)
            continue
        if c == "/":
            prev = toks[-1] if toks else None
            regex_ok = prev is None or (prev.type == "punct" and prev.value not in (")", "]", "<")) or \
                (prev.type == "id" and prev.value in _REGEX_AFTER_WORD)
            if regex_ok:
                j, in_class = i + 1, False
                while j < n and text[j] != "\n":
                    ch = text[j]
                    if ch == "\\":
                        j += 2
                        continue
                    if ch == "[":
                        in_class = True
                    elif ch == "]":
                        in_class = False
                    elif ch == "/" and not in_class:
                        j += 1
                        while j < n and text[j].isalpha():
                            j += 1
                        emit("re", i, j)
                        i = j
                        break
                    j += 1
                else:
                    emit("punct", i, i + 1)   # no closing slash on this line: a division after all
                    i += 1
                continue
        m = _JS_NUM.match(text, i)
        if m and (c.isdigit() or (c == "." and i + 1 < n and text[i + 1].isdigit())):
            emit("num", i, m.end())
            i = m.end()
            continue
        m = _JS_ID.match(text, i)
        if m:
            emit("id", i, m.end())
            i = m.end()
            continue
        for p in _JS_PUNCT:
            if text.startswith(p, i):
                if p == "{":
                    brace += 1
                elif p == "}":
                    brace -= 1
                emit("punct", i, i + len(p))
                i += len(p)
                break
        else:
            emit("punct", i, i + 1)   # a character the language does not have; kept so the stream never loses text
            i += 1
    return toks


_OPEN, _CLOSE = {"{": "}", "(": ")", "[": "]", "${": "}"}, {"}", ")", "]"}   # `${` opens a template hole its `}` closes
_CONTINUES_BEFORE = {".", "?.", ",", "(", "[", "+", "-", "*", "/", "%", "?", ":", "=", "&&", "||", "??", "=>", "==", "===", "!=", "!==",
                     "<", ">", "<=", ">=", "&", "|", "^", "**", "instanceof", "in", "as", "extends", "implements", "else", "catch",
                     "finally", "while", "satisfies"}


def _js_statement_end(toks, j):
    """Index after the last token of the statement starting at j: a `;` at depth 0, or the ASI line break — a token on a
    new line, at depth 0, after something that can end a statement, before something that can start one."""
    n, depth = len(toks), 0
    while j < n:
        t = toks[j]
        if t.type == "punct":
            if t.value in _OPEN:
                depth += 1
            elif t.value in _CLOSE:
                depth -= 1
                if depth < 0:
                    return j   # a closing bracket we did not open: the statement ended before it
            elif t.value == ";" and depth == 0:
                return j + 1
        if depth == 0 and j + 1 < n and toks[j + 1].line > t.line:
            nxt = toks[j + 1]
            ends = not (t.type == "punct" and t.value not in _CLOSE) and not (t.type == "id" and t.value in ("return", "typeof", "new", "else", "case"))
            if ends and nxt.value not in _CONTINUES_BEFORE:
                return j + 1
        j += 1
    return n


def _js_body_end(toks, j):
    """From j, the index after the `}` that closes the first `{` met at depth 0 (a function or class body)."""
    n, depth, opened = len(toks), 0, False
    while j < n:
        t = toks[j]
        if t.type == "punct":
            if t.value in _OPEN:
                depth += 1
                opened = opened or t.value == "{" and depth == 1
            elif t.value in _CLOSE:
                depth -= 1
                if depth == 0 and opened:
                    return j + 2 if j + 1 < n and toks[j + 1].value == ";" and toks[j + 1].line == t.line else j + 1
                if depth < 0:
                    return j
            elif t.value == ";" and depth == 0 and not opened:
                return j + 1   # `declare function f(): void;` — a body-less declaration
        j += 1
    return n


def _js_pattern_names(toks, j, end):
    """Names bound by a destructuring pattern starting at j (`{a, b: c, ...d}` / `[x, y]`), up to `end`."""
    names, depth, k = [], 0, j
    while k < end:
        t = toks[k]
        if t.type == "punct" and t.value in ("{", "["):
            depth += 1
        elif t.type == "punct" and t.value in ("}", "]"):
            depth -= 1
            if depth == 0:
                return names, k + 1
        elif t.type == "punct" and t.value == "=":
            # a default value: skip it to the next `,` at this depth
            d = 0
            k += 1
            while k < end and not (d == 0 and toks[k].value in (",", "}", "]")):
                if toks[k].value in _OPEN:
                    d += 1
                elif toks[k].value in _CLOSE:
                    d -= 1
                k += 1
            continue
        elif t.type == "id" and t.value not in JS_KEYWORDS:
            nxt = toks[k + 1] if k + 1 < end else None
            if not (nxt and nxt.value == ":"):   # `{key: name}` binds name, not key
                names.append(t.value)
        k += 1
    return names, k


def _js_skip_type(toks, k, end):
    """After a `:` type annotation: skip to the `=` or `,` at depth 0 that ends it (angle brackets count as depth here)."""
    depth = 0
    while k < end:
        v = toks[k].value
        if v in _OPEN or v == "<":
            depth += 1
        elif v in _CLOSE or v == ">":
            depth -= 1
        elif v == ">>":
            depth -= 2
        elif depth <= 0 and v in ("=", ",", ";"):
            return k
        k += 1
    return k


def _js_declarators(toks, j, end):
    """`const a = 1, {b, c} = o, d: T = e` -> [a, b, c, d]."""
    names, k = [], j
    while k < end:
        t = toks[k]
        if t.type == "id" and t.value not in JS_KEYWORDS:
            names.append(t.value)
            k += 1
        elif t.type == "punct" and t.value in ("{", "["):
            got, k = _js_pattern_names(toks, k, end)
            names += got
        else:
            k += 1
            continue
        if k < end and toks[k].value == "!":   # TS definite assignment `x!: T`
            k += 1
        if k < end and toks[k].value == ":":
            k = _js_skip_type(toks, k + 1, end)
        if k < end and toks[k].value == "=":
            depth = 0
            k += 1
            while k < end and not (depth == 0 and toks[k].value == ","):
                if toks[k].value in _OPEN:
                    depth += 1
                elif toks[k].value in _CLOSE:
                    depth -= 1
                k += 1
        if k < end and toks[k].value == ",":
            k += 1
    return names


def _js_import_bindings(toks, j, end):
    """`import a, {b as c, type d}, * as e from 'm'` -> [a, c, d, e]; `import 'm'` -> []; `import x = require('m')` -> [x]."""
    names, k = [], j
    while k < end:
        t = toks[k]
        if t.type == "str" or t.value in ("from", "=", ";"):
            break
        if t.type == "id" and t.value not in ("type", "typeof"):
            nxt = toks[k + 1] if k + 1 < end else None
            if nxt and nxt.value == "as":
                k += 2
                continue   # the `as` target is what is bound; it is read on the next round
            if t.value not in ("as",):
                names.append(t.value)
        k += 1
    return names


def scan_js(text):
    toks = js_tokens(text)
    texts, deps, hidden = {}, {}, {}
    top = []   # (names, start, end)
    i, n = 0, len(toks)
    while i < n:
        j = i
        while j < n and toks[j].value == "@":   # a decorator: `@name.path(args)`
            j += 1
            while j < n and (toks[j].type == "id" or toks[j].value == "."):
                j += 1
            if j < n and toks[j].value == "(":
                depth = 0
                while j < n:
                    if toks[j].value in _OPEN:
                        depth += 1
                    elif toks[j].value in _CLOSE:
                        depth -= 1
                        if depth == 0:
                            j += 1
                            break
                    j += 1
        mods = set()
        while j < n and toks[j].type == "id" and toks[j].value in ("export", "default", "declare", "abstract", "async") and \
                (toks[j].value != "async" or (j + 1 < n and toks[j + 1].value == "function")) and \
                (toks[j].value != "default" or "export" in mods):
            mods.add(toks[j].value)
            j += 1
        t = toks[j] if j < n else None
        nxt = toks[j + 1] if j + 1 < n else None
        names, end = [], None
        if t is None:
            break
        v = t.value if t.type == "id" else None
        if v == "function":
            k = j + 1
            if k < n and toks[k].value == "*":
                k += 1
            if k < n and toks[k].type == "id" and toks[k].value != "(":
                names = [toks[k].value]
            elif "default" in mods:
                names = ["default"]
            end = _js_body_end(toks, k)
        elif v == "class" or (v == "abstract" and nxt and nxt.value == "class"):
            k = j + 1 if v == "class" else j + 2
            if k < n and toks[k].type == "id" and toks[k].value not in ("extends", "implements", "{"):
                names = [toks[k].value]
            elif "default" in mods:
                names = ["default"]
            end = _js_body_end(toks, k)
        elif v in ("interface", "enum") and nxt and nxt.type == "id" or (v == "const" and nxt and nxt.value == "enum"):
            k = j + 2 if v == "const" else j + 1
            names = [toks[k].value]
            end = _js_body_end(toks, k)
        elif v in ("namespace", "module") and nxt and nxt.type in ("id", "str") and j + 2 < n and toks[j + 2].value in ("{", "."):
            names = [nxt.value if nxt.type == "id" else nxt.value[1:-1]]
            end = _js_body_end(toks, j + 1)
        elif v == "type" and nxt and nxt.type == "id" and j + 2 < n and toks[j + 2].value in ("=", "<"):
            names = [nxt.value]
            end = _js_statement_end(toks, j)
        elif v in ("const", "let", "var"):
            end = _js_statement_end(toks, j)
            names = _js_declarators(toks, j + 1, end)
        elif v == "import" and not (nxt and nxt.value in ("(", ".")):
            end = _js_statement_end(toks, j)
            s = text[toks[i].start:toks[end - 1].end]
            for name in _js_import_bindings(toks, j + 1, end):
                hidden[name] = (hidden[name] + "\n" + s) if name in hidden else s
            i = end
            continue
        elif v in ("module", "exports") and nxt and nxt.value == ".":
            # CommonJS: `module.exports = ...`, `exports.foo = ...`, `module.exports.foo = ...`
            k, path = j, []
            while k < n and (toks[k].type == "id" or toks[k].value == "."):
                if toks[k].type == "id":
                    path.append(toks[k].value)
                k += 1
            end = _js_statement_end(toks, j)
            if k < n and toks[k].value == "=" and path[:1] in (["module"], ["exports"]) and (path[0] != "module" or path[1:2] == ["exports"]):
                names = [".".join(path)]
        elif "default" in mods:
            end = _js_statement_end(toks, j)
            names = ["default"]
        else:
            end = _js_statement_end(toks, j)
        end = max(end if end is not None else j + 1, j + 1)
        if names:
            top.append((names, i, end))
        i = end
    for names, start, end in top:
        s = text[toks[start].start:toks[end - 1].end]
        free = set()
        for k in range(start, end):
            t = toks[k]
            if t.type != "id" or t.value in JS_KEYWORDS or t.value.startswith("#"):
                continue
            prev = toks[k - 1] if k > start else None
            after = toks[k + 1] if k + 1 < end else None
            if prev is not None and prev.value in (".", "?."):
                continue   # a property, not a name
            if after is not None and after.value == ":" and not (prev is not None and prev.value == "?"):
                continue   # a key or a parameter being typed
            free.add(t.value)
        for name in names:
            key = ":" + name
            texts[key] = (texts[key] + "\n" + s) if key in texts else s
            deps[key] = deps.get(key, set()) | (free - set(names))
    return Scan({"": text, **texts}, deps, hidden)


# ---------------------------------------------------------------- data files: JSON, YAML, TOML, INI, env

def _json_string_end(text, i):
    j, n = i + 1, len(text)
    while j < n:
        if text[j] == "\\":
            j += 2
        elif text[j] == '"':
            return j + 1
        else:
            j += 1
    raise ValueError("unterminated string")


def scan_json(text):
    """Top-level keys of a JSON object (`package.json:scripts`, `tsconfig.json:compilerOptions`), each with its raw
    `"key": value` text so a quote is what a reader sees. A root array, or a file that will not scan, is one anchor."""
    out = {"": text}
    try:
        i, n = 0, len(text)
        while i < n and text[i].isspace():
            i += 1
        if i >= n or text[i] != "{":
            return Scan(out)
        i += 1
        while i < n:
            while i < n and text[i] in " \t\r\n,":
                i += 1
            if i >= n or text[i] == "}":
                break
            if text[i] != '"':
                return Scan({"": text})
            key_start = i
            i = _json_string_end(text, i)
            key = json.loads(text[key_start:i])
            while i < n and text[i].isspace():
                i += 1
            if text[i] != ":":
                return Scan({"": text})
            i += 1
            depth = 0
            while i < n:
                c = text[i]
                if c == '"':
                    i = _json_string_end(text, i)
                    continue
                if c in "{[":
                    depth += 1
                elif c in "}]":
                    if depth == 0:
                        break
                    depth -= 1
                elif c == "," and depth == 0:
                    break
                i += 1
            k = ":" + key
            s = text[key_start:i].rstrip()
            out[k] = (out[k] + "\n" + s) if k in out else s
    except (ValueError, IndexError):
        return Scan({"": text})
    return Scan(out)


def _line_blocks(text, is_key, is_break=lambda l: False, attach_comments=False):
    """{key: text} for a line-oriented file: a key line opens a block that runs to the next key line (or a break line).
    With attach_comments, the comment lines directly above a key belong to it (an env sample documents each variable there)."""
    out, lines = {}, text.split("\n")
    starts = []
    for idx, line in enumerate(lines):
        key = is_key(line)
        if key is not None:
            starts.append((idx, key))
        elif is_break(line):
            starts.append((idx, None))
    for pos, (idx, key) in enumerate(starts):
        if key is None:
            continue
        end = starts[pos + 1][0] if pos + 1 < len(starts) else len(lines)
        begin = idx
        if attach_comments:
            while begin > 0 and lines[begin - 1].lstrip().startswith("#") and (pos == 0 or begin - 1 > starts[pos - 1][0]):
                begin -= 1
        s = "\n".join(lines[begin:end]).rstrip("\n")
        out[key] = (out[key] + "\n" + s) if key in out else s
    return out


_YAML_KEY = re.compile(r'''^(?:"([^"]*)"|'([^']*)'|([A-Za-z0-9_.\-/$]+))\s*:(?:\s|$)''')
_YAML_BREAK = re.compile(r"^(---|\.\.\.)(\s|$)")


def scan_yaml(text):
    """Top-level keys (column 0). YAML needs no parser for that much: a key at column 0 opens a block that runs to the
    next column-0 key or document marker. Nested keys are inside their top-level key's block."""
    def key(line):
        m = _YAML_KEY.match(line)
        return (m.group(1) or m.group(2) or m.group(3)) if m else None
    return Scan({"": text, **{":" + k: v for k, v in _line_blocks(text, key, lambda l: bool(_YAML_BREAK.match(l))).items()}})


_TOML_TABLE = re.compile(r"^\[\[?\s*([^\]]+?)\s*\]\]?\s*(#.*)?$")
_TOML_KEY = re.compile(r'''^((?:[A-Za-z0-9_\-]+|"[^"]*"|'[^']*')(?:\.(?:[A-Za-z0-9_\-]+|"[^"]*"|'[^']*'))*)\s*=''')


def scan_toml(text):
    """Tables (`pyproject.toml:project`, `pyproject.toml:tool.pytest.ini_options`) and the bare keys before the first table."""
    seen_table = [False]

    def key(line):
        m = _TOML_TABLE.match(line)
        if m:
            seen_table[0] = True
            return m.group(1)
        if not seen_table[0]:
            m = _TOML_KEY.match(line)
            return m.group(1).replace('"', "").replace("'", "") if m else None
        return None
    return Scan({"": text, **{":" + k: v for k, v in _line_blocks(text, key).items()}})


_INI_SECTION = re.compile(r"^\[([^\]]+)\]\s*([#;].*)?$")
_INI_KEY = re.compile(r"^([^\s=:;#\[][^=:]*?)\s*[=:]")


def scan_ini(text):
    seen_section = [False]

    def key(line):
        m = _INI_SECTION.match(line)
        if m:
            seen_section[0] = True
            return m.group(1).strip()
        if not seen_section[0]:
            m = _INI_KEY.match(line)
            return m.group(1) if m else None
        return None
    return Scan({"": text, **{":" + k: v for k, v in _line_blocks(text, key).items()}})


_ENV_KEY = re.compile(r"^\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_.\-]*)\s*=")


def scan_env(text):
    """`KEY=value` lines, one anchor each (`.env.example:DATABASE_URL`), with the comment lines above the key — in a
    sample env file those lines are the variable's documentation, and the file lists the variables a deployment needs."""
    def key(line):
        m = _ENV_KEY.match(line)
        return m.group(1) if m else None
    return Scan({"": text, **{":" + k: v for k, v in _line_blocks(text, key, lambda l: not l.strip(), attach_comments=True).items()}})
