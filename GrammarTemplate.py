"""
GrammarTemplate.py
==================
Canonical "template" grammar.  This file plays two roles:

  1. It is the reference grammar exercised by main_parser.py and
     main_inferencer.py.
  2. It is the structural template from which more specialised grammars
     (e.g. GrammarIndexed.py) are derived: copy this file, adjust the
     lexicon, sentences, and rule priorities, and override `name`.

Loaded by the drivers via grammar_loader.load_grammar_from_file.
"""

from category import Category
from grammar_config import GrammarConfig


class GrammarTemplate(GrammarConfig):
    name = "template"

    def __init__(self):
        # Grammar-specific atomic categories
        RR = Category("RR")
        self.RR = RR
        S  = Category("S")
        self.S = S

        super().__init__(
            name=self.name,

            rule_priorities={"FA": 1, "BA": 1, "FC": 2, "BC": 2,
                             "FS": 4, "BS": 4, "FXS": 6, "BXS": 6,
                             "COORD": 8, "FTR": -9, "BTR": -9},

            lexicon={
                "i": [RR],
                "c": [Category("RR", "\\", RR)],   # RR\RR
                "g": [Category("S",  "\\", RR)],   # S\RR
            },

            coordinable_categories={"RR", "S"},

            sentences=[
                # ---- Reference language (parses under L with no inference) ----
                # These derive plain S and have no outcome of interest.
                # They serve as the baseline: D(L) and D(L') should both
                # parse them.
                "i g",            # i + S\RR  ->  S
                "i c g",          # i c -> RR ; RR + S\RR -> S
                "i c c g",        # i c c -> RR ; RR + S\RR -> S

                # ---- Strings containing the unknown symbol x ----
                # Pure-x sentences (similar context to g, will infer x ~ S\RR)
                "i x",
                "i c x",
                "i c c x",

                # Mixed sentence: needs S COORD S (RR & S both coordinable);
                # uses x and g in symmetric positions.  Multiple x and
                # multiple g coordinated.
                "i x i g",
                "i c x i c g",

                # ---- Strings designed to be HARD ----
                # No initial state -- structurally ungrammatical; should
                # NOT parse, raising D(L) above zero and giving the
                # ablation a non-trivial baseline.
                "c c g i c x",

                # ---- Strings designed for configuration overlap ----
                # The same configuration set { RR, RR\RR, S\RR } (after
                # inferring x ~ S\RR) licenses multiple of these.
                "i c x i c x",
                "i x i x",
            ],
        )
