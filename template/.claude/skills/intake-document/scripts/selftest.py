#!/usr/bin/env python3
"""Self-test for intake.py. Run: python3 -I -B skills/intake-document/scripts/selftest.py

Mechanics run against a fake `markitdown` package on PYTHONPATH, so no dependency is
needed. The real-conversion cases run only when `markitdown` is importable (use
`uv run --python 3.12 --with 'markitdown[docx,pptx,xlsx,xls,pdf,outlook]~=0.1.8' python -B <this file>`).
The script under test always runs as a subprocess with `-B`, so no bytecode is written.
"""
import ast
import importlib.util
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

sys.dont_write_bytecode = True  # nothing local is imported; the script under test runs with -B

SCRIPT = Path(__file__).resolve().parent / "intake.py"
STAMP_RE = r"\d{8}-\d{4}"

FAKE_MARKITDOWN = '''
class _Result:
    def __init__(self, text):
        self.text_content = text


class MarkItDown:
    def __init__(self, *args, **kwargs):
        pass

    def convert_local(self, path, **kwargs):
        with open(path, "rb") as handle:
            data = handle.read()
        if data.startswith(b"BOOM"):
            raise RuntimeError("boom")
        if data.startswith(b"EMPTY"):
            return _Result("")
        return _Result("# Fake conversion\\n\\n" + data.decode("utf-8", "replace"))

    def _forbidden(self, *args, **kwargs):
        raise AssertionError("only convert_local() may be used")

    convert = convert_uri = convert_url = convert_stream = convert_response = _forbidden
'''

FAKE_PYMUPDF = '''
def to_markdown(path):
    return "# pymupdf fake\\n\\nbody"
'''

BROKEN_IMPORT = 'raise ImportError("simulated missing package")\n'


def limit_file_size(nbytes):
    """preexec_fn: cap the size of any file the child writes (simulates a full disk)."""
    def apply():
        import resource
        import signal
        signal.signal(signal.SIGXFSZ, signal.SIG_IGN)
        resource.setrlimit(resource.RLIMIT_FSIZE, (nbytes, nbytes))
    return apply


def tree(root):
    """Everything under root (files and dirs) with file hashes, for before/after compares."""
    out = {}
    for path in sorted(Path(root).rglob("*")):
        rel = path.relative_to(root).as_posix()
        out[rel] = path.read_bytes() if path.is_file() else None
    return out


class IntakeBase(unittest.TestCase):
    def setUp(self):
        self.base = Path(tempfile.mkdtemp(prefix="intake-selftest-")).resolve()
        self.addCleanup(shutil.rmtree, str(self.base), True)
        self.proj = self.base / "proj"
        self.proj.mkdir()
        (self.proj / ".git").mkdir()  # intake only runs at a git top level
        self.fake = self._pkg("fake_md", "markitdown", FAKE_MARKITDOWN)
        self.nomd = self._pkg("no_md", "markitdown", BROKEN_IMPORT)
        self.src = self.base / "src"
        self.src.mkdir()

    def _pkg(self, folder, name, source):
        pkg = self.base / folder / name
        pkg.mkdir(parents=True)
        (pkg / "__init__.py").write_text(source, encoding="utf-8")
        return self.base / folder

    def make_src(self, name, content=b"hello world\n"):
        path = self.src / name
        path.write_bytes(content if isinstance(content, bytes) else content.encode("utf-8"))
        return path

    def run_intake(self, *args, path=None, cwd=None, env_extra=None, fsize=None):
        """Run intake.py with `-B`; `path` is a PYTHONPATH dir (default: the fake markitdown)."""
        env = dict(os.environ)
        env.pop("PYTHONPATH", None)
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        env.update(env_extra or {})
        pythonpath = self.fake if path is None else path
        if pythonpath is not False:
            env["PYTHONPATH"] = str(pythonpath)
        return subprocess.run([sys.executable, "-B", str(SCRIPT)] + [str(a) for a in args],
                              cwd=str(cwd or self.proj), env=env, capture_output=True, text=True, check=False,
                              preexec_fn=limit_file_size(fsize) if fsize else None)

    def ok(self, *args, **kw):
        res = self.run_intake(*args, **kw)
        self.assertEqual(res.returncode, 0, res.stdout + res.stderr)
        return res

    def fails(self, *args, **kw):
        before = tree(self.proj)
        res = self.run_intake(*args, **kw)
        self.assertEqual(res.returncode, 2, "expected exit 2\n" + res.stdout + res.stderr)
        self.assertEqual(tree(self.proj), before, "an error must leave nothing written")
        return res

    def only(self, directory, pattern):
        found = sorted(Path(directory).glob(pattern))
        self.assertEqual(len(found), 1, f"expected one {pattern} in {directory}, got {found}")
        return found[0]


class TestMechanics(IntakeBase):
    def test_naming_and_copy_not_move(self):
        src = self.make_src("Partner Contract (Final).txt", b"terms\n")
        self.ok(src, "--type", "contract")
        dest = self.proj / "docs/intake/contract"
        raw = self.only(dest, "partner_contract_final-*.txt")
        self.assertRegex(raw.name, rf"^partner_contract_final-{STAMP_RE}\.txt$")
        self.assertTrue(src.exists(), "original must stay in place")
        self.assertEqual(raw.read_bytes(), src.read_bytes())
        self.only(dest, "partner_contract_final-*.md")

    def test_vietnamese_title_and_override(self):
        src = self.make_src("Hợp \u0111ồng \u0110ối tác.txt")
        self.ok(src, "--type", "contract")
        self.only(self.proj / "docs/intake/contract", "hop_dong_doi_tac-*.txt")
        src2 = self.make_src("x.txt")
        self.ok(src2, "--type", "spec", "--title", "My  Spec!!")
        self.only(self.proj / "docs/intake/spec", "my_spec-*.txt")

    def test_frontmatter_sha256_and_verbatim_body(self):
        src = self.make_src("quote.txt", b"line one\nline two\n")
        self.ok(src, "--type", "finance", "--scope", "x", "--dest", "docs/{scope}/{type}")
        md = self.only(self.proj / "docs/x/finance", "quote-*.md").read_text(encoding="utf-8")
        head, _, body = md.partition("\n---\n\n")
        fields = dict(line.split(": ", 1) for line in head.splitlines()[1:])
        self.assertEqual(head.splitlines()[0], "---")
        self.assertEqual(fields["source_filename"], '"quote.txt"')
        self.assertEqual(fields["scope"], '"x"')
        self.assertEqual(fields["type"], '"finance"')
        import hashlib
        self.assertEqual(fields["sha256"], f'"{hashlib.sha256(src.read_bytes()).hexdigest()}"')
        self.assertRegex(fields["intake_timestamp"], r'^"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}[+-]\d{2}:\d{2}"$')
        self.assertRegex(fields["converter"], r'^"markitdown \S+"$')
        self.assertRegex(fields["intake_document"], rf'^"docs/x/finance/quote-{STAMP_RE}\.txt"$')
        self.assertEqual(body, "# Fake conversion\n\nline one\nline two\n")
        self.assertNotIn(str(self.src), md, "no absolute source path in the output")
        self.assertNotIn(str(self.base), md)

    def test_frontmatter_scope_null_without_scope(self):
        self.ok(self.make_src("a.txt"), "--type", "others")
        md = self.only(self.proj / "docs/intake/others", "a-*.md").read_text(encoding="utf-8")
        self.assertIn("\nscope: null\n", md)

    def test_default_ledger_created_appended_escaped(self):
        self.ok(self.make_src("one.txt"), "--type", "contract", "--sender", "Acme | Sales",
                "--reason", "renewal", "--notes", "line1\nline2 | tail")
        ledger = self.proj / "docs/intake/HISTORY.md"
        first = ledger.read_text(encoding="utf-8")
        self.assertTrue(first.startswith("# Intake History\n"))
        self.assertEqual(first.count("- **"), 2, "one row for the original, one for the .md")
        self.assertIn("Sender: Acme \\| Sales", first)
        self.assertIn("Notes: line1 line2 \\| tail", first)
        self.assertRegex(first, rf"\[one-{STAMP_RE}\.txt\]\(contract/one-{STAMP_RE}\.txt\) \(original\)")
        self.ok(self.make_src("two.txt"), "--type", "proposal")
        second = ledger.read_text(encoding="utf-8")
        self.assertTrue(second.startswith(first), "ledger is append only")
        self.assertEqual(second.count("# Intake History"), 1)
        self.assertEqual(second.count("- **"), 4)
        self.assertIn("Sender: —", second)

    def test_custom_ledger_row_matches_gohost_manifest_check(self):
        manifest = self.proj / "docs/features/booking/input/MANIFEST.md"
        manifest.parent.mkdir(parents=True)
        manifest.write_text("# Input\n\n| File | Version | Source | Date | sha256 |\n|---|---|---|---|---|\n",
                            encoding="utf-8")
        src = self.make_src("PRD Booking.pdf", b"%PDF-1.4 not really\n")
        self.ok(src, "--type", "spec", "--scope", "booking", "--version", "v2",
                "--dest", "docs/features/{scope}/input",
                "--ledger", "docs/features/{scope}/input/MANIFEST.md",
                "--ledger-row", "| `{file}` | {version} | {sender}, {source} | {date} | {sha256} |",
                "--sender", "PO | team")
        folder = manifest.parent
        files = sorted(p.name for p in folder.iterdir() if p.name != "MANIFEST.md")
        self.assertEqual(files, ["prd_booking-v2.md", "prd_booking-v2.pdf"])
        text = manifest.read_text(encoding="utf-8")
        self.assertTrue(text.startswith("# Input\n\n| File |"), "existing content untouched")
        # Same checks as go-helmmetry scripts/docs-check.sh (c).
        import hashlib
        row_re = re.compile(r"^\| `[^`]+` \|")
        rows = [line for line in text.splitlines() if row_re.match(line)]
        self.assertEqual(len(rows), 2)
        named = {re.match(r"^\| `([^`]+)`", line).group(1) for line in rows}
        self.assertEqual(named, set(files), "every MANIFEST row points at a real file and vice versa")
        for name in files:
            line = next(row for row in text.splitlines() if f"`{name}`" in row)
            want = re.search(r"[0-9a-f]{64}", line).group(0)
            self.assertEqual(hashlib.sha256((folder / name).read_bytes()).hexdigest(), want, name)
        self.assertIn("PO \\| team, PRD Booking.pdf", text)
        self.assertRegex(text, r"\| v2 \|")
        self.assertRegex(text, r"\| \d{4}-\d{2}-\d{2} \|")

    def test_custom_ledger_without_trailing_newline(self):
        ledger = self.proj / "m.md"
        ledger.write_text("| a |", encoding="utf-8")
        self.ok(self.make_src("a.txt"), "--type", "data", "--ledger", "m.md", "--ledger-row", "| `{file}` |")
        lines = ledger.read_text(encoding="utf-8").splitlines()
        self.assertEqual(lines[0], "| a |")
        self.assertEqual(len(lines), 3)

    def test_custom_ledger_must_exist(self):
        res = self.fails(self.make_src("a.txt"), "--type", "data", "--ledger", "docs/nope/MANIFEST.md")
        self.assertIn("custom ledger does not exist", res.stderr)

    def test_dest_without_type_placeholder(self):
        self.ok(self.make_src("a.txt"), "--type", "data", "--dest", "inbox")
        self.only(self.proj / "inbox", "a-*.txt")
        self.only(self.proj / "inbox", "a-*.md")

    def test_version_replaces_timestamp(self):
        self.ok(self.make_src("a.txt"), "--type", "data", "--version", "r2026-10-17")
        self.assertTrue((self.proj / "docs/intake/data/a-r2026-10-17.txt").is_file())
        self.ok(self.make_src("b.txt"), "--type", "data", "--version", "v1.3a")
        self.assertTrue((self.proj / "docs/intake/data/b-v1.3a.md").is_file())
        self.ok(self.make_src("c.txt"), "--type", "data", "--version", "v2026-09-30")
        self.assertTrue((self.proj / "docs/intake/data/c-v2026-09-30.md").is_file())

    def test_invalid_version_rejected(self):
        for bad in ("2", "v", "V2", "v2/../x", "r2026-1-1", "latest", "v1_2", "r\u0662\u0660\u0662\u0666-10-17"):
            res = self.fails(self.make_src("a.txt"), "--type", "data", "--version", bad)
            self.assertIn("--version", res.stderr)

    def test_image_copied_without_markdown_or_converter(self):
        png = self.make_src("Logo.PNG", b"\x89PNG\r\n\x1a\nfake")
        self.ok(png, "--type", "branding", path=self.nomd)  # would fail if conversion were attempted
        dest = self.proj / "docs/intake/branding"
        self.assertEqual([p.suffix for p in dest.iterdir()], [".png"])
        self.assertEqual((self.proj / "docs/intake/HISTORY.md").read_text(encoding="utf-8").count("- **"), 1)

    def test_markdown_source_is_copied_only(self):
        self.ok(self.make_src("notes.md", "# Mine\n"), "--type", "others", path=self.nomd)
        self.assertEqual([p.name[:6] for p in (self.proj / "docs/intake/others").iterdir()], ["notes-"])

    def test_overwrite_refused(self):
        src = self.make_src("a.txt", b"first")
        self.ok(src, "--type", "data", "--version", "v1")
        raw = self.proj / "docs/intake/data/a-v1.txt"
        ledger_before = (self.proj / "docs/intake/HISTORY.md").read_bytes()
        src.write_bytes(b"second")
        res = self.fails(src, "--type", "data", "--version", "v1")
        self.assertIn("already exists", res.stderr)
        self.assertEqual(raw.read_bytes(), b"first")
        self.assertEqual((self.proj / "docs/intake/HISTORY.md").read_bytes(), ledger_before)

    def test_existing_markdown_target_also_refused(self):
        dest = self.proj / "docs/intake/data"
        dest.mkdir(parents=True)
        (dest / "a-v1.md").write_text("mine", encoding="utf-8")
        self.fails(self.make_src("a.txt"), "--type", "data", "--version", "v1")
        self.assertEqual((dest / "a-v1.md").read_text(encoding="utf-8"), "mine")

    def test_missing_dependency_exit_2_with_uv_hint(self):
        res = self.fails(self.make_src("a.txt"), "--type", "data", path=self.nomd)
        self.assertIn("uv run --no-project --exclude-newer 2026-10-15T00:00:00Z --python 3.12 --with",
                      res.stderr)
        self.assertIn("markitdown[", res.stderr)
        self.assertEqual(res.stdout, "")

    def test_conversion_failure_writes_nothing(self):
        res = self.fails(self.make_src("a.txt", b"BOOM"), "--type", "data")
        self.assertIn("conversion of a.txt failed", res.stderr)

    def test_preview_writes_nothing_and_reports_plan(self):
        (self.proj / "docs/tenants/hpf").mkdir(parents=True)
        before = tree(self.proj)
        res = self.ok(self.make_src("Rules.txt", b"rule 1\n"), "--preview", "--type", "rules",
                      "--scope", "hpf", "--dest", "docs/tenants/{scope}/in/{type}")
        self.assertEqual(tree(self.proj), before)
        out = res.stdout
        self.assertIn("title     = rules", out)
        self.assertRegex(out, rf"base name = rules-{STAMP_RE}")
        self.assertRegex(out, rf"original  = docs/tenants/hpf/in/rules/rules-{STAMP_RE}\.txt")
        self.assertRegex(out, rf"markdown  = docs/tenants/hpf/in/rules/rules-{STAMP_RE}\.md")
        self.assertIn("ledger    = docs/intake/HISTORY.md (will be created)", out)
        self.assertIn("converter = markitdown", out)
        self.assertIn("rule 1", out)

    def test_preview_without_type_or_scope_is_lenient_and_lists_scopes(self):
        (self.proj / "docs/tenants/hpf").mkdir(parents=True)
        (self.proj / "docs/tenants/vpc").mkdir()
        res = self.ok(self.make_src("a.txt"), "--preview", "--dest", "docs/tenants/{scope}/in/{type}")
        self.assertIn("scopes    = hpf, vpc", res.stdout)
        self.assertIn("<type>", res.stdout)

    def test_preview_image_has_no_excerpt(self):
        res = self.ok(self.make_src("l.png", b"x"), "--preview", "--type", "branding", path=self.nomd)
        self.assertNotIn("excerpt", res.stdout)
        self.assertIn("markdown  = (none)", res.stdout)


class TestSafety(IntakeBase):
    def test_type_validation(self):
        src = self.make_src("a.txt")
        self.assertIn("--type is required", self.fails(src).stderr)
        self.assertIn("unknown --type", self.fails(src, "--type", "roster").stderr)
        self.ok(src, "--type", "roster", "--types", "roster,other")
        self.assertIn("--types entry", self.fails(src, "--type", "x", "--types", "x,../y").stderr)

    def test_scope_validation(self):
        src = self.make_src("a.txt")
        for bad in ("../evil", "UPPER", "a/b", "-x", ""):
            res = self.fails(src, "--type", "data", "--scope", bad, "--dest", "docs/{scope}")
            self.assertIn("--scope", res.stderr)

    def test_unknown_scope_lists_known_ones(self):
        (self.proj / "docs/tenants/hpf").mkdir(parents=True)
        (self.proj / "docs/tenants/vpc").mkdir()
        (self.proj / "docs/tenants/_template").mkdir()
        res = self.fails(self.make_src("a.txt"), "--type", "data", "--scope", "nope",
                         "--dest", "docs/tenants/{scope}/in/{type}")
        self.assertIn("unknown scope 'nope'", res.stderr)
        self.assertIn("known: hpf, vpc", res.stderr)
        self.ok(self.make_src("b.txt"), "--type", "data", "--scope", "hpf",
                "--dest", "docs/tenants/{scope}/in/{type}")
        self.only(self.proj / "docs/tenants/hpf/in/data", "b-*.txt")

    def test_scope_accepted_when_scope_parent_does_not_exist(self):
        self.ok(self.make_src("a.txt"), "--type", "data", "--scope", "fresh", "--dest", "newroot/{scope}/in")
        self.only(self.proj / "newroot/fresh/in", "a-*.txt")

    def test_scope_placeholder_without_scope_is_usage_error(self):
        res = self.fails(self.make_src("a.txt"), "--type", "data", "--dest", "docs/{scope}/in")
        self.assertIn("{scope}", res.stderr)

    def test_scope_without_placeholder_is_usage_error(self):
        res = self.fails(self.make_src("a.txt"), "--type", "data", "--scope", "hpf")
        self.assertIn("--scope given", res.stderr)

    def test_unknown_placeholder_and_bad_row_template(self):
        src = self.make_src("a.txt")
        self.assertIn("unknown placeholder", self.fails(src, "--type", "data", "--dest", "docs/{tenant}").stderr)
        ledger = self.proj / "l.md"
        ledger.write_text("x\n", encoding="utf-8")
        res = self.fails(src, "--type", "data", "--ledger", "l.md", "--ledger-row", "| {nope} |")
        self.assertIn("--ledger-row", res.stderr)

    def test_path_traversal_rejected(self):
        src = self.make_src("a.txt")
        outside = self.base / "outside"
        outside.mkdir()
        for dest in ("../outside", "docs/../../outside", str(outside), "docs/{type}/../../../outside"):
            res = self.fails(src, "--type", "data", "--dest", dest)
            self.assertIn("outside --root", res.stderr, dest)
        self.assertEqual(list(outside.iterdir()), [])

    def test_symlink_escape_rejected(self):
        outside = self.base / "outside"
        outside.mkdir()
        (self.proj / "docs").mkdir()
        os.symlink(str(outside), str(self.proj / "docs/link"))
        res = self.fails(self.make_src("a.txt"), "--type", "data", "--dest", "docs/link/{type}")
        self.assertIn("outside --root", res.stderr)
        self.assertEqual(list(outside.iterdir()), [])

    def test_ledger_outside_root_or_into_git_rejected(self):
        src = self.make_src("a.txt")
        other = self.base / "other.md"
        other.write_text("keep\n", encoding="utf-8")
        res = self.fails(src, "--type", "data", "--ledger", "../other.md", "--ledger-row", "| x |")
        self.assertIn("outside --root", res.stderr)
        self.assertEqual(other.read_text(encoding="utf-8"), "keep\n")
        res = self.fails(src, "--type", "data", "--dest", ".git/hooks")
        self.assertIn(".git", res.stderr)

    def test_root_flag_confines_writes(self):
        elsewhere = self.base / "elsewhere"
        elsewhere.mkdir()
        self.ok(self.make_src("a.txt"), "--type", "data", "--root", self.proj, cwd=elsewhere)
        self.assertEqual(list(elsewhere.iterdir()), [])
        self.only(self.proj / "docs/intake/data", "a-*.txt")

    def test_bad_inputs(self):
        self.assertIn("input not found", self.fails(self.src / "missing.txt", "--type", "data").stderr)
        self.assertIn("input not found", self.fails(self.src, "--type", "data").stderr)
        res = self.fails("https://example.com/x.pdf", "--type", "data")
        self.assertIn("URLs are not supported", res.stderr)
        res = self.fails(self.make_src("日本語.txt"), "--type", "data")
        self.assertIn("--title", res.stderr)

    def test_pdf_engine(self):
        pdf = self.make_src("Doc.pdf", b"%PDF-1.4\n")
        missing = self._pkg("no_pymupdf", "pymupdf4llm", BROKEN_IMPORT)
        res = self.fails(pdf, "--type", "data", "--pdf-engine", "pymupdf4llm",
                         path=os.pathsep.join([str(missing), str(self.fake)]))
        self.assertIn("AGPL-3.0", res.stderr)
        stub = self._pkg("fake_pymupdf", "pymupdf4llm", FAKE_PYMUPDF)
        env_path = os.pathsep.join([str(stub), str(self.fake)])
        self.ok(pdf, "--type", "data", "--pdf-engine", "pymupdf4llm", path=env_path)
        md = self.only(self.proj / "docs/intake/data", "doc-*.md").read_text(encoding="utf-8")
        self.assertIn('converter: "pymupdf4llm ', md)
        self.assertIn("# pymupdf fake", md)
        # default engine and non-PDF files ignore the pymupdf4llm package entirely
        self.ok(self.make_src("t.txt"), "--type", "data", "--pdf-engine", "pymupdf4llm", path=self.fake)

    def test_source_stays_python_39_compatible_and_local_only(self):
        source = SCRIPT.read_text(encoding="utf-8")
        ast.parse(source, feature_version=(3, 9))
        self.assertNotRegex(source, r"\bmatch\s+\w+\s*:")
        self.assertRegex(source, r"\.convert_local\(")
        for forbidden in (".convert(", ".convert_uri(", ".convert_url(", ".convert_stream("):
            self.assertNotIn(forbidden, source)
        head = source.split("def convert(", 1)[0]
        self.assertNotRegex(head, r"(?m)^(import|from)\s+(markitdown|pymupdf4llm)")


class TestRollback(IntakeBase):
    """Review fixes 1, 2, 5: nothing partial survives, copies are plain 0644 files."""

    def setUp(self):
        super().setUp()
        if not importlib.util.find_spec("resource"):
            self.skipTest("resource module (RLIMIT_FSIZE) not available")

    def assert_rolled_back(self, res):
        self.assertEqual(res.returncode, 2, res.stdout + res.stderr)
        self.assertIn("rolled back", res.stderr)
        self.assertNotIn("Traceback", res.stderr)
        self.assertNotIn("COULD NOT UNDO", res.stderr)

    def test_original_copy_fails_midway(self):
        before = tree(self.proj)
        res = self.run_intake(self.make_src("big.txt", b"x" * 3000), "--type", "data", fsize=1000)
        self.assert_rolled_back(res)
        self.assertEqual(tree(self.proj), before)

    def test_markdown_write_fails_after_original_copied(self):
        before = tree(self.proj)
        res = self.run_intake(self.make_src("a.txt", b"y" * 500), "--type", "data", fsize=700)
        self.assert_rolled_back(res)
        self.assertEqual(tree(self.proj), before, "the already written original must be removed")

    def test_ledger_append_fails_and_is_truncated_back(self):
        ledger = self.proj / "docs/intake/HISTORY.md"
        ledger.parent.mkdir(parents=True)
        ledger.write_bytes(b"# Intake History\n\nold row\n")
        before = tree(self.proj)
        res = self.run_intake(self.make_src("a.txt", b"z" * 100), "--type", "data",
                              "--notes", "n" * 3000, fsize=1500)
        self.assert_rolled_back(res)
        self.assertEqual(tree(self.proj), before)

    def test_ledger_insert_fails_and_leaves_no_temp_file(self):
        ledger = self.proj / "m.md"
        ledger.write_bytes(b"| a |\n")
        before = tree(self.proj)
        res = self.run_intake(self.make_src("a.txt", b"z" * 100), "--type", "data", "--ledger", "m.md",
                              "--ledger-row", "| `{file}` | {notes} |", "--notes", "n" * 3000, fsize=1500)
        self.assert_rolled_back(res)
        self.assertEqual(tree(self.proj), before)

    def test_copies_are_plain_644_and_not_executable(self):
        src = self.make_src("script.txt", b"echo\n")
        os.chmod(str(src), 0o755)
        self.ok(src, "--type", "data")
        for path in (self.proj / "docs/intake/data").iterdir():
            self.assertEqual(path.stat().st_mode & 0o777, 0o644, path.name)

    def test_dangling_symlink_at_target_is_refused(self):
        dest = self.proj / "docs/intake/data"
        dest.mkdir(parents=True)
        os.symlink(str(self.base / "nowhere"), str(dest / "a-v1.txt"))
        self.fails(self.make_src("a.txt"), "--type", "data", "--version", "v1")
        self.assertFalse((self.base / "nowhere").exists())

    def test_read_only_ledger_append_fails_cleanly(self):
        if os.geteuid() == 0:
            self.skipTest("root ignores read-only modes")
        ledger = self.proj / "docs" / "LOG.md"
        ledger.parent.mkdir()
        ledger.write_text("# log\n", encoding="utf-8")
        os.chmod(str(ledger), 0o444)
        self.addCleanup(os.chmod, str(ledger), 0o644)
        res = self.fails(self.make_src("a.txt"), "--type", "data", "--ledger", "docs/LOG.md")
        self.assertIn("rolled back", res.stderr)
        self.assertNotIn("COULD NOT UNDO", res.stderr)
        self.assertEqual(ledger.read_text(encoding="utf-8"), "# log\n")

    def test_read_only_ledger_with_row_template_is_refused_up_front(self):
        if os.geteuid() == 0:
            self.skipTest("root ignores read-only modes")
        ledger = self.proj / "docs" / "LOG.md"
        ledger.parent.mkdir()
        ledger.write_text("| a |\n", encoding="utf-8")
        os.chmod(str(ledger), 0o444)
        self.addCleanup(os.chmod, str(ledger), 0o644)
        res = self.fails(self.make_src("a.txt"), "--type", "data", "--ledger", "docs/LOG.md",
                         "--ledger-row", "| `{file}` |")
        self.assertIn("not writable", res.stderr)
        self.assertNotIn("COULD NOT UNDO", res.stderr)

    def test_os_error_is_exit_2_not_a_traceback(self):
        if os.geteuid() == 0:
            self.skipTest("root can read mode 000 files")
        src = self.make_src("locked.txt")
        os.chmod(str(src), 0)
        self.addCleanup(os.chmod, str(src), 0o600)
        res = self.fails(src, "--type", "data", "--no-convert")
        self.assertIn("intake.py: error:", res.stderr)
        self.assertNotIn("Traceback", res.stderr)

    def test_blocked_destination_directory_is_rolled_back(self):
        (self.proj / "docs").write_text("a file, not a directory", encoding="utf-8")
        res = self.fails(self.make_src("a.txt"), "--type", "data")
        self.assertNotIn("Traceback", res.stderr)


class TestBinariesAndText(IntakeBase):
    """Review fixes 4, 6, 7."""

    def test_copy_only_binaries_never_reach_the_converter(self):
        for name in ("song.MP3", "clip.wav", "talk.m4a", "movie.mp4", "design.psd", "bundle.zip",
                     "font.woff2", "photo.heic", "setup.exe"):
            self.ok(self.make_src(name, b"\x00\x01binary"), "--type", "data", path=self.nomd)
        files = sorted(p.suffix for p in (self.proj / "docs/intake/data").iterdir())
        self.assertNotIn(".md", files)
        self.assertEqual(len(files), 9)

    def test_no_convert_flag_copies_only(self):
        self.ok(self.make_src("a.txt"), "--type", "data", "--no-convert", path=self.nomd)
        self.assertEqual([p.suffix for p in (self.proj / "docs/intake/data").iterdir()], [".txt"])
        res = self.ok(self.make_src("b.txt"), "--preview", "--type", "data", "--no-convert", path=self.nomd)
        self.assertIn("converter = none (--no-convert)", res.stdout)

    def test_nul_bytes_in_converted_text_refused(self):
        res = self.fails(self.make_src("a.txt", b"left\x00right"), "--type", "data")
        self.assertIn("NUL", res.stderr)
        self.assertIn("--no-convert", res.stderr)

    def test_preview_with_missing_custom_ledger_shows_missing(self):
        res = self.ok(self.make_src("a.txt"), "--preview", "--type", "data", "--ledger", "docs/M.md")
        self.assertIn("docs/M.md (MISSING)", res.stdout)

    def test_empty_conversion_warns_in_run_and_preview(self):
        src = self.make_src("scan.txt", b"EMPTY")
        res = self.run_intake(src, "--preview", "--type", "data")
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertIn("no text", res.stderr)
        self.assertIn("pymupdf4llm", res.stderr)
        res = self.ok(src, "--type", "data")
        self.assertIn("no text", res.stderr)

    def test_control_characters_are_escaped_in_frontmatter(self):
        name = "a\x7fb\u0085c\ufeffd.txt"
        self.ok(self.make_src(name), "--type", "data", "--title", "ctl")
        raw = self.only(self.proj / "docs/intake/data", "ctl-*.md").read_bytes().decode("utf-8")
        head = raw.split("\n---\n", 1)[0]
        for char in ("\x7f", "\u0085", "\ufeff"):
            self.assertNotIn(char, head)
        self.assertIn('source_filename: "a\\u007fb\\u0085c\\ufeffd.txt"', head)

    def test_non_utf8_names_and_text_give_a_clear_error(self):
        res = self.fails("bad\udcff.txt", "--type", "data")
        self.assertIn("rename the file", res.stderr)
        self.assertNotIn("Traceback", res.stderr)
        res = self.fails(self.make_src("a.txt"), "--type", "data", "--notes", "oops\udcff")
        self.assertIn("--notes", res.stderr)
        self.assertNotIn("Traceback", res.stderr)


class TestGuards(IntakeBase):
    """Review fixes 8, 9, 10, 11."""

    def test_hidden_and_tooling_directories_rejected(self):
        src = self.make_src("a.txt")
        for dest in (".github/workflows", "docs/.GIT/x", ".claude/skills", ".husky", ".vscode/x",
                     "node_modules/pkg", "docs/Node_Modules"):
            res = self.fails(src, "--type", "data", "--dest", dest)
            self.assertRegex(res.stderr, r"hidden path component|node_modules", dest)

    def test_hidden_directory_reached_through_a_symlink_rejected(self):
        (self.proj / ".github").mkdir()
        os.symlink(str(self.proj / ".github"), str(self.proj / "innocent"))
        self.fails(self.make_src("a.txt"), "--type", "data", "--dest", "innocent")
        self.assertEqual(list((self.proj / ".github").iterdir()), [])

    def test_instruction_and_memory_files_cannot_be_ledgers(self):
        src = self.make_src("a.txt")
        for name in ("CLAUDE.md", "docs/agents.md", "AGENTS.MD", "CLAUDE.local.md", "GEMINI.md",
                     "agent.md", "docs/copilot-instructions.md"):
            res = self.fails(src, "--type", "data", "--ledger", name)
            self.assertIn("--ledger must not be", res.stderr, name)

    def test_custom_ledger_must_be_markdown(self):
        src = self.make_src("a.txt")
        for name in ("notes.txt", "authorized_keys", "ledger"):
            (self.proj / name).write_text("x\n", encoding="utf-8")
            res = self.fails(src, "--type", "data", "--ledger", name)
            self.assertIn("Markdown file", res.stderr, name)
        (self.proj / "MANIFEST.MD").write_text("x\n", encoding="utf-8")
        self.ok(src, "--type", "data", "--ledger", "MANIFEST.MD")

    def test_root_must_be_the_git_top_level(self):
        sub = self.proj / "sub"
        sub.mkdir()
        res = self.fails(self.make_src("a.txt"), "--type", "data", "--root", sub)
        self.assertIn("repository top level", res.stderr)
        self.ok(self.make_src("b.txt"), "--type", "data", "--root", self.proj)
        self.ok(self.make_src("c.txt"), "--type", "data", "--root", ".")

    def test_root_outside_git_is_refused(self):
        plain = self.base / "plain"
        plain.mkdir()
        res = self.run_intake(self.make_src("a.txt"), "--type", "data", "--root", plain, cwd=plain)
        self.assertEqual(res.returncode, 2, res.stdout + res.stderr)
        self.assertIn("top level of a git repository", res.stderr)
        self.assertEqual(list(plain.iterdir()), [])

    def test_hidden_folders_under_home_are_refused_as_root_even_in_git(self):
        home = self.base / "home"
        env = {"HOME": str(home)}
        for parts in ((".ssh",), (".oh-my-zsh",), (".Config", "nvim"), (".LaunchAgents",)):
            root = home.joinpath(*parts)
            (root / ".git").mkdir(parents=True)
            res = self.run_intake(self.make_src("a.txt"), "--type", "data", "--root", root,
                                  "--dest", ".", "--ledger", "authorized_keys", cwd=root, env_extra=env)
            self.assertEqual(res.returncode, 2, parts)
            self.assertIn("hidden folder under your home", res.stderr, parts)
            self.assertEqual(sorted(p.name for p in root.iterdir()), [".git"], parts)

    def test_hidden_folders_deeper_in_a_normal_repo_are_fine_as_root(self):
        home = self.base / "home"
        env = {"HOME": str(home)}
        worktree = home / "Work" / "repo" / ".claude" / "worktrees" / "x"
        worktree.mkdir(parents=True)
        (worktree / ".git").write_text("gitdir: ../../../.git/worktrees/x\n", encoding="utf-8")
        self.ok(self.make_src("a.txt"), "--type", "data", "--root", worktree, cwd=worktree, env_extra=env)
        self.only(worktree / "docs/intake/data", "a-*.txt")
        absolute = str(worktree / "docs" / "abs")
        self.ok(self.make_src("b.txt"), "--type", "data", "--root", worktree, "--dest", absolute,
                cwd=worktree, env_extra=env)
        self.only(worktree / "docs/abs", "b-*.txt")

    def test_absolute_hidden_dest_error_suggests_a_relative_path(self):
        res = self.fails(self.make_src("a.txt"), "--type", "data", "--dest", str(self.proj / ".github"))
        self.assertIn("relative to --root", res.stderr)

    def test_secret_like_inputs_refused(self):
        for name in (".env", ".env.production", "server.pem", "tls.KEY", "id_rsa", "id_ed25519.pub",
                     "cert.p12", "cert.pfx", ".netrc", ".git-credentials", ".npmrc"):
            res = self.fails(self.make_src(name), "--type", "data")
            self.assertIn("secret or key", res.stderr, name)

    def test_inputs_inside_git_dirs_and_secret_homes_refused(self):
        git_file = self.src / "repo" / ".git" / "config"
        git_file.parent.mkdir(parents=True)
        git_file.write_text("[core]\n", encoding="utf-8")
        self.assertIn(".git", self.fails(git_file, "--type", "data").stderr)
        home = self.base / "home"
        for parts in ((".ssh",), (".aws",), (".gnupg",), (".config", "gh")):
            target = home.joinpath(*parts) / "notes.txt"
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text("x", encoding="utf-8")
            res = self.fails(target, "--type", "data", env_extra={"HOME": str(home)})
            self.assertIn("refusing to ingest from", res.stderr, parts)
        for parts in ((".AWS",), (".Config", "GH"), (".config", "gcloud"), (".docker",), (".kube",)):
            target = home.joinpath(*parts) / "credentials.txt"
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text("x", encoding="utf-8")
            res = self.fails(target, "--type", "data", env_extra={"HOME": str(home)})
            self.assertIn("refusing to ingest from", res.stderr, parts)
        other = home / ".config" / "other.txt"
        other.write_text("fine", encoding="utf-8")
        self.ok(other, "--type", "data", env_extra={"HOME": str(home)})


    def test_devices_and_pipes_are_refused_without_blocking(self):
        res = self.fails("/dev/null", "--type", "data")
        self.assertRegex(res.stderr, r"/dev|not a regular file")
        fifo = self.src / "pipe.txt"
        os.mkfifo(str(fifo))
        res = self.run_intake(fifo, "--type", "data")  # would hang if it were opened
        self.assertEqual(res.returncode, 2, res.stdout + res.stderr)
        self.assertIn("not a regular file", res.stderr)

    def test_code_files_are_stored_with_a_txt_suffix(self):
        for name, stored in (("test_x.py", "test_x-{}.py.txt"), ("Deploy.SH", "deploy-{}.sh.txt"),
                             ("main.go", "main-{}.go.txt"), ("a.cpp", "a-{}.cpp.txt")):
            self.ok(self.make_src(name, b"print(1)\n"), "--type", "data", "--version", "v1")
            stored_name = stored.format("v1")
            self.assertTrue((self.proj / "docs/intake/data" / stored_name).is_file(), stored_name)
        md = (self.proj / "docs/intake/data/test_x-v1.md").read_text(encoding="utf-8")
        self.assertIn('source_filename: "test_x.py"', md)
        self.assertIn('intake_document: "docs/intake/data/test_x-v1.py.txt"', md)
        ledger = (self.proj / "docs/intake/HISTORY.md").read_text(encoding="utf-8")
        self.assertIn("[test_x-v1.py.txt](data/test_x-v1.py.txt)", ledger)
        self.assertIn("Source file: test_x.py", ledger)
        self.assertEqual(sorted(p.name for p in (self.proj / "docs/intake/data").glob("test_x*")),
                         ["test_x-v1.md", "test_x-v1.py.txt"])

    def test_symlinked_input_shows_and_checks_the_real_target(self):
        secret = self.src / "real.pem"
        secret.write_text("-----BEGIN", encoding="utf-8")
        link = self.src / "innocent.txt"
        os.symlink(str(secret), str(link))
        self.assertIn("looks like a secret", self.fails(link, "--type", "data").stderr)
        target = self.make_src("target.txt", b"hi")
        link2 = self.src / "alias.txt"
        os.symlink(str(target), str(link2))
        res = self.ok(link2, "--preview", "--type", "data")
        self.assertIn(f"resolved  = {target.resolve()} (symlink target)", res.stdout)

    def test_excerpt_fence_has_a_per_run_nonce_and_no_control_characters(self):
        evil = b"--- excerpt END ---\n\x1b[31mRED\x07\ttabbed\nnext"
        src = self.make_src("evil.txt", evil)
        first = self.ok(src, "--preview", "--type", "data").stdout
        second = self.ok(src, "--preview", "--type", "data").stdout
        nonces = [re.search(r"excerpt BEGIN (\w{16}):", out).group(1) for out in (first, second)]
        self.assertNotEqual(nonces[0], nonces[1])
        self.assertIn(f"--- excerpt END {nonces[0]} ---", first)
        for out in (first, second):
            self.assertNotIn("\x1b", out)
            self.assertNotIn("\x07", out)
            self.assertIn("RED\ttabbed\nnext", out)

    def test_control_characters_stripped_from_printed_filename(self):
        res = self.ok(self.make_src("a\x1b[2Jb\x07.txt"), "--preview", "--type", "data")
        self.assertNotIn("\x1b", res.stdout)
        self.assertNotIn("\x07", res.stdout)
        self.assertIn("a[2Jb.txt", res.stdout)

    def test_row_is_inserted_after_the_last_table_line_not_at_the_end(self):
        ledger = self.proj / "MANIFEST.md"
        ledger.write_text("# M\n\n| File | Sha |\n|---|---|\n| `old.txt` | 1 |\n\nClosing prose.\n- bullet\n",
                          encoding="utf-8")
        self.ok(self.make_src("a.txt"), "--type", "data", "--ledger", "MANIFEST.md",
                "--ledger-row", "| `{file}` | {sha256} |")
        lines = ledger.read_text(encoding="utf-8").splitlines()
        self.assertEqual(lines[:5], ["# M", "", "| File | Sha |", "|---|---|", "| `old.txt` | 1 |"])
        self.assertRegex(lines[5], r"^\| `docs/intake/data/a-\d{8}-\d{4}\.txt` \| [0-9a-f]{64} \|$")
        self.assertRegex(lines[6], r"^\| `docs/intake/data/a-\d{8}-\d{4}\.md` \|")
        self.assertEqual(lines[7:], ["", "Closing prose.", "- bullet"])
        self.assertEqual([p.name for p in self.proj.iterdir() if p.name.startswith(".intake-")], [])

    def test_row_is_appended_when_the_ledger_has_no_table(self):
        ledger = self.proj / "log.md"
        ledger.write_text("just prose", encoding="utf-8")
        self.ok(self.make_src("a.txt"), "--type", "data", "--ledger", "log.md", "--ledger-row", "- {file}")
        lines = ledger.read_text(encoding="utf-8").splitlines()
        self.assertEqual(lines[0], "just prose")
        self.assertEqual(len(lines), 3)


@unittest.skipUnless(importlib.util.find_spec("markitdown"), "markitdown not importable; "
                     "run via: uv run --python 3.12 --with 'markitdown[docx,pptx,xlsx,xls,pdf,outlook]~=0.1.8' ...")
class TestRealConversion(IntakeBase):
    def real(self, src, *extra):
        return self.ok(src, "--type", "data", *extra, path=False)

    def read_md(self, pattern):
        return self.only(self.proj / "docs/intake/data", pattern).read_text(encoding="utf-8")

    def test_html(self):
        src = self.make_src("page.html", "<html><body><h1>Intake Title</h1><p>Hello <b>world</b></p>"
                            "<ul><li>alpha</li><li>beta</li></ul></body></html>")
        self.real(src)
        md = self.read_md("page-*.md")
        self.assertRegex(md, r'converter: "markitdown 0\.\d+\.\d+')
        self.assertIn("# Intake Title", md)
        self.assertIn("Hello **world**", md)
        self.assertRegex(md, r"[*-] alpha")

    def test_csv(self):
        src = self.make_src("table.csv", "name,qty\nwidget,3\ngadget,5\n")
        self.real(src)
        md = self.read_md("table-*.md")
        self.assertIn("| name | qty |", md)
        self.assertIn("| widget | 3 |", md)

    def test_docx(self):
        if not importlib.util.find_spec("mammoth"):
            self.skipTest("mammoth (docx extra) not importable")
        docx = self.src / "memo.docx"
        w = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
        with zipfile.ZipFile(str(docx), "w") as z:
            z.writestr("[Content_Types].xml",
                       '<?xml version="1.0"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
                       '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
                       '<Default Extension="xml" ContentType="application/xml"/>'
                       '<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument'
                       '.wordprocessingml.document.main+xml"/></Types>')
            z.writestr("_rels/.rels",
                       '<?xml version="1.0"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                       '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/'
                       'officeDocument" Target="word/document.xml"/></Relationships>')
            z.writestr("word/document.xml",
                       f'<?xml version="1.0"?><w:document xmlns:w="{w}"><w:body><w:p><w:r><w:t>Memo body text</w:t></w:r>'
                       '</w:p></w:body></w:document>')
        self.real(docx)
        self.assertIn("Memo body text", self.read_md("memo-*.md"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
