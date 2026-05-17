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
                "i c x i i g",
                "i i g i c i g",
                "c c g i c x",
            ],
        )
