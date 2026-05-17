"""
main_parser.py
==============
CCG parser driver. Loads a grammar from a .py file specified on the
command line and prints all accepted derivations of every test
sentence in that grammar.

The driver is grammar-agnostic: it forwards the grammar's
`parse_target` predicate (if any) to the CCGParser, so grammars that
accept full-span derivations whose final category is non-atomic
(e.g. GrammarIndexed, whose target sentence reduces to S[t]\\S[t-2])
are handled correctly. When the grammar leaves `parse_target` at its
default (None), the parser falls back to the atomic-S criterion used
by GrammarTemplate.

Usage (standalone):
    python main_parser.py <grammar_file.py>

Usage (via dispatcher):
    python main.py parser <grammar_file.py>

The shared display helpers (`derivation_score`, `print_step`,
`print_banner`, `load_or_exit`) live in `main.py`.
"""

import sys

from parser import CCGParser
from main import derivation_score, print_step, print_banner, load_or_exit


USAGE = "Usage: python main_parser.py <grammar_file.py>"


def main():
    if len(sys.argv) != 2:
        print(USAGE, file=sys.stderr)
        print("  Example: python main_parser.py GrammarIndexed.py",
              file=sys.stderr)
        sys.exit(1)

    grammar_file = sys.argv[1]
    config = load_or_exit(grammar_file)

    print_banner(grammar_file)

    # Thread the grammar's acceptance predicate through to the parser.
    # GrammarIndexed declares parse_target=_s_headed (accepts any
    # S-headed category); GrammarTemplate leaves it as None, so the
    # parser falls back to its atomic-S default.
    parser = CCGParser(
        lexicon=config.lexicon,
        rule_priorities=config.rule_priorities,
        coordinable_categories=config.coordinable_categories,
        parse_target=config.parse_target,
    )

    config.print_grammar()

    for s in config.sentences:
        print("=" * 80)
        print("Sentence:", s)

        tokens = [w for w in s.split() if w != ","]
        traces = parser.parse(tokens)

        if not traces:
            print("  No derivation.")
            continue

        ordered_traces = sorted(
            traces,
            key=lambda t: derivation_score(t, config.rule_priorities),
        )

        print(f"  Total derivations: {len(ordered_traces)} ")
        for d, trace in enumerate(ordered_traces, 1):
            print(f"  Derivation #{d} "
                  f"[steps={len(trace)}, "
                  f"score={derivation_score(trace, config.rule_priorities)[1]}]")
            for i, step in enumerate(trace, 1):
                print_step(i, step)


if __name__ == "__main__":
    main()
