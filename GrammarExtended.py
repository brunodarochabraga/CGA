"""
GrammarExtended.py
==================

Extension of GrammarTemplate to a two-track lexicon in which an
unprimed and a primed "run" coexist and can be joined by a single
bridging operator.

Lexicon
-------
    i  ├ RR
    i' ├ RR'
    c  ├ RR  \\ RR     |     RR' \\ RR'    (polymorphic: either track)
    g  ├ S' \\ RR                          (closes an RR run into S')
    g' ├ (S / S') \\ RR'                   (closes an RR' run into S/S')

Coordination rule
-----------------
    RR , RR  ⇒  RR
(declared via `coordinable_categories = {"RR"}`; only the unprimed RR
is coordinable, matching the rule given in the problem statement.)

Bridging
--------
The category of `g'` is the device that joins the two tracks: it
consumes an `RR'`-prefix on the left and yields a forward-looking
functor `S/S'` that, when supplied with a complete `S'`-sentence on
the right, returns an atomic `S`.

Target sentence
---------------
    "i' c g' i i g"

Hand derivation
---------------
    i'       : RR'
    c        : RR'\\RR'
    g'       : (S/S')\\RR'
    i        : RR
    i        : RR
    g        : S'\\RR

       i' c              -> RR'                           (BA)
       (i' c) g'         -> S/S'                          (BA)
       i i               -> RR                            (COORD: RR,RR=>RR)
       (i i) g           -> S'                            (BA)
       [i' c g'] [i i g] -> S                             (FA: S/S', S' => S)

Because the final category is atomic S, no `parse_target` override is
needed: the parser's default acceptance criterion (atomic with head
"S") suffices.
"""

from category import Category
from grammar_config import GrammarConfig


class GrammarExtended(GrammarConfig):
    name = "extended"

    def __init__(self):
        # Atomic categories.  Prime is embedded in the atom *name*; the
        # dataclass treats it as an opaque string label, so equality
        # (RR == RR, RR' == RR', RR != RR') falls out automatically.
        RR  = Category("RR")
        RRp = Category("RR'")
        S   = Category("S")
        Sp  = Category("S'")

        # Convenience constructors -----------------------------------------
        # c has two entries (polymorphic across tracks).
        c_unprimed = Category("RR",  "\\", RR)    # RR\RR
        c_primed   = Category("RR'", "\\", RRp)   # RR'\RR'

        # g  : S'\RR     (closes an unprimed run, yielding the primed
        # sentence atom S' — the type the bridge g' will consume on
        # the right).
        g_cat = Category("S'", "\\", RR)

        # g' : (S/S')\RR'
        # Build the inner functor S/S' first, then wrap it as the
        # result of a backward slash taking RR' on the right.
        s_over_sp = Category("S", "/", Sp)        # S/S'
        gp_cat    = Category(s_over_sp, "\\", RRp)

        super().__init__(
            name=self.name,

            rule_priorities={
                "FA":   1,  "BA":   1,
                "FC":   2,  "BC":   2,
                "FS":   4,  "BS":   4,
                "FXS":  6,  "BXS":  6,
                "COORD": 8,
                "FTR":  -9, "BTR":  -9,    # type-raising disabled
            },

            lexicon={
                "i":  [RR],
                "i'": [RRp],
                "c":  [c_unprimed, c_primed],
                "g":  [g_cat],
                "g'": [gp_cat],
            },

            # Only RR is coordinable, exactly as stated in the
            # problem: "RR, RR => RR".
            coordinable_categories={"RR"},

            sentences=[
                "i' c g' i i g",
            ],

            # parse_target left at None: the parser's default
            # (atomic, head 'S') accepts the final S.
        )
