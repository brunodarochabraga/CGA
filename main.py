"""
main.py
=======
Unified command-line entry point AND home of the driver-shared
display helpers.

CLI
---
    python main.py parser     <grammar_file.py>
    python main.py inferencer <grammar_file.py>

Sub-command aliases:  parser | parse | p   |   inferencer | infer | i

Examples:
    python main.py parser     GrammarTemplate.py
    python main.py parser     GrammarIndexed.py
    python main.py inferencer GrammarExtendedMissingIp.py

The two underlying drivers (`main_parser.py`, `main_inferencer.py`)
remain runnable standalone:
    python main_parser.py     GrammarIndexed.py
    python main_inferencer.py GrammarExtendedMissingIp.py

Shared driver helpers
---------------------
`derivation_score`, `print_step`, `print_banner`, and `load_or_exit`
are defined here and imported by both drivers, so the display
configuration and the grammar-loading error path live in exactly one
place.  `_RULE_SYMBOLS` is private; callers go through `print_step`.

Architectural note: keeping shared driver helpers in `main.py` means
that when the CLI dispatcher runs (`python main.py ...`), the file is
loaded twice --- once as `__main__`, once as `main` --- once Python
imports the chosen driver, which `from main import ...`s back here.
The double load is harmless (only module-level definitions; the
`__main__` guard prevents re-dispatch) but it is a known Python
idiom-mismatch.  The standard alternative is a third module
`driver_common.py`; this codebase consolidates into `main.py` by
deliberate user choice (see the project README / commit history).
"""

import sys


# ============================================================
# Shared display configuration
# ============================================================

# Private: the public surface is `print_step`.
_RULE_SYMBOLS = {
    "(  )": "(  )",
    "FA":   "(> )",
    "BA":   "(< )",
    "FC":   "(B>)",
    "BC":   "(<B)",
    "FS":   "(S>)",
    "BS":   "(<S)",
    "FXS":  "(X>)",
    "BXS":  "(<X)",
    "COORD": "(& )",
    "FTR":  "(T>)",
    "BTR":  "(<T)",
}


def derivation_score(steps, rule_priorities):
    """Lexicographic key (length, sum-of-priorities) used to order
    derivations for display.  Lower is preferred."""
    return (
        len(steps),
        sum(rule_priorities.get(step.rule, 1000) for step in steps),
    )


def print_step(idx, step):
    """Print one derivation step with its rule glyph prefix.

    The glyph table is private to this module so that adding a new
    combinator only requires a one-line edit here, with no driver
    needing to be touched.
    """
    key = str(step).split(":")[0].strip()
    print(f"   {idx:>3}. {_RULE_SYMBOLS.get(key, '(  )')} {step}")


# ============================================================
# Shared banner and grammar-loading helpers
# ============================================================

_PROJECT_LINE_DEFAULT = "Categorical-Generative Analysis 1.0 - by Bruno da Rocha Braga"


def print_banner(grammar_file, mode=None, subtitle=None):
    """Print the standard top-of-run banner.

    `mode` (e.g. "INFERENTIAL") replaces the author tagline with a
    bracketed mode label, matching the convention used by the
    inferencer driver.  `subtitle` adds a second descriptive line.
    """
    print("=" * 80)
    if mode is None:
        print(_PROJECT_LINE_DEFAULT)
    else:
        print(f"Categorical-Generative Analysis 1.0  [{mode}]")
    if subtitle:
        print(subtitle)
    print(f"Grammar file: {grammar_file}")
    print("=" * 80)


def load_or_exit(grammar_file):
    """Load a GrammarConfig from a file, or exit(2) with a clean error
    message on failure.  Centralises the try/except both drivers
    previously inlined."""
    # Imported lazily so the parser driver does not pay the cost of
    # loading grammar_loader's dependencies if it never reaches this
    # path (defence in depth: a stubbed driver could short-circuit).
    from grammar_loader import load_grammar_from_file
    try:
        return load_grammar_from_file(grammar_file)
    except (FileNotFoundError, ImportError, ValueError) as e:
        print(f"Error loading grammar: {e}", file=sys.stderr)
        sys.exit(2)


# ============================================================
# CLI dispatcher
# ============================================================

USAGE = (
    "Usage: python main.py <command> <grammar_file.py>\n"
    "  <command> = parser | inferencer\n"
    "  Examples:\n"
    "    python main.py parser     GrammarTemplate.py\n"
    "    python main.py inferencer GrammarExtendedMissingIp.py"
)

# Maps a CLI alias to (module_name, canonical_label).
_COMMANDS = {
    "parser":     ("main_parser",     "parser"),
    "parse":      ("main_parser",     "parser"),
    "p":          ("main_parser",     "parser"),
    "inferencer": ("main_inferencer", "inferencer"),
    "infer":      ("main_inferencer", "inferencer"),
    "i":          ("main_inferencer", "inferencer"),
}


def main():
    if len(sys.argv) != 3:
        print(USAGE, file=sys.stderr)
        sys.exit(1)

    raw_cmd = sys.argv[1]
    grammar_file = sys.argv[2]

    try:
        module_name, label = _COMMANDS[raw_cmd.lower()]
    except KeyError:
        print(f"Unknown command: {raw_cmd!r}", file=sys.stderr)
        print(USAGE, file=sys.stderr)
        sys.exit(1)

    # Lazy import: don't load the inferencer machinery when only the
    # parser is needed, and vice versa.
    try:
        driver = __import__(module_name)
    except ImportError as e:
        print(f"Could not load driver {module_name!r}: {e}", file=sys.stderr)
        sys.exit(2)

    # Each underlying driver reads its grammar file from sys.argv[1]
    # and expects exactly two argv entries.  Rewrite argv to that shape
    # so the driver runs unchanged.
    sys.argv = [f"main.py ({label})", grammar_file]
    driver.main()


if __name__ == "__main__":
    main()
