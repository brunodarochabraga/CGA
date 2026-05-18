"""
GrammarModified.py
==================
Variant of the template grammar in which the symbol g' is genuinely
distinguished from g by its left-prefix context, in a sense that the
inference algorithm can verify deductively.

Design
------
The base grammar has three known symbols:

    i  : RR                 (initial state)
    c  : RR\\RR              (state-preserving transition)
    g  : S\\RR               (terminating transition, closes an RR prefix)

We add one more known symbol that acts as a *primed* initial state:

    i' : RR'                (initial state of a primed run)

and we treat c as also accepting the primed state by giving it a
second entry:

    c  : RR\\RR  |  RR'\\RR'  (state-preserving in either run)

The unknown symbol g' has no lexical entry. Its category is to be
inferred from context. The corpus is constructed so that every
sentence containing g' has, immediately to its left, a prefix that
reduces deductively to RR' (not RR). Every sentence containing g
has a left-prefix that reduces to RR.

Under atomic differentiation, the candidate pool for g' includes
both S\\RR and S\\RR'. The algorithm then *forces* g' = S\\RR'
because:

  - the prefix 'i c'    reduces to RR     (so g must be S\\RR)
  - the prefix 'i' c'   reduces to RR'    (so g' must be S\\RR')
  - mixing them would be deductively inconsistent

This is the prefix-based deductive distinction the manuscript needs:
g and g' differ not by labelling convention but as a logical
consequence of the combinatory structure of their left contexts.

Note that the LLM, when generating decision sequences, would not
produce 'i'' as an explicit token --- in the manuscript framing,
the primed initial state stands in for a run that began under
different conditions (e.g. a different prompt class, a different
reasoning mode). The grammar makes that distinction visible to
the inferencer.
"""

from category import Category
from grammar_config import GrammarConfig


class GrammarModified(GrammarConfig):
    name = "modified"

    # ---------------------------------------------------------------
    # Per-word root-atom policy for inference.
    #
    # An unknown word listed in `inference_s_prime_only` is inferred
    # only with categories that, in every derivation in which they
    # appear, root that derivation in a primed sentence atom (S', S'',
    # ...).  Derivations rooted in canonical S are discarded for that
    # word.  The substantive claim is that g' marks a non-canonical
    # sentence type: an LLM continuation produced under different
    # conditions than the canonical S-class run.
    #
    # The inferencer driver consumes this attribute via
    #   getattr(config, 'inference_s_prime_only', set())
    # and is therefore an opt-in feature; grammars that do not declare
    # it behave exactly as before.
    # ---------------------------------------------------------------
    inference_s_prime_only = {"g'"}

    def __init__(self):
        RR  = Category("RR")
        RRp = Category("RR'")
        S   = Category("S")
        self.RR  = RR
        self.RRp = RRp
        self.S   = S

        super().__init__(
            name=self.name,

            rule_priorities={"FA": 1, "BA": 1, "FC": 2, "BC": 2,
                             "FS": 4, "BS": 4, "FXS": 6, "BXS": 6,
                             "COORD": 8, "FTR": -9, "BTR": -9},

            lexicon={
                # ---- unprimed run ----
                "i":  [RR],                              # initial state
                "g":  [Category("S", "\\", RR)],         # closes an RR run

                # ---- primed run ----
                "i'": [RRp],                             # primed initial state

                # ---- state-preserving transition, available in both runs ----
                "c":  [Category("RR",  "\\", RR),
                       Category("RR'", "\\", RRp)],

                # ---- g' has no entry ----  the inferencer must discover
                # that g' : S\RR' from the surrounding prefix.
            },

            # Both RR and RR' are coordinable atoms (a primed and an
            # unprimed run can each be the unit of coordination); S is
            # coordinable as before so that two complete sentences can
            # combine.
            coordinable_categories={"RR", "RR'", "S"},

            sentences=[
                # ---- REFERENCE-LANGUAGE STRINGS (no outcome of interest) ----
                # These use only unprimed types; their configurations do not
                # carry a primed-S atom, so they are NOT outcome-bearing,
                # though they parse and reduce D(L) and D(L').
                "i g",            # config: { RR , S\RR }
                "i c g",          # config: { RR , RR\RR , S\RR }
                "i c c g",        # config: { RR , RR\RR , S\RR }
                "i i g",          # uses COORD (RR,RR=>RR), then BA

                # ---- OUTCOME-OF-INTEREST STRINGS ----
                # All of these use g', which the inferencer pins to
                # S'\RR' (a type containing the primed-S atom).
                # Their configurations CARRY the outcome of interest.
                "i' g'",          # smallest primed sentence: needs g' = S'\RR'
                "i' c g'",        # adds the primed c entry RR'\RR'
                "i' c c g'",      # repeats c (still same configuration!)

                # ---- MIXED SENTENCES ----
                # Two-track coordination: unprimed and primed run joined.
                # If g' is inferred as S'\RR' the two halves close into
                # S and S' respectively; S COORD S' fails (atoms differ),
                # so these strings genuinely fail to parse.  They serve
                # as discrepancy-driving negative examples.
                "i c g i' c g'",
                "i' c g' i c g",

                # ---- CONFIGURATION-OVERLAP DESIGN ----
                # These three primed strings all use the same lexical
                # types in their derivation: { RR' , RR'\RR' , S'\RR' }.
                # They produce ONE configuration witnessed by THREE
                # strings, giving a hasCondition > 1 and a non-trivial
                # consistency ratio.
                "i' c c c g'",
                "i' c c g' i' c g'",   # also exercises COORD if RR' is coordinable

                # ---- STRUCTURALLY UNGRAMMATICAL ----
                # No initial state; D(L) > 0; ablation can later test
                # whether any hypothesis fixes it.
                "c c g i c g'",
            ],
        )
