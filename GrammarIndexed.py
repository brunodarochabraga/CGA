"""
GrammarIndexed.py
=================

Grammar with indexed atomic categories (extension of GrammarTemplate).

Lexicon
-------
    {i}      ├ RR
    {c}      ├ RR \\ RR
    {g[t]}   ├ (S[t] \\ S[t-1]) \\ RR

The entry for `g` is a *scheme*: it has one free index variable, `t`.
When the parser encounters a surface token  g[α]  for any expression α,
the scheme variable is substituted by α and offsets are propagated.

    g[t-1]  ->  (S[t-1] \\ S[t-2]) \\ RR
    g[t]    ->  (S[t]   \\ S[t-1]) \\ RR
    g[t+1]  ->  (S[t+1] \\ S[t]  ) \\ RR

Coordination rule
-----------------
    RR , RR  ⇒  RR
(declared via `coordinable_categories = {"RR", "S"}`).

Test sentence
-------------
    "i c g[t-1] i i g[t]"

The derivation reaches  S[t] \\ S[t-2] :  a *temporal transition* from
state at t-2 to state at t, obtained by composing  S[t-1]\\S[t-2]  (built
from "i c g[t-1]") with  S[t]\\S[t-1]  (built from "i i g[t]")  via the
backward composition rule BC  (Y\\Z  X\\Y  ⇒  X\\Z).

Because the result is not atomic, we override `parse_target` to accept
any full-span derivation whose innermost head is S; this captures both
plain S[α] sentences and S-headed transition categories.
"""

from category import Category, parse_category
from grammar_config import GrammarConfig


def _s_headed(cat: Category) -> bool:
    """Accept categories whose innermost result is 'S' (regardless of
    indices or argument structure):  S, S[t], S[t]\\S[t-2], S[t]/NP, ..."""
    return cat.head_name() == "S"


class GrammarIndexed(GrammarConfig):
    name = "indexed"

    def __init__(self):
        RR = Category("RR")

        super().__init__(
            name=self.name,

            rule_priorities={
                "FA":   1,  "BA":   1,
                "FC":   2,  "BC":   2,
                "FS":   4,  "BS":   4,
                "FXS":  6,  "BXS":  6,
                "COORD": 8,
                "FTR":  -9, "BTR":  -9,  # type raising disabled
            },

            lexicon={
                "i": [RR],
                "c": [parse_category(r"RR\RR")],
                # Single-parameter scheme: variable `t` will be substituted
                # at parse time when the surface token carries an index.
                "g": [parse_category(r"(S[t]\S[t-1])\RR")],
            },

            coordinable_categories={"RR", "S"},

            sentences=[
                "i c g[t-1] i i g[t]",
            ],

            parse_target=_s_headed,
        )
