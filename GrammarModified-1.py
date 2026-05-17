"""
GrammarModified-1.py
====================
Variant of the template grammar with a distinct registry name.
Edit the rule priorities, lexicon, coordinable categories, or
sentences below to define an experimental grammar variant.
"""

from category import Category
from grammar_config import GrammarConfig


class GrammarModifiedV1(GrammarConfig):
    name = "modified-1"

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
                "i' c g' i i g",
                "i i g i c i g",
                "i c c g i' c g'",
            ],
        )
