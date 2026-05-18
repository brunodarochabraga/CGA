"""
measurer.py
===========
Configurational analysis measures for a CCG grammar:

  - discrepancy   D(L)  = 1 - parsed / total
  - consistency   |X ∩ Y| / |X|
  - coverage      |X ∩ Y| / |Y|
  - explanations  total number of full-spanning atomic-rooted derivations
  - configurations and their per-configuration indices
  - Step 4 ablation:  eliminate hypothesis types t such that
    D(L' \\ {t}) is not strictly greater than D(L')

Semantics (per the manuscript):

  * A Configuration is a SET of types -- not a multiset, not a set of
    (symbol, type) pairs.  Two derivations using the same set of types
    map to the same configuration even if they assign those types to
    different symbols or use them different numbers of times.

  * A string s has the OUTCOME OF INTEREST iff some derivation of s
    uses a configuration containing a type whose atomic subterms
    include a primed-S atom ('S\\'', 'S\\'\\'', ...).  The check is
    over the lexical types assigned to symbols (i.e., types appearing
    in the configuration), not over intermediate-result categories
    that arise during the derivation.

  * The discrepancy D(L) is the fraction of strings in S that do NOT
    have a full-spanning atomic-rooted derivation under L, regardless
    of root atom.  Lower is better; D in [0, 1].
"""

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Dict, FrozenSet, List, Set, Tuple

from category import Category
from parser import Step
from inferencer import (
    parse_permissive,
    atomic_full_spans,
    expanded_coordinable,
    expanded_type_raise_targets,
)


# ============================================================
# Primed-S detection
# ============================================================

def _atom_name(c: Category) -> str:
    """Return the name string of an atomic category, e.g. 'S', 'S\\'', 'RR'."""
    return str(c.result) if isinstance(c.result, str) else str(c.result)


def _has_primed_S_atom(cat: Category) -> bool:
    """
    True iff `cat` contains any atomic subterm whose name is a
    PRIMED-S: starts with 'S' and is followed by one or more
    apostrophes.  'S' alone does NOT qualify; 'RR\\'' does not
    qualify (does not start with 'S').
    """
    if cat is None:
        return False
    if cat.is_atomic():
        name = _atom_name(cat)
        return (name.startswith("S")
                and len(name) > 1
                and all(ch == "'" for ch in name[1:]))
    left = (_has_primed_S_atom(cat.result)
            if isinstance(cat.result, Category)
            else _has_primed_S_atom(Category(cat.result)))
    return left or _has_primed_S_atom(cat.argument)


def carries_outcome_of_interest(types: Set[Category]) -> bool:
    """
    True iff at least one type in the set contains a primed-S atomic
    subterm.  This is the test that decides whether a configuration
    'leads to the outcome of interest'.
    """
    return any(_has_primed_S_atom(t) for t in types)


# ============================================================
# Configuration extraction
# ============================================================

def configuration_of_derivation(steps: List[Step]) -> FrozenSet[Category]:
    """
    Reduce a derivation (sequence of Step) to its CONFIGURATION:
    the SET of lexical types assigned to symbols of the string.

    Only LEX steps are inspected; the types that appear in non-LEX
    rule applications are intermediate results of combinator
    composition and are NOT part of the configuration.
    """
    types = set()
    for step in steps:
        if step.rule == "LEX":
            # step.output is the lexical category assigned.
            types.add(step.output)
    return frozenset(types)


# ============================================================
# Top-level measures
# ============================================================

@dataclass
class ConfigStats:
    types: FrozenSet[Category]
    hasCondition: int = 0       # # strings whose derivation uses this configuration
    hasBoth: int = 0            # # of those strings that also have the outcome
    consistency: float = 0.0
    coverage: float = 0.0


@dataclass
class MeasuresResult:
    total_strings: int
    parsed_strings: int          # # strings with at least one atomic-rooted derivation
    hasOutcome: int              # # strings with outcome of interest
    explanations: int            # # of all atomic-rooted derivations across all strings
    discrepancy: float           # D = 1 - parsed_strings / total_strings
    configurations: List[ConfigStats] = field(default_factory=list)
    # Per-string diagnostic: how the string was classified.
    per_string: List[dict] = field(default_factory=list)


def compute_measures(sentences: List[str],
                     lexicon: Dict[str, List[Category]],
                     rule_priorities: Dict[str, int],
                     coordinable_categories: Set[str],
                     type_raise_targets: List[Category]) -> MeasuresResult:
    """
    Compute the configurational measures for the given grammar over
    the given list of sentence strings.

    The lexicon is taken as-is (no inference is performed here);
    callers wishing to evaluate L' should pass the inferred L'.
    Coordinable categories and type-raise targets are also taken
    as-is; if the grammar's inference pipeline has expanded them with
    primed counterparts, the caller should pass the expanded versions.
    """
    n_total = len(sentences)
    n_parsed = 0
    hasOutcome = 0
    explanations = 0

    # Map from configuration (frozenset of types) -> {
    #     "hasCondition": int,        # number of strings using it
    #     "hasBoth": int,             # of those, number with outcome
    # }
    cfg_index: Dict[FrozenSet[Category], Dict[str, int]] = defaultdict(
        lambda: {"hasCondition": 0, "hasBoth": 0}
    )

    per_string = []

    for s in sentences:
        words = [w for w in s.split() if w != ","]
        items = parse_permissive(
            words, lexicon, rule_priorities,
            coordinable_categories, type_raise_targets,
        )
        atomic_items = atomic_full_spans(items)

        if not atomic_items:
            per_string.append({
                "sentence": s,
                "parsed": False,
                "outcome": False,
                "n_derivations": 0,
                "configurations": [],
            })
            continue

        n_parsed += 1
        explanations += len(atomic_items)

        # Collect the configurations witnessed by THIS string (as a
        # set -- multiple derivations may produce the same config).
        s_configs: Set[FrozenSet[Category]] = set()
        for it in atomic_items:
            s_configs.add(configuration_of_derivation(it.steps))

        # Does any configuration of this string carry the outcome?
        s_has_outcome = any(carries_outcome_of_interest(set(c))
                            for c in s_configs)
        if s_has_outcome:
            hasOutcome += 1

        # Update per-configuration bookkeeping: each configuration
        # gets +1 hasCondition, and +1 hasBoth iff the string has
        # the outcome.  We only register configurations that
        # themselves carry the outcome -- consistency and coverage
        # are defined only over outcome-carrying configurations.
        for cfg in s_configs:
            if carries_outcome_of_interest(set(cfg)):
                cfg_index[cfg]["hasCondition"] += 1
                if s_has_outcome:
                    cfg_index[cfg]["hasBoth"] += 1

        per_string.append({
            "sentence": s,
            "parsed": True,
            "outcome": s_has_outcome,
            "n_derivations": len(atomic_items),
            "configurations": list(s_configs),
        })

    # Compute per-configuration consistency and coverage.
    configurations: List[ConfigStats] = []
    for cfg, counts in cfg_index.items():
        cs = ConfigStats(types=cfg,
                         hasCondition=counts["hasCondition"],
                         hasBoth=counts["hasBoth"])
        cs.consistency = (cs.hasBoth / cs.hasCondition
                          if cs.hasCondition > 0 else 0.0)
        cs.coverage = (cs.hasBoth / hasOutcome
                       if hasOutcome > 0 else 0.0)
        configurations.append(cs)

    # Sort: highest coverage first, then highest consistency.
    configurations.sort(
        key=lambda cs: (-cs.coverage, -cs.consistency, len(cs.types))
    )

    discrepancy = 1.0 - (n_parsed / n_total) if n_total > 0 else 0.0

    return MeasuresResult(
        total_strings=n_total,
        parsed_strings=n_parsed,
        hasOutcome=hasOutcome,
        explanations=explanations,
        discrepancy=discrepancy,
        configurations=configurations,
        per_string=per_string,
    )


# ============================================================
# Step 4: ablation of hypothesis types
# ============================================================

def ablate_hypothesis_types(sentences: List[str],
                            lexicon_reference: Dict[str, List[Category]],
                            lexicon_prime: Dict[str, List[Category]],
                            rule_priorities: Dict[str, int],
                            coordinable_categories: Set[str],
                            type_raise_targets: List[Category]
                            ) -> Tuple[Dict[str, List[Category]], List[dict]]:
    """
    Step 4 of the manuscript's algorithm.

    For each hypothesis-introduced type t in L' (i.e., each type
    appearing in L'[symbol] but not in L[symbol]), test whether
    removing t from L' makes the discrepancy STRICTLY WORSE.

      If D(L' \\ {t}) > D(L'):  the type is necessary; keep it.
      Else:                     the type is redundant; eliminate it.

    Returns (pruned_lexicon, decisions) where `decisions` is a list of
    {"symbol", "type", "D_after_removal", "D_prime", "kept"} dicts.
    """
    # First compute D(L') for comparison.
    measures_prime = compute_measures(
        sentences, lexicon_prime, rule_priorities,
        coordinable_categories, type_raise_targets,
    )
    D_prime = measures_prime.discrepancy

    # Identify hypothesis types per symbol.
    decisions = []
    pruned = {w: list(cats) for w, cats in lexicon_prime.items()}

    for symbol, cats in lexicon_prime.items():
        reference_cats = lexicon_reference.get(symbol, [])
        reference_strs = {str(c) for c in reference_cats}
        # A type is a hypothesis type iff its string form is NOT
        # already among the reference types for this symbol.
        for t in cats:
            if str(t) in reference_strs:
                continue  # reference type, not subject to ablation
            # Build trial lexicon without this type.
            trial = {w: list(c) for w, c in pruned.items()}
            trial[symbol] = [c for c in trial[symbol] if str(c) != str(t)]
            if not trial[symbol]:
                del trial[symbol]
            measures_trial = compute_measures(
                sentences, trial, rule_priorities,
                coordinable_categories, type_raise_targets,
            )
            D_trial = measures_trial.discrepancy
            keep = D_trial > D_prime
            decisions.append({
                "symbol": symbol,
                "type": t,
                "D_after_removal": D_trial,
                "D_prime": D_prime,
                "kept": keep,
            })
            if not keep:
                pruned = trial   # eliminate t

    return pruned, decisions


# ============================================================
# Reporting
# ============================================================

def print_measures_report(result: MeasuresResult, *,
                          title: str = "MEASURES",
                          show_configurations: bool = True,
                          show_per_string: bool = True) -> None:
    print("=" * 80)
    print(title)
    print("=" * 80)
    print(f"Total strings           : {result.total_strings}")
    print(f"Parsed strings          : {result.parsed_strings}")
    print(f"Strings w/ outcome (Y)  : {result.hasOutcome}")
    print(f"Total derivations (N_d) : {result.explanations}")
    print(f"Discrepancy D           : {result.discrepancy:.4f}  "
          f"(= 1 - {result.parsed_strings}/{result.total_strings})")

    if result.explanations > result.hasOutcome and result.hasOutcome > 0:
        excess = result.explanations - result.hasOutcome
        print(f"  Note: {result.explanations} derivations for "
              f"{result.hasOutcome} outcome-bearing strings "
              f"({excess} concurrent explanation(s)). Aim is to keep "
              f"this difference close to zero.")

    if show_per_string:
        print()
        print("-" * 80)
        print("Per-string classification:")
        print("-" * 80)
        for d in result.per_string:
            tag_parse = "PARSED " if d["parsed"] else "FAIL   "
            tag_out   = "OUTCOME" if d["outcome"] else "       "
            print(f"  [{tag_parse}] [{tag_out}] "
                  f"{d['n_derivations']:>3} deriv  :  {d['sentence']}")

    if show_configurations:
        print()
        print("-" * 80)
        print("Outcome-carrying configurations "
              "(set of lexical types assigned to symbols):")
        print("-" * 80)
        if not result.configurations:
            print("  (none -- no configuration carries the outcome of interest)")
        else:
            print(f"  {'#':>3}  {'cons':>6}  {'cov':>6}  "
                  f"{'hasCond':>7}  {'hasBoth':>7}  types")
            for k, cs in enumerate(result.configurations, 1):
                types_str = " , ".join(sorted(str(t) for t in cs.types))
                print(f"  {k:>3}  {cs.consistency:>6.3f}  {cs.coverage:>6.3f}"
                      f"  {cs.hasCondition:>7}  {cs.hasBoth:>7}"
                      f"  {{ {types_str} }}")


def print_ablation_report(decisions: List[dict],
                          pruned_lexicon: Dict[str, List[Category]]) -> None:
    print("=" * 80)
    print("STEP 4: HYPOTHESIS-TYPE ABLATION")
    print("=" * 80)
    print("Each row: test whether removing one hypothesis type from L'")
    print("makes the discrepancy strictly worse.  If yes, the type is")
    print("KEPT (necessary); if not, it is ELIMINATED (redundant).")
    print()
    if not decisions:
        print("  (no hypothesis types to ablate)")
    else:
        d_prime_label = "D(L')"
        d_star_label  = "D(L*)"
        print(f"  {'symbol':<6}  {'type':<32}  "
              f"{d_star_label:>7}  {d_prime_label:>7}  decision")
        print(f"  {'-' * 6}  {'-' * 32}  "
              f"{'-' * 7}  {'-' * 7}  {'-' * 8}")
        for d in decisions:
            dec = "KEPT" if d["kept"] else "ELIMINATED"
            type_str = str(d["type"])
            if len(type_str) > 32:
                type_str = type_str[:29] + "..."
            print(f"  {d['symbol']:<6}  {type_str:<32}  "
                  f"{d['D_after_removal']:>7.4f}  {d['D_prime']:>7.4f}  {dec}")

    print()
    print("Pruned lexicon (after ablation):")
    for w, cats in pruned_lexicon.items():
        cats_str = " | ".join(str(c) for c in cats)
        print(f"   {w:<3} : {cats_str}")
