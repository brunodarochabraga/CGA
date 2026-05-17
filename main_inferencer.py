"""
main_inferencer.py
==================
Driver for the lexeme-inference workflow.

Loads a grammar from a .py file specified on the command line, runs
the inference algorithm from inferencer.py, and reports both the
inferred lexicon and the discrepancy measure.

Usage (standalone):
    python main_inferencer.py <grammar_file.py>

Usage (via dispatcher):
    python main.py inferencer <grammar_file.py>

The inference algorithm itself lives in `inferencer.py`.
The shared display helpers (`derivation_score`, `print_step`,
`print_banner`, `load_or_exit`) live in `main.py`.
"""

import sys

from category import Category
from inferencer import (
    parse_permissive,
    atomic_full_spans,
    infer_lexicon,
    expanded_coordinable,
    expanded_type_raise_targets,
    is_primed,
    diagnose_counterfactuals,
)
from main import derivation_score, print_step, print_banner, load_or_exit


# ============================================================
# S-extension test
# ============================================================
# An "S-extension" root atom is the canonical S itself or any
# prime-extension of S (S', S'', ...).  In the design adopted here,
# priming an atom means moving to a sister language: derivations
# rooted in S' are valid sentences in a parallel language to the
# canonical S-language, NOT failures.  Only derivations rooted in
# atoms that are not S-extensions (RR, RR', NP, ...) count as
# substantive failures, because they yield non-sentential categories.

def is_s_extension(root_name):
    """True iff root_name is S, S', S'', or any further prime-extension."""
    if not root_name.startswith("S"):
        return False
    suffix = root_name[1:]
    return suffix == "" or all(ch == "'" for ch in suffix)


def s_extension_count(atomic_items):
    """Number of full-spanning items whose root is an S-extension."""
    return sum(1 for it in atomic_items
               if is_s_extension(str(it.category.result)))


def non_s_extension_count(atomic_items):
    """Number of full-spanning items whose root is NOT an S-extension."""
    return sum(1 for it in atomic_items
               if not is_s_extension(str(it.category.result)))


# ============================================================
# Reporting helpers
# ============================================================

def print_modified_grammar(grammar_name, lexicon, rule_priorities,
                           coordinable_categories, unknowns, header):
    """
    Full grammar printout in the style of GrammarConfig.print_grammar(),
    with the inferred entries flagged so they stand out.
    """
    print(header)
    print(f"Grammar: {grammar_name}  (modified by inference)")

    print("  Lexicon:")
    for token, cats in lexicon.items():
        cats_str = " | ".join(str(c) for c in cats)
        flag = "  <<  inferred" if token in unknowns else ""
        print(f"   {token:<2} : {cats_str}{flag}")

    print("\n  Rule priorities:")
    for rule, prio in sorted(rule_priorities.items()):
        status = "DISABLED" if prio < 0 else prio
        print(f"   {rule:<6} : {status}")

    print("\n  Coordinable categories (extended with primed atoms):")
    print(f"   {sorted(coordinable_categories)}")


def print_derivations_for_sentence(sentence, items, rule_priorities):
    """
    Per-sentence printout. Returns (n_atomic_total, n_S_rooted) so the
    caller can tally the discrepancy measure.
    """
    print(f"Sentence: {sentence}")
    atomic_items = atomic_full_spans(items)
    if not atomic_items:
        print("  No derivation.")
        return 0, 0

    by_root_S = [it for it in atomic_items
                 if str(it.category.result) == "S"]

    # Order: S-rooted first; then by root name; then by score.
    ordered = sorted(
        atomic_items,
        key=lambda it: (
            0 if str(it.category.result) == "S" else 1,
            str(it.category.result),
            *derivation_score(it.steps, rule_priorities),
        ),
    )

    print(f"  Total derivations: {len(ordered)}  "
          f"(S-rooted: {len(by_root_S)}, "
          f"non-S-rooted: {len(ordered) - len(by_root_S)})")
    for d, it in enumerate(ordered, 1):
        score = derivation_score(it.steps, rule_priorities)
        print(f"  Derivation #{d} "
              f"[root={it.category}, "
              f"steps={len(it.steps)}, "
              f"score={score[1]}]")
        for i, step in enumerate(it.steps, 1):
            print_step(i, step)
    return len(atomic_items), len(by_root_S)


# ============================================================
# Main
# ============================================================

USAGE = "Usage: python main_inferencer.py <grammar_file.py>"


def main():
    if len(sys.argv) != 2:
        print(USAGE, file=sys.stderr)
        print("  Example: python main_inferencer.py GrammarTemplate.py",
              file=sys.stderr)
        sys.exit(1)

    grammar_file = sys.argv[1]
    config = load_or_exit(grammar_file)

    print_banner(grammar_file,
                 mode="INFERENTIAL",
                 subtitle="Lexeme inference by atomic differentiation")

    config.print_grammar()

    rule_priorities = config.rule_priorities
    coordinable = config.coordinable_categories
    base_targets = [Category("S")]   # mirrors CCGParser default

    # ---------- PRE-INFERENCE PARSE ----------
    print("\n" + "=" * 80)
    print("PRE-INFERENCE PARSE")
    print("=" * 80)

    total = len(config.sentences)
    pre_no_derivation = 0
    pre_S_failures = 0
    pre_status = {}   # sentence -> (strict_ok, S_ext_ok)

    for s in config.sentences:
        print("-" * 80)
        words = [w for w in s.split() if w != ","]
        items = parse_permissive(
            words, config.lexicon, rule_priorities,
            coordinable, base_targets,
        )
        n_total, _ = print_derivations_for_sentence(
            s, items, rule_priorities
        )
        # S-extension-rooted count: S, S', S'', ... all count as success.
        atomic_items = atomic_full_spans(items)
        n_S_ext = s_extension_count(atomic_items)
        if n_total == 0:
            pre_no_derivation += 1
        if n_S_ext == 0:
            pre_S_failures += 1
        pre_status[s] = (n_total > 0, n_S_ext > 0)

    # ---------- INFERENCE ----------
    print("\n" + "=" * 80)
    print("INFERENCE")
    print("=" * 80)

    # Build a per-word root policy from the grammar's optional
    # `inference_s_prime_only` attribute.  Words listed there are
    # inferred only with categories that appear in derivations whose
    # root atom is a primed sentence type (any string starting with
    # 'S' and containing at least one apostrophe).  All other words
    # (and all words when the attribute is absent) accept any root.
    s_prime_only_words = set(getattr(config, "inference_s_prime_only", set()))

    def _s_prime_predicate(root_name):
        return root_name.startswith("S") and "'" in root_name

    root_policy = {w: _s_prime_predicate for w in s_prime_only_words}

    if s_prime_only_words:
        print("Root-atom policy (per-word):")
        for w in sorted(s_prime_only_words):
            print(f"   {w:<3} : S-prime only "
                  f"(derivations rooted in canonical S are discarded)")
        print()

    inferred, unknowns, candidates = infer_lexicon(
        config.sentences, config.lexicon, rule_priorities,
        coordinable, base_targets,
        root_policy=root_policy,
    )

    if not unknowns:
        print("No unknown words; nothing to infer.")
        return

    print(f"Unknown words : {unknowns}")
    print(f"Candidate pool: {len(candidates)} differentiated variants "
          f"derived from existing lexicon skeletons")
    for c in candidates:
        marker = "*" if is_primed(c) else " "
        print(f"   {marker} {c}")
    print("   (* = differentiated / primed)")

    print("\nInferred categories per unknown word "
          "(simplest first; primed = differentiated):")

    augmented_lex = {k: list(v) for k, v in config.lexicon.items()}
    for w in unknowns:
        cats = inferred.get(w, [])
        if not cats:
            print(f"   {w:<2} : (no consistent inference --- "
                  f"sentences containing '{w}' will be ignored)")
            continue
        cats_str = " | ".join(
            (("*" if is_primed(c) else " ") + str(c))
            for c in cats
        )
        print(f"   {w:<2} : {cats_str}")
        augmented_lex[w] = cats

    print()
    extended_coord = expanded_coordinable(coordinable)
    extended_targets = expanded_type_raise_targets(base_targets)

    print_modified_grammar(
        config.name, augmented_lex, rule_priorities,
        extended_coord, set(unknowns),
        header="-" * 80,
    )

    # ---------- POST-INFERENCE PARSE ----------
    print("\n" + "=" * 80)
    print("POST-INFERENCE PARSE")
    print("=" * 80)

    post_no_derivation = 0
    post_S_failures = 0
    post_failing_sentences = []   # need counterfactual diagnostic
    post_status = {}   # sentence -> (strict_ok, S_ext_ok)
    for s in config.sentences:
        print("-" * 80)
        words = [w for w in s.split() if w != ","]
        items = parse_permissive(
            words, augmented_lex, rule_priorities,
            extended_coord, extended_targets,
        )
        n_total, _ = print_derivations_for_sentence(
            s, items, rule_priorities
        )
        atomic_items = atomic_full_spans(items)
        n_S_ext = s_extension_count(atomic_items)
        if n_total == 0:
            post_no_derivation += 1
        if n_S_ext == 0:
            post_S_failures += 1
            # Counterfactual diagnostic is for sentences that DERIVE
            # but only to non-sentential roots (RR, RR', etc.), or
            # that do not derive at all.  Sentences whose only
            # derivations root in S-extensions (S, S', S'', ...) are
            # successful in a sister language and are NOT diagnosed.
            post_failing_sentences.append(s)
        post_status[s] = (n_total > 0, n_S_ext > 0)

    # ---------- DISCREPANCY MEASURE ----------
    print("\n" + "=" * 80)
    print("DISCREPANCY MEASURE")
    print("=" * 80)

    def pct(num, den):
        return 0.0 if den == 0 else 100.0 * num / den

    # Per-sentence outcome table.  Two flags per sentence:
    #   strict : has ANY full-spanning derivation (any root atom).
    #   S-ext  : has a derivation rooted in S OR any prime-extension
    #            (S', S'', ...).  These belong to sister languages
    #            of the canonical S-language and count as successes.
    # ✓ = success, ✗ = failure.
    max_len = max(len(s) for s in config.sentences) if config.sentences else 0
    sent_w  = max(max_len, 12)
    print()
    print(f"  {'Sentence':<{sent_w}}    "
          f"{'strict before / after':>22}    "
          f"{'S-ext before / after':>22}")
    print(f"  {'-' * sent_w}    "
          f"{'-' * 22}    "
          f"{'-' * 22}")
    for s in config.sentences:
        pre_strict, pre_S   = pre_status[s]
        post_strict, post_S = post_status[s]
        strict_col = f"   {'✓' if pre_strict else '✗'}   /   " \
                     f"{'✓' if post_strict else '✗'}"
        S_col      = f"   {'✓' if pre_S      else '✗'}   /   " \
                     f"{'✓' if post_S      else '✗'}"
        print(f"  {s:<{sent_w}}    "
              f"{strict_col:>22}    "
              f"{S_col:>22}")
    print()
    print(f"Total sentences                       : {total}")
    print()
    print("Strict failure (no derivation at all,")
    print("regardless of root category):")
    print(f"   before intervention : {pre_no_derivation:>3} / {total}  "
          f"({pct(pre_no_derivation, total):>5.1f}%)")
    print(f"   after  intervention : {post_no_derivation:>3} / {total}  "
          f"({pct(post_no_derivation, total):>5.1f}%)")
    print()
    print("S-extension failure (no derivation rooted in S, S', S'',")
    print("...; sentences parse only to non-sentential atoms like RR):")
    print(f"   before intervention : {pre_S_failures:>3} / {total}  "
          f"({pct(pre_S_failures, total):>5.1f}%)")
    print(f"   after  intervention : {post_S_failures:>3} / {total}  "
          f"({pct(post_S_failures, total):>5.1f}%)")

    print()
    print("-" * 80)
    print("Final modified lexicon:")
    for token, cats in augmented_lex.items():
        cats_str = " | ".join(str(c) for c in cats)
        flag = "  <<  inferred" if token in unknowns else ""
        print(f"   {token:<2} : {cats_str}{flag}")

    # ---------- COUNTERFACTUAL DIAGNOSTIC ----------
    # For each sentence whose only derivations root in non-sentential
    # atoms (RR, RR', ...) or that does not derive at all, report
    # which single revision of a known word's lexical entry would
    # make the sentence parse to an S-extension (S, S', S'', ...).
    # Sentences that already derive an S-extension are NOT diagnosed:
    # under the design contract, deriving S' (or S'', ...) is a
    # successful parse in a sister language, not a failure.
    # The lexicon is NOT modified.  This is a deductive error message,
    # not an inferred fact.
    if post_failing_sentences:
        print()
        print("=" * 80)
        print("COUNTERFACTUAL DIAGNOSTIC")
        print("=" * 80)
        print("For each sentence that does not derive any S-extension")
        print("(S, S', S'', ...) after inference, we report which SINGLE")
        print("additional entry to a known word's lexical category set")
        print("would make the sentence parseable to an S-extension.")
        print()
        print("Sentences whose only derivations already root in an")
        print("S-extension are NOT diagnosed: they belong to a sister")
        print("language of the canonical S-language and are successful")
        print("parses, not failures.")
        print()
        print("⚠  These are COUNTERFACTUALS, not inferences. The actual")
        print("   lexicon is NOT modified. They are diagnostic information")
        print("   about which existing lexical commitments are implicated")
        print("   in each failure.")
        print()

        for s in post_failing_sentences:
            print("-" * 80)
            print(f"Sentence: {s}")
            cfs = diagnose_counterfactuals(
                s, augmented_lex, rule_priorities,
                extended_coord, extended_targets,
                protected_words=unknowns,
            )
            if not cfs:
                print("  No single-revision counterfactual fixes this")
                print("  sentence. The failure is structural: no single")
                print("  additional category for any single known word")
                print("  yields an S-derivation. Consider a corpus or")
                print("  grammar review rather than a lexical revision.")
                continue
            print(f"  {len(cfs)} single-revision counterfactual(s) found:")
            for k, cf in enumerate(cfs, 1):
                w = cf["word"]
                orig = " | ".join(str(c) for c in cf["original_cats"])
                added = cf["added_category"]
                marker = "*" if is_primed(added) else " "
                print(f"   [{k}] If {w} had, in addition to {{ {orig} }},")
                print(f"       the category {marker}{added}")
                print(f"       then '{s}' would derive S.")


if __name__ == "__main__":
    main()
