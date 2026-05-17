"""
inferencer.py
=============
Algorithm for inferring missing CCG lexemes by atomic differentiation.

Given a base grammar and a set of test sentences, this module:

  1. Identifies words that appear in sentences but not in the lexicon.
  2. Builds a finite candidate space by *atomic differentiation*: for
     every category structure already in the lexicon, generate every
     variant obtained by priming a (possibly empty) subset of its
     atomic positions, e.g.
         S\\RR  ->  S\\RR ,  S'\\RR ,  S\\RR' ,  S'\\RR'
     Primed atoms inherit the behavioural status of their unprimed
     counterparts (coordinability, eligibility as a type-raise target).
  3. Runs a permissive CKY parser that retains every full-spanning
     derivation regardless of root atom.
  4. Collects which candidate categories were actually consumed by
     occurrences of each unknown word in any successful derivation.
     The inferred lexicon for word `w` is that union.

The module is purely algorithmic. It performs no I/O, no printing, no
configuration choices. Driver scripts call `infer_lexicon` and friends
and decide for themselves how to report the results.
"""

from category import Category
from parser import (
    FA, BA, FC, BC, FS, BS, FXS, BXS, COORD,
    type_raise, Item, Step,
)


# ============================================================
# Atomic-position machinery
# ============================================================
# A category is a binary tree whose leaves are atomic names. Each
# leaf has a "path" --- a tuple of "L"/"R" --- locating it in the
# tree. Differentiation = renaming a chosen subset of leaves to
# their primed versions (RR -> RR', S -> S').

def atomic_positions(cat, prefix=()):
    """Return [(path, atom_name), ...] for every leaf of `cat`."""
    if cat.is_atomic():
        return [(prefix, str(cat.result))]
    positions = []
    if isinstance(cat.result, Category):
        positions.extend(atomic_positions(cat.result, prefix + ("L",)))
    else:
        positions.append((prefix + ("L",), str(cat.result)))
    positions.extend(atomic_positions(cat.argument, prefix + ("R",)))
    return positions


def replace_atom_at(cat, path, new_name):
    """Return a new Category with the leaf at `path` renamed."""
    if not path:
        return Category(new_name)
    head, rest = path[0], path[1:]
    if head == "L":
        if isinstance(cat.result, Category):
            new_result = replace_atom_at(cat.result, rest, new_name)
        else:
            assert not rest, "path runs past an atomic leaf"
            new_result = new_name
        return Category(new_result, cat.slash, cat.argument)
    else:  # "R"
        new_arg = replace_atom_at(cat.argument, rest, new_name)
        return Category(cat.result, cat.slash, new_arg)


def differentiate(cat, prime_indices, positions):
    """
    Return `cat` with the leaves at the chosen indices into `positions`
    renamed to their primed counterparts.
    """
    result = cat
    # Rename longer paths first so earlier renames don't move them.
    selected = sorted(
        [positions[i] for i in prime_indices],
        key=lambda p: -len(p[0]),
    )
    for path, original_atom in selected:
        result = replace_atom_at(result, path, original_atom + "'")
    return result


def category_size(cat):
    """Number of nodes in the category tree (atomic = 1)."""
    if cat.is_atomic():
        return 1
    left = category_size(cat.result) if isinstance(cat.result, Category) else 1
    return 1 + left + category_size(cat.argument)


def is_primed(cat):
    """True iff at least one leaf of `cat` carries a prime mark."""
    return any("'" in atom for _, atom in atomic_positions(cat))


# ============================================================
# Candidate generation (the hypothesis space)
# ============================================================

def generate_candidates(lexicon):
    """
    For every category structure currently in the lexicon, generate
    every differentiated variant (priming any subset of its atomic
    leaves, including the empty subset --- the unprimed original).

    The hypothesis space is therefore finite and bounded by
        sum_{C in lexicon} 2^{leaves(C)}
    duplicates removed by string identity.

    Returns the candidates ordered by increasing structural complexity.
    """
    candidates = []
    seen = set()
    for token, cats in lexicon.items():
        for cat in cats:
            positions = atomic_positions(cat)
            n = len(positions)
            for mask in range(2 ** n):
                indices = [i for i in range(n) if (mask >> i) & 1]
                variant = differentiate(cat, indices, positions)
                key = str(variant)
                if key not in seen:
                    seen.add(key)
                    candidates.append(variant)
    candidates.sort(key=lambda c: (category_size(c), str(c)))
    return candidates


# ============================================================
# Permissive CKY parser
# ============================================================
# Re-uses the combinators imported from parser.py without modifying
# them. Differs from CCGParser.parse in only one respect: it does not
# filter the final chart cell to S-rooted items; every full-spanning
# Item is returned.

def parse_permissive(words, lexicon, rule_priorities,
                     coordinable_categories, type_raise_targets):
    """Like CCGParser.parse, but returns every full-spanning Item,
    not only S-rooted ones."""
    n = len(words)
    if n == 0:
        return []
    chart = [[[] for _ in range(n + 1)] for _ in range(n)]

    all_rules = [FA, BA, FC, BC, FS, BS, FXS, BXS]
    rules = [r for r in all_rules
             if rule_priorities.get(r.__name__, float("inf")) >= 0]
    rules.sort(key=lambda r: rule_priorities.get(r.__name__, float("inf")))

    for i, w in enumerate(words):
        for cat in lexicon.get(w, []):
            base = Item(cat, [Step("LEX", [w], cat)])
            chart[i][i + 1].append(base)
            chart[i][i + 1].extend(
                type_raise(base, type_raise_targets, rule_priorities)
            )

    for span in range(2, n + 1):
        for i in range(n - span + 1):
            j = i + span
            for k in range(i + 1, j):
                for l in chart[i][k]:
                    for r in chart[k][j]:
                        for rule in rules:
                            res = rule(l, r)
                            if res:
                                chart[i][j].append(res)
                                chart[i][j].extend(
                                    type_raise(res, type_raise_targets,
                                               rule_priorities)
                                )
                        coord = COORD(l, r, coordinable_categories)
                        if coord:
                            chart[i][j].append(coord)

    return chart[0][n]


def atomic_full_spans(items):
    """Items that span the whole sentence and end at an atomic root."""
    return [it for it in items if it.category.is_atomic()]


# ============================================================
# Inference
# ============================================================

def find_unknowns(sentences, lexicon):
    """Words appearing in any sentence but absent from the lexicon."""
    unknowns = []
    seen = set()
    for s in sentences:
        for w in s.split():
            if w == ",":
                continue
            if w not in lexicon and w not in seen:
                unknowns.append(w)
                seen.add(w)
    return unknowns


def expanded_coordinable(coordinable_categories):
    """Add primed counterparts (S -> S', RR -> RR', ...) to the set."""
    expanded = set(coordinable_categories)
    for atom in list(coordinable_categories):
        expanded.add(atom + "'")
    return expanded


def expanded_type_raise_targets(targets):
    """Add primed counterparts of atomic type-raise targets."""
    expanded = list(targets)
    for t in targets:
        if t.is_atomic():
            expanded.append(Category(str(t.result) + "'"))
    return expanded


def infer_lexicon(sentences, base_lexicon, rule_priorities,
                  coordinable_categories, type_raise_targets,
                  root_policy=None):
    """
    Run inference over `sentences` against `base_lexicon`.

    Parameters
    ----------
    sentences, base_lexicon, rule_priorities,
    coordinable_categories, type_raise_targets :
        As before.

    root_policy : Optional[Dict[str, Callable[[str], bool]]]
        Per-word policy on the root atom of accepted derivations.
        A mapping from unknown-word name to a predicate over the
        string name of the derivation's root atom (e.g. "S", "S'",
        "RR", "RR'").  When supplied, an unknown word w accumulates
        a candidate category c ONLY from derivations whose root
        atom satisfies policy[w].  Words absent from the mapping
        accept any atomic root, preserving the previous behaviour.

        Example:
            root_policy = { "g'": lambda r: r == "S'" }
        means: g' is inferred only with categories that appear in
        derivations rooted in S', never in derivations rooted in S
        (or any other atom).  This expresses the substantive claim
        that g' marks a non-canonical sentence type, not a variant
        of the canonical S.

    Returns
    -------
      inferred  : dict word -> sorted list of inferred Categories
      unknowns  : list of unknown words (in order of first appearance)
      candidates: the full candidate pool (for reporting)
    """
    unknowns = find_unknowns(sentences, base_lexicon)
    if not unknowns:
        return {}, [], []

    candidates = generate_candidates(base_lexicon)

    trial_lex = {k: list(v) for k, v in base_lexicon.items()}
    for w in unknowns:
        trial_lex[w] = list(candidates)

    extended_coord = expanded_coordinable(coordinable_categories)
    extended_targets = expanded_type_raise_targets(type_raise_targets)

    # Default predicate: accept any atomic root.
    def _accept_any(_root_name):
        return True

    policy = dict(root_policy or {})
    for w in unknowns:
        policy.setdefault(w, _accept_any)

    inferred = {w: set() for w in unknowns}

    for sentence in sentences:
        words = [w for w in sentence.split() if w != ","]
        if not any(w in unknowns for w in words):
            continue

        items = parse_permissive(
            words, trial_lex, rule_priorities,
            extended_coord, extended_targets,
        )
        atomic_items = atomic_full_spans(items)

        for it in atomic_items:
            root_name = str(it.category.result)
            for step in it.steps:
                if step.rule == "LEX" and step.inputs[0] in unknowns:
                    w = step.inputs[0]
                    if policy[w](root_name):
                        inferred[w].add(step.output)

    inferred_sorted = {
        w: sorted(cats, key=lambda c: (category_size(c), str(c)))
        for w, cats in inferred.items()
    }
    return inferred_sorted, unknowns, candidates


# ============================================================
# Counterfactual diagnostic (does NOT modify the lexicon)
# ============================================================
# For each unparsable sentence, ask: "which single revision of a
# known word's lexical entry would make this sentence parse to S?"
#
# A revision is the *addition* of one differentiated variant to an
# existing known word, not the replacement of its current category.
# We try one such revision at a time, holding the rest of the lexicon
# fixed. The output is a structured report of counterfactuals; the
# caller decides how to display them. The actual lexicon is never
# changed.
#
# This preserves the rigid-inference contract (one fixed category per
# known word, only unknowns are subject to inference) while giving
# the user an interpretable diagnostic when a sentence still fails
# after inference. It is the deductive analogue of an error message,
# not an inferred fact.


def _is_s_extension_name(name):
    """True iff `name` is 'S' or any prime-extension 'S', 'S\'', 'S\'\'', ..."""
    if not name.startswith("S"):
        return False
    suffix = name[1:]
    return suffix == "" or all(ch == "'" for ch in suffix)


def parses_to_S(words, lexicon, rule_priorities,
                coordinable_categories, type_raise_targets):
    """True iff `words` admits at least one full-spanning derivation
    rooted in an S-extension (S, S', S'', ...).  Under the design
    contract, all of these are successful parses in (possibly sister)
    sentence languages."""
    items = parse_permissive(
        words, lexicon, rule_priorities,
        coordinable_categories, type_raise_targets,
    )
    for it in items:
        if it.category.is_atomic() and _is_s_extension_name(str(it.category.result)):
            return True
    return False


def diagnose_counterfactuals(sentence, lexicon, rule_priorities,
                             coordinable_categories, type_raise_targets,
                             protected_words=()):
    """
    Given a sentence that does not parse to S under the current
    lexicon, enumerate single-revision counterfactuals: for each
    known word w (not in `protected_words`) and each candidate
    category `v` drawn from the full grammar candidate pool, test
    whether augmenting w's entries with `v` would make the sentence
    parse to S.

    The candidate pool is the same one used by `infer_lexicon` for
    unknowns: every differentiated variant of every category currently
    in the lexicon. This is wider than just the differentiated
    variants of w's own categories: the counterfactual may need to
    give w a category SHAPE it does not currently possess (e.g. an
    atomic category for a word whose only entry is a functor).

    Parameters
    ----------
    sentence            : the sentence string (tokens whitespace-split,
                          commas ignored, as elsewhere in the module).
    lexicon             : the lexicon as it stands AFTER inference.
    rule_priorities     : grammar's rule priorities.
    coordinable_categories : set of coordinable atomic names
                          (already expanded with primed atoms).
    type_raise_targets  : list of type-raise target Categories
                          (already expanded with primed atoms).
    protected_words     : iterable of words that should NOT be
                          counterfactually revised (typically the
                          inferred-unknown words: revising them
                          would just re-run inference, not diagnose).

    Returns
    -------
    List of dicts, each describing one successful counterfactual:
        {
          "word"           : str   - the known word being revised
          "original_cats"  : list[Category] - its current entries
          "added_category" : Category - the extra entry that fixes it
        }
    The list is sorted by structural simplicity of the added category.
    Empty list iff no single-revision counterfactual exists.
    """
    words = [w for w in sentence.split() if w != ","]
    if not words:
        return []

    protected = set(protected_words)
    counterfactuals = []
    seen_keys = set()

    # The candidate pool is the full grammar pool, identical to the
    # one used for inference of unknowns. This keeps the diagnostic
    # symmetric with inference: any category the inferencer would
    # consider for an unknown is also a candidate for counterfactual
    # revision of a known word.
    candidate_pool = generate_candidates(lexicon)

    # Iterate over the KNOWN words actually appearing in this sentence;
    # there is no point counterfactually revising a word that is not
    # used by the sentence.
    sentence_known_words = [
        w for w in dict.fromkeys(words)
        if w in lexicon and w not in protected
    ]

    for w in sentence_known_words:
        current_cats = list(lexicon[w])
        for v in candidate_pool:
            # Skip the trivial case: v is already in w's lexicon.
            if any(str(v) == str(c) for c in current_cats):
                continue
            # Build a trial lexicon: clone, add v to w's entries.
            trial_lex = {k: list(cats) for k, cats in lexicon.items()}
            trial_lex[w] = list(current_cats) + [v]
            if parses_to_S(words, trial_lex, rule_priorities,
                           coordinable_categories, type_raise_targets):
                key = (w, str(v))
                if key not in seen_keys:
                    seen_keys.add(key)
                    counterfactuals.append({
                        "word": w,
                        "original_cats": list(current_cats),
                        "added_category": v,
                    })

    counterfactuals.sort(
        key=lambda cf: (
            category_size(cf["added_category"]),
            cf["word"],
            str(cf["added_category"]),
        )
    )
    return counterfactuals
