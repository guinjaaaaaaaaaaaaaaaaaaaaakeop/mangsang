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
CSS_EXT = (".css", ".scss", ".sass", ".less")
HTML_EXT = (".html", ".htm", ".xhtml")
COMPONENT_EXT = (".astro", ".vue", ".svelte")
BLOCK_EXT = (".prisma", ".graphql", ".gql", ".proto")
NESTED_KEY_DEPTH = 3   # `openapi.yaml:paths./users/{id}`, `compose.yaml:services.web`, `tokens.json:color.primary.500`


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
    if ext in (".md", ".markdown", ".mdx"):
        return "markdown"
    if ext in CSS_EXT:
        return "css"
    if ext in HTML_EXT:
        return "html"
    if ext in COMPONENT_EXT:
        return "component"
    if ext == ".sql":
        return "sql"
    if ext in BLOCK_EXT:
        return "block"
    if base == "dockerfile" or base.startswith("dockerfile.") or base.endswith(".dockerfile"):
        return "dockerfile"
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
          "toml": scan_toml, "ini": scan_ini, "env": scan_env, "css": scan_css, "html": scan_html, "component": scan_component,
          "sql": scan_sql, "block": scan_block, "dockerfile": scan_dockerfile}.get(kind)
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
    if kind in ("yaml", "toml", "ini", "env", "dockerfile"):
        comment = ("#", ";") if kind == "ini" else ("#",)
        return "\n".join(l.rstrip() for l in text.split("\n") if l.strip() and not l.lstrip().startswith(comment))
    if kind == "css":
        return _css_normalize(text)
    if kind == "sql":
        return " ".join(_sql_strip_comments(text).split())
    if kind == "block":
        return " ".join(re.sub(r"//[^\n]*|#[^\n]*|/\*.*?\*/", " ", text, flags=re.S).split())
    if kind in ("html", "component"):
        return " ".join(re.sub(r"<!--.*?-->", " ", text, flags=re.S).split())
    if kind == "markdown":
        # a section runs to the next heading, so its blank lines before that heading are the layout of what follows: the last
        # section of a file ended at one newline, and adding a section after it staled it with no word changed (2026-09-30)
        return text.rstrip() + "\n"
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
        elif isinstance(node, ast.Expr) and isinstance(node.value, ast.Call) and node.value.args \
                and isinstance(node.value.args[0], ast.Constant) and isinstance(node.value.args[0].value, str):
            # a registration: `app.add_url_rule("/users", …)`, `urlpatterns.append(path("x", …))` — a top-level call whose first
            # argument is a string names what it registers; the string is the name (`app.add_url_rule("/users")`)
            chain, f = [], node.value.func
            while isinstance(f, ast.Attribute):
                chain.insert(0, f.attr)
                f = f.value
            names = ['%s("%s")' % (".".join([f.id] + chain), node.value.args[0].value)] if isinstance(f, ast.Name) and f.id not in ("print",) else []
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


_NOT_REGISTRATION = {"console", "require", "import", "alert", "print", "throw", "return", "new", "typeof", "await", "void", "delete", "if", "for", "while", "switch", "case"}


def _js_registration(toks, j, end):
    """`app.get("/users", handler)`, `describe("login", () => …)`, `it("rejects a bad password", …)`, `router.post("/x")`:
    a statement that is a call whose first argument is a string — it registers something, and the string names it.
    Returns the anchor name `callee("string")` or None."""
    k, chain = j, []
    while k < end and toks[k].type == "id":
        chain.append(toks[k].value)
        if k + 1 < end and toks[k + 1].value == ".":
            k += 2
        else:
            k += 1
            break
    if not chain or chain[0] in _NOT_REGISTRATION or chain[0] in JS_KEYWORDS or k >= end or toks[k].value != "(":
        return None
    if k + 1 < end and toks[k + 1].type == "str":
        return '%s("%s")' % (".".join(chain), toks[k + 1].value[1:-1])
    return None


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
            reg = _js_registration(toks, j, end)
            if reg:
                names = [reg]
                # what the registration's callbacks register in turn: `describe("auth", () => { it("rejects …", …) })`,
                # `router.route("/x").get(…)` — each is an anchor of its own, named by its own string; the outer holds them all
                for k in range(j + 1, end):
                    prev = toks[k - 1]
                    if toks[k].type == "id" and prev.type == "punct" and prev.value in ("{", "}", ";", ")"):
                        inner_end = _js_statement_end(toks, k)
                        inner = _js_registration(toks, k, min(inner_end, end))
                        if inner:
                            top.append(([inner], k, min(inner_end, end)))
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


def _json_members(text, i, path, out, depth):
    """i at `{`: records `"key": value` spans as anchors `path.key`, recursing into object values to NESTED_KEY_DEPTH.
    Returns the index after the closing `}`."""
    n = len(text)
    i += 1
    while i < n:
        while i < n and text[i] in " \t\r\n,":
            i += 1
        if i >= n:
            raise ValueError("unterminated object")
        if text[i] == "}":
            return i + 1
        if text[i] != '"':
            raise ValueError("not a key")
        key_start = i
        i = _json_string_end(text, i)
        key = ".".join(path + [json.loads(text[key_start:i])])
        while i < n and text[i].isspace():
            i += 1
        if i >= n or text[i] != ":":
            raise ValueError("no colon")
        i += 1
        while i < n and text[i].isspace():
            i += 1
        if i < n and text[i] == "{" and depth < NESTED_KEY_DEPTH:
            i = _json_members(text, i, path + [json.loads(text[key_start:_json_string_end(text, key_start)])], out, depth + 1)
        else:
            i = _json_value_end(text, i)
        k = ":" + key
        span = text[key_start:i].rstrip()
        out[k] = (out[k] + "\n" + span) if k in out else span
    raise ValueError("unterminated object")


def _json_value_end(text, i):
    """i at a value: the index after it (before the `,` or closing bracket that follows)."""
    n, depth = len(text), 0
    while i < n:
        c = text[i]
        if c == '"':
            i = _json_string_end(text, i)
            continue
        if c in "{[":
            depth += 1
        elif c in "}]":
            if depth == 0:
                return i
            depth -= 1
        elif c == "," and depth == 0:
            return i
        i += 1
    return i


def scan_json(text):
    """Keys of a JSON object, nested to NESTED_KEY_DEPTH as dotted paths (`package.json:scripts`, `package.json:scripts.test`,
    `tokens.json:color.primary.500`), each with its raw `"key": value` text so a quote is what a reader sees. A root
    array, or a file that will not scan, is one anchor."""
    out = {}
    try:
        i, n = 0, len(text)
        while i < n and text[i].isspace():
            i += 1
        if i >= n or text[i] != "{":
            return Scan({"": text})
        _json_members(text, i, [], out, 1)
    except (ValueError, IndexError):
        return Scan({"": text})
    return Scan({"": text, **out})


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


_YAML_KEY = re.compile(r'''^(\s*)(?:"([^"]*)"|'([^']*)'|([A-Za-z0-9_.\-/$<>{}*@]+))\s*:(?:\s+(.*))?$''')
_YAML_BREAK = re.compile(r"^(---|\.\.\.)(\s|$)")


def scan_yaml(text):
    """Mapping keys, nested to NESTED_KEY_DEPTH as dotted paths (`compose.yaml:services`, `compose.yaml:services.web`,
    `openapi.yaml:paths./users/{id}`), by indentation — YAML needs no parser for that much. A key's block runs to the
    next line indented no deeper than the key (a list item, a document marker, a shallower key end it too). Keys inside
    list items (`- name: x`) and inside block scalars (`|`, `>`) are content, not anchors."""
    lines, out = text.split("\n"), {}
    stack = []   # [(indent, key)] of the open mapping keys
    opened = []  # [(indent, dotted, start_line)] anchors not yet closed
    skip_deeper_than = None   # inside a block scalar: skip lines indented deeper than this

    def close(upto_indent, idx):
        while opened and opened[-1][0] >= upto_indent:
            ind, dotted, start = opened.pop()
            span = "\n".join(lines[start:idx]).rstrip("\n")
            k = ":" + dotted
            out[k] = (out[k] + "\n" + span) if k in out else span
        while stack and stack[-1][0] >= upto_indent:
            stack.pop()

    for idx, line in enumerate(lines):
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        indent = len(line) - len(line.lstrip(" "))
        if skip_deeper_than is not None:
            if indent > skip_deeper_than:
                continue
            skip_deeper_than = None
        if _YAML_BREAK.match(line):
            close(0, idx)
            continue
        m = _YAML_KEY.match(line)
        if line.lstrip().startswith("- ") or line.strip() == "-":
            close(indent + 1, idx)
            skip_deeper_than = indent   # the item's own mapping is content of the list, not keys of the document
            continue
        if not m:
            close(indent + 1, idx)
            continue
        close(indent, idx)
        key = m.group(2) or m.group(3) or m.group(4)
        value = (m.group(5) or "").strip()
        dotted = ".".join([k for _, k in stack] + [key])
        if len(stack) < NESTED_KEY_DEPTH:
            opened.append((indent, dotted, idx))
        stack.append((indent, key))
        if value.split("#")[0].strip() in ("|", ">", "|-", ">-", "|+", ">+"):
            skip_deeper_than = indent
    close(0, len(lines))
    while out and "" in out:
        del out[""]
    return Scan({"": text, **out})


_TOML_TABLE = re.compile(r"^\[\[?\s*([^\]]+?)\s*\]\]?\s*(#.*)?$")
_TOML_KEY = re.compile(r'''^((?:[A-Za-z0-9_\-]+|"[^"]*"|'[^']*')(?:\.(?:[A-Za-z0-9_\-]+|"[^"]*"|'[^']*'))*)\s*=''')


def scan_toml(text):
    """Tables (`pyproject.toml:project`, `pyproject.toml:tool.pytest.ini_options`), the bare keys before the first table, and
    the keys inside a table as `table.key` (`pyproject.toml:project.dependencies`) — a table's anchor holds the whole table;
    a key's block is its line and the continuation lines (a multi-line array) until the next key or table."""
    tables = _line_blocks(text, lambda l: _TOML_TABLE.match(l).group(1) if _TOML_TABLE.match(l) else None)
    blocks, current, open_key = {}, None, None
    for line in text.split("\n"):
        m = _TOML_TABLE.match(line)
        if m:
            current, open_key = m.group(1), None
            continue
        m = _TOML_KEY.match(line)
        if m:
            k = m.group(1).replace('"', "").replace("'", "")
            open_key = "%s.%s" % (current, k) if current else k
            blocks[open_key] = (blocks[open_key] + "\n" + line) if open_key in blocks else line
        elif open_key and line.strip() and not line.lstrip().startswith("#"):
            blocks[open_key] += "\n" + line
    return Scan({"": text, **{":" + k: v for k, v in tables.items()}, **{":" + k: v for k, v in blocks.items()}})


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


# ---------------------------------------------------------------- CSS / SCSS

_CSS_GROUP_AT = ("@media", "@supports", "@layer", "@container", "@scope", "@document")
_CSS_VAR_DECL = re.compile(r"^\s*(--[\w-]+|\$[\w-]+)\s*:")
_CSS_READS = re.compile(r"var\(\s*(--[\w-]+)|(\$[\w-]+)|@include\s+([\w-]+)|@extend\s+(%[\w-]+|\.[\w-]+)|animation(?:-name)?\s*:\s*([^;{}]+)")


def _css_strip_comments(text):
    text = re.sub(r"/\*.*?\*/", lambda m: " " * len(m.group(0)), text, flags=re.S)   # same length: offsets stay valid
    return re.sub(r"(?m)//[^\n]*", lambda m: " " * len(m.group(0)), text) if "//" in text else text


def _css_normalize(text):
    t = " ".join(_css_strip_comments(text).split())
    return re.sub(r"\s*([{}:;,()>+~])\s*", r"\1", t).replace(";}", "}")


def _css_selectors(prelude):
    """`a, b:is(c, d)` -> ["a", "b:is(c, d)"]: one anchor per selector, so `.btn` is `.btn` wherever it is listed."""
    out, depth, cur = [], 0, ""
    for c in prelude:
        if c == "(":
            depth += 1
        elif c == ")":
            depth -= 1
        if c == "," and depth == 0:
            out.append(cur.strip())
            cur = ""
        else:
            cur += c
    out.append(cur.strip())
    return [x for x in out if x]


def _css_statements(text, start, end):
    """(stmt_start, brace_or_None, stmt_end) for the statements of one block level: `prelude { … }` or `declaration;`."""
    i = start
    while i < end:
        while i < end and text[i] in " \t\r\n;":
            i += 1
        if i >= end:
            return
        s0, depth, j = i, 0, i
        while j < end:
            c = text[j]
            if c in "\"'":
                k = j + 1
                while k < end and text[k] != c and text[k] != "\n":
                    k += 2 if text[k] == "\\" else 1
                j = k + 1
                continue
            if c == "(":
                depth += 1
            elif c == ")":
                depth -= 1
            elif depth == 0 and c == "{":
                d, k = 1, j + 1
                while k < end and d:
                    ch = text[k]
                    if ch in "\"'":
                        m = k + 1
                        while m < end and text[m] != ch and text[m] != "\n":
                            m += 2 if text[m] == "\\" else 1
                        k = m + 1
                        continue
                    d += (ch == "{") - (ch == "}")
                    k += 1
                yield s0, j, k
                i = k
                break
            elif depth == 0 and c == ";":
                yield s0, None, j + 1
                i = j + 1
                break
            j += 1
        else:
            yield s0, None, end
            return


def scan_css(text):
    """Rules by selector (`styles.css:.btn`, `styles.css:.nav a`), at-rules by prelude (`@media (max-width: 600px)`,
    `@keyframes fade`, `@font-face`, `@mixin card`), custom properties and SCSS variables one anchor each
    (`styles.css:--color-primary`, `styles.css:$gutter`). A rule inside a group at-rule (`@media … { .nav { … } }`) is
    also `.nav` — the same selector twice is one anchor holding both texts, so `.nav` covers its mobile branch. A rule
    reads what its declarations use: `var(--x)`, `$x`, `@include m`, `@extend %p`, `animation: fade` -> `@keyframes fade`.
    The cascade (order, specificity) is not a read the fingerprint sees; the file anchor does."""
    clean = _css_strip_comments(text)
    texts, deps = {}, {}

    def add(key, span, free):
        k = ":" + key
        texts[k] = (texts[k] + "\n" + span) if k in texts else span
        deps[k] = deps.get(k, set()) | free

    def reads_of(body):
        free = set()
        for m in _CSS_READS.finditer(body):
            if m.group(1):
                free.add(m.group(1))
            elif m.group(2):
                free.add(m.group(2))
            elif m.group(3):
                free.add("@mixin " + m.group(3))
            elif m.group(4):
                free.add(m.group(4))
            elif m.group(5):
                for word in re.findall(r"(?<![\w.-])[A-Za-z_][\w-]*", m.group(5)):
                    free.add("@keyframes " + word)
        return free

    def walk(start, end, nested_in_rule):
        for s0, brace, e in _css_statements(clean, start, end):
            raw = text[s0:e].rstrip()
            if brace is None:
                m = _CSS_VAR_DECL.match(clean[s0:e])
                if m:
                    add(m.group(1), raw.rstrip(";"), reads_of(clean[s0:e]) - {m.group(1)})
                elif not nested_in_rule:
                    prelude = " ".join(clean[s0:e].rstrip(";").split())
                    if prelude.startswith("@") and not prelude.startswith(("@import", "@use", "@forward", "@charset")):
                        add(prelude, raw.rstrip(";"), reads_of(clean[s0:e]))
                continue
            prelude = " ".join(clean[s0:brace].split())
            if not prelude:
                continue
            body = clean[brace + 1:e - 1]
            if prelude.startswith(_CSS_GROUP_AT):
                add(prelude, raw, reads_of(body))
                walk(brace + 1, e - 1, False)   # the rules inside are anchors of their own too
            elif prelude.startswith(("@keyframes", "@font-face", "@mixin", "@function", "@page", "@property", "@counter-style", "@font-feature-values")):
                if not nested_in_rule:
                    add(re.sub(r"\(.*$", "", prelude).strip() if prelude.startswith(("@mixin", "@function")) else prelude, raw, reads_of(body) - {prelude})
                walk(brace + 1, e - 1, True)   # custom properties declared inside still count
            elif prelude.startswith("@"):
                if not nested_in_rule:
                    add(prelude, raw, reads_of(body))
            else:
                if not nested_in_rule:
                    for sel in _css_selectors(prelude):
                        add(sel, raw, reads_of(body))
                walk(brace + 1, e - 1, True)   # SCSS nesting and `:root { --x: … }`: nested rules belong to their holder; variables are anchors

    walk(0, len(clean), False)
    return Scan({"": text, **texts}, deps)


# ---------------------------------------------------------------- HTML and single-file components (Astro, Vue, Svelte)

_VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"}


def _merge(into, other, prefix=""):
    for k, v in other.texts.items():
        if k == "":
            continue
        into.texts[k] = (into.texts[k] + "\n" + v) if k in into.texts else v
        into.deps[k] = into.deps.get(k, set()) | other.deps.get(k, set())
    for k, v in other.hidden.items():
        into.hidden[k] = (into.hidden[k] + "\n" + v) if k in into.hidden else v


def scan_html(text, base=None):
    """Elements with an `id` (`index.html:#hero`, the element's whole text), `<title>`, and what the inline `<style>` and
    `<script>` blocks declare, by their own scanners — a component's scoped `.card` rule and its `const title` are anchors
    beside its `#hero` section. An element reads the classes and ids its style block declares (`class="card"` -> `.card`)."""
    from html.parser import HTMLParser
    out = base or Scan({"": text})
    line_starts = [0] + [m.end() for m in re.finditer("\n", text)]
    offset = lambda pos: line_starts[pos[0] - 1] + pos[1]
    stack, blocks = [], []   # (tag, start offset, id, classes) ; (kind, start, end) of style/script contents

    class P(HTMLParser):
        def handle_starttag(self, tag, attrs):
            at = dict(attrs)
            start = offset(self.getpos())
            if tag in _VOID:
                return
            stack.append((tag, start, at.get("id"), (at.get("class") or "").split(), at.get("type")))

        def handle_endtag(self, tag):
            if not any(t == tag for t, *_ in stack):
                return
            close = text.find(">", offset(self.getpos())) + 1
            while stack:
                t, start, id_, classes, type_ = stack.pop()
                if t == tag:
                    inner_start = text.find(">", start) + 1
                    inner_end = offset(self.getpos())
                    if t == "style":
                        blocks.append(("css", inner_start, inner_end))
                    elif t == "script" and (type_ or "module").split(";")[0].strip() in ("module", "text/javascript", "application/javascript", "text/typescript", "ts", "text/babel"):
                        blocks.append(("js", inner_start, inner_end))
                    elif t == "title":
                        k = ":title"
                        out.texts[k] = (out.texts[k] + "\n" + text[start:close]) if k in out.texts else text[start:close]
                    if id_:
                        k = ":#" + id_
                        span = text[start:close]
                        out.texts[k] = (out.texts[k] + "\n" + span) if k in out.texts else span
                        out.deps[k] = out.deps.get(k, set()) | {"." + c for c in classes}
                    break

    p = P(convert_charrefs=False)
    try:
        p.feed(text)
        p.close()
    except Exception:
        pass
    for kind, a, b in blocks:
        _merge(out, scan_css(text[a:b]) if kind == "css" else scan_js(text[a:b]))
    return out


def scan_component(text):
    """`.astro`: the frontmatter (between `---` fences) is TypeScript, the rest is HTML with `<style>`/`<script>` blocks.
    `.vue`/`.svelte`: `<script>` and `<style>` blocks and the template's ids — the same HTML scanner."""
    out = Scan({"": text})
    m = re.match(r"^---[ \t]*\n(.*?)\n---[ \t]*\n", text, re.S)
    rest_from = 0
    if m:
        _merge(out, scan_js(m.group(1)))
        rest_from = m.end()
    return scan_html(text[rest_from:], out) if rest_from else scan_html(text, out)


# ---------------------------------------------------------------- SQL, schema/IDL blocks (Prisma, GraphQL, protobuf), Dockerfile

_SQL_HEAD = re.compile(r"^\s*(?:CREATE|ALTER|DROP)\s+(?:OR\s+REPLACE\s+)?(?:UNIQUE\s+)?(?:TEMP(?:ORARY)?\s+)?(?:MATERIALIZED\s+)?"
                       r"(TABLE|INDEX|VIEW|FUNCTION|PROCEDURE|TYPE|TRIGGER|SEQUENCE|SCHEMA|EXTENSION|POLICY|DOMAIN|ROLE)\s+"
                       r"(?:IF\s+(?:NOT\s+)?EXISTS\s+)?(?:CONCURRENTLY\s+)?(?:ONLY\s+)?(\"[^\"]+\"|`[^`]+`|\[[^\]]+\]|[\w.]+)", re.I)
_SQL_READS = re.compile(r"\bREFERENCES\s+(\"[^\"]+\"|[\w.]+)|\bON\s+(?:ONLY\s+)?(\"[^\"]+\"|[\w.]+)\s*(?:\(|USING|$)", re.I | re.M)


def _sql_strip_comments(text):
    text = re.sub(r"/\*.*?\*/", lambda m: " " * len(m.group(0)), text, flags=re.S)
    return re.sub(r"(?m)--[^\n]*", lambda m: " " * len(m.group(0)), text)


def _sql_statements(text):
    """(start, end) of each `;`-terminated statement, quotes and `$$ … $$` bodies respected."""
    clean, i, n = _sql_strip_comments(text), 0, len(text)
    while i < n:
        while i < n and clean[i] in " \t\r\n;":
            i += 1
        if i >= n:
            return
        s0, j = i, i
        while j < n:
            c = clean[j]
            if c == "'":
                j = clean.find("'", j + 1)
                j = n if j < 0 else j + 1
                continue
            if clean.startswith("$$", j):
                j = clean.find("$$", j + 2)
                j = n if j < 0 else j + 2
                continue
            if c == ";":
                break
            j += 1
        yield s0, min(j + 1, n)
        i = j + 1


def scan_sql(text):
    """`CREATE TABLE users`, `ALTER TABLE users …`, `CREATE INDEX users_email_idx` — statements by the object they define,
    the same object's statements one anchor (`schema.sql:users` is the table and every ALTER on it). A table reads the tables
    it REFERENCES; an index reads the table it is ON."""
    texts, deps = {}, {}
    clean = _sql_strip_comments(text)
    for a, b in _sql_statements(text):
        m = _SQL_HEAD.match(clean[a:b])
        if not m:
            continue
        name = m.group(2).strip('"`[]')
        k = ":" + name
        span = text[a:b].rstrip()
        texts[k] = (texts[k] + "\n" + span) if k in texts else span
        free = {(r.group(1) or r.group(2)).strip('"') for r in _SQL_READS.finditer(clean[a:b])}
        deps[k] = deps.get(k, set()) | (free - {name})
    return Scan({"": text, **texts}, deps)


_BLOCK_HEAD = re.compile(r"^[ \t]*(?:extend\s+)?(model|type|enum|input|interface|union|scalar|directive|datasource|generator|message|service|schema|view)\b[ \t]*(@?[\w.]+)?", re.M)


def scan_block(text):
    """Prisma, GraphQL and protobuf: `model User { … }`, `type Query { … }`, `enum Role { … }`, `message Ping { … }` — one anchor
    per named block (`schema.prisma:User`, `schema.graphql:Query`), nameless blocks by keyword (`datasource`). A block reads
    the other blocks its fields name (`author User` -> `User`)."""
    texts, deps, names = {}, {}, []
    clean = re.sub(r"//[^\n]*|#[^\n]*", lambda m: " " * len(m.group(0)), text)
    clean = re.sub(r"/\*.*?\*/", lambda m: " " * len(m.group(0)), clean, flags=re.S)
    found = []
    for m in _BLOCK_HEAD.finditer(clean):
        s0 = m.start()
        while s0 > 0 and clean[s0 - 1] in " \t":
            s0 -= 1
        brace = clean.find("{", m.end())
        nl = clean.find("\n", m.end())
        if brace < 0 or (0 <= nl < brace):
            # `scalar DateTime`, `union U = A | B`: a line, not a block
            e = nl if nl >= 0 else len(clean)
        else:
            d, e = 0, brace
            while e < len(clean):
                d += (clean[e] == "{") - (clean[e] == "}")
                e += 1
                if d == 0:
                    break
        if found and s0 < found[-1][1]:
            continue   # nested (an rpc inside a service): part of its holder
        name = m.group(2) or m.group(1)
        found.append((s0, e, name))
    names = {n for _, _, n in found}
    for s0, e, name in found:
        k = ":" + name
        span = text[s0:e].rstrip()
        texts[k] = (texts[k] + "\n" + span) if k in texts else span
        words = set(re.findall(r"[A-Za-z_][\w.]*", clean[s0:e]))
        deps[k] = deps.get(k, set()) | ((words & names) - {name})
    return Scan({"": text, **texts}, deps)


_DOCKER_INSTR = re.compile(r"^\s*([A-Za-z]+)\b")


def scan_dockerfile(text):
    """Instructions by kind — `Dockerfile:FROM`, `Dockerfile:EXPOSE`, `Dockerfile:CMD`, `Dockerfile:ENV` — each anchor holding
    every line of that instruction (continuations joined); `ARG`/`ENV` names read by `$NAME` are the anchor's reads."""
    texts, deps = {}, {}
    lines, joined, cur = text.split("\n"), [], None
    for line in lines:
        if cur is not None:
            cur += "\n" + line
        elif not line.strip() or line.lstrip().startswith("#"):
            continue
        else:
            cur = line
        if not line.rstrip().endswith("\\"):
            joined.append(cur)
            cur = None
    if cur is not None:
        joined.append(cur)
    declared = {}   # variable name -> the instruction kind that declares it (ARG or ENV)
    for stmt in joined:
        m = _DOCKER_INSTR.match(stmt)
        if m and m.group(1).upper() in ("ARG", "ENV"):
            for v in re.findall(r"(?m)^\s*(?:ARG|ENV)\s+([A-Za-z_]\w*)|\s([A-Za-z_]\w*)=", stmt):
                declared[v[0] or v[1]] = m.group(1).upper()
    for stmt in joined:
        m = _DOCKER_INSTR.match(stmt)
        if not m:
            continue
        kind = m.group(1).upper()
        k = ":" + kind
        texts[k] = (texts[k] + "\n" + stmt) if k in texts else stmt
        deps[k] = deps.get(k, set()) | {declared[w] for w in re.findall(r"\$\{?([A-Za-z_]\w*)", stmt) if w in declared and declared[w] != kind}
    return Scan({"": text, **texts}, deps)
