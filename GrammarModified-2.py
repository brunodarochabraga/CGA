"""
GrammarModified-2.py
====================
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


class GrammarModifiedV2(GrammarConfig):
    name = "modified-2"

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
                # g  appears after RR-prefixes only.
                "i c g",
                "i c c g",

                # g' appears after RR'-prefixes only.
                "i' c g'",
                "i' c c g'",

                # A mixed sentence: an unprimed run coordinated with
                # a primed run.  This forces g' away from S\RR (which
                # would not unify with the i' c prefix) and pins it
                # to S\RR'.  The S COORD S closes the whole sentence.
                "i c g i' c g'",
            ],
        )
