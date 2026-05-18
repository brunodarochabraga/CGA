"""
main_measurer.py
================
End-to-end driver for the configurational-analysis measures.

Workflow
--------
1. Load a grammar from a .py file.
2. Compute D(L), the BASELINE discrepancy under the reference
   lexicon (no inference).
3. Run the inferencer to obtain the augmented lexicon L'
   (configurations that solve the missing-type-structure problem).
4. Compute D(L'), consistency, coverage, and configurations under L'.
5. Step 4 ablation: eliminate hypothesis types from L' whose removal
   does not strictly worsen the discrepancy.
6. Report the measures one more time on the pruned lexicon.

Usage:
    python main_measurer.py <grammar_file.py>

Examples:
    python main_measurer.py GrammarTemplate.py
    python main_measurer.py GrammarModified.py
"""

import sys

from category import Category
from main import print_banner, load_or_exit
from inferencer import (
    infer_lexicon, expanded_coordinable, expanded_type_raise_targets,
)
from measurer import (
    compute_measures, ablate_hypothesis_types,
    print_measures_report, print_ablation_report,
)


USAGE = "Usage: python main_measurer.py <grammar_file.py>"


def main():
    if len(sys.argv) != 2:
        print(USAGE, file=sys.stderr)
        sys.exit(1)

    grammar_file = sys.argv[1]
    config = load_or_exit(grammar_file)

    print_banner(grammar_file, mode="MEASURES",
                 subtitle="Configurational analysis (D, consistency, coverage)")

    config.print_grammar()

    rule_priorities = config.rule_priorities
    coordinable_base = config.coordinable_categories
    base_targets = [Category("S")]

    # ---------------------------------------------------------------
    # 1.  Baseline:  D(L) on the reference lexicon.
    # ---------------------------------------------------------------
    baseline = compute_measures(
        config.sentences, config.lexicon, rule_priorities,
        coordinable_base, base_targets,
    )
    print()
    print_measures_report(baseline, title="BASELINE  D(L)  -- reference lexicon",
                          show_configurations=False)

    # ---------------------------------------------------------------
    # 2.  Run inferencer to obtain L'.
    # ---------------------------------------------------------------
    s_prime_only_words = set(getattr(config, "inference_s_prime_only", set()))
    if s_prime_only_words:
        def _s_prime_predicate(root_name):
            return root_name.startswith("S") and "'" in root_name
        root_policy = {w: _s_prime_predicate for w in s_prime_only_words}
    else:
        root_policy = None

    inferred, unknowns, candidates = infer_lexicon(
        config.sentences, config.lexicon, rule_priorities,
        coordinable_base, base_targets,
        root_policy=root_policy,
    )

    print()
    print("=" * 80)
    print("INFERENCE")
    print("=" * 80)
    if not unknowns:
        print("No unknown words; L' = L.  Skipping inference.")
        return
    print(f"Unknown words : {unknowns}")
    augmented_lex = {w: list(cats) for w, cats in config.lexicon.items()}
    for w in unknowns:
        cats = inferred.get(w, [])
        if not cats:
            print(f"   {w:<3} : (no consistent inference)")
            continue
        cats_str = " | ".join(str(c) for c in cats)
        print(f"   {w:<3} : {cats_str}   <<  inferred")
        augmented_lex[w] = cats

    # When the inferencer's atomic-differentiation expanded the
    # coordinable set and the type-raise targets, the augmented
    # lexicon may have primed atoms; we must use the extended
    # versions for the L'-side measures.
    extended_coord   = expanded_coordinable(coordinable_base)
    extended_targets = expanded_type_raise_targets(base_targets)

    # ---------------------------------------------------------------
    # 3.  Measures under L'.
    # ---------------------------------------------------------------
    result_prime = compute_measures(
        config.sentences, augmented_lex, rule_priorities,
        extended_coord, extended_targets,
    )
    print()
    print_measures_report(result_prime,
                          title="MEASURES UNDER L'  (after inference)")

    # ---------------------------------------------------------------
    # 4.  Step 4 ablation.
    # ---------------------------------------------------------------
    print()
    pruned_lex, decisions = ablate_hypothesis_types(
        config.sentences, config.lexicon, augmented_lex, rule_priorities,
        extended_coord, extended_targets,
    )
    print_ablation_report(decisions, pruned_lex)

    # ---------------------------------------------------------------
    # 5.  Measures under the pruned lexicon.
    # ---------------------------------------------------------------
    if pruned_lex != augmented_lex:
        result_pruned = compute_measures(
            config.sentences, pruned_lex, rule_priorities,
            extended_coord, extended_targets,
        )
        print()
        print_measures_report(result_pruned,
                              title="MEASURES AFTER ABLATION")

    # ---------------------------------------------------------------
    # 6.  Summary.
    # ---------------------------------------------------------------
    print()
    print("=" * 80)
    print("SUMMARY  (phi = D(L) - D(L'))")
    print("=" * 80)
    final = (result_pruned if pruned_lex != augmented_lex else result_prime)
    print(f"  D(L)                 = {baseline.discrepancy:.4f}")
    print(f"  D(L')                = {result_prime.discrepancy:.4f}")
    if pruned_lex != augmented_lex:
        print(f"  D(L') after ablation = {final.discrepancy:.4f}")
    phi = baseline.discrepancy - final.discrepancy
    print(f"  phi                  = {phi:.4f}  "
          f"({'improvement' if phi > 0 else 'no improvement' if phi == 0 else 'regression'})")


if __name__ == "__main__":
    main()
