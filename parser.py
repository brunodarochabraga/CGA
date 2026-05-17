import re
from dataclasses import dataclass
from typing import List, Union, Callable, Optional

from category import Category, parse_index

# --------------------------------------------------
# UTIL
# --------------------------------------------------

def ensure_category(x):
    """Guarantee that a value is a Category object."""
    return x if isinstance(x, Category) else Category(x)


# --------------------------------------------------
# DERIVATION STEP
# --------------------------------------------------

@dataclass
class Step:
    rule: str
    inputs: List[Union[str, Category]]
    output: Category

    def __str__(self):
        ins = " , ".join(str(x) for x in self.inputs)
        return f"{self.rule:<5}: {ins} ⇒ {self.output}"


# --------------------------------------------------
# PARSE ITEM
# --------------------------------------------------

@dataclass
class Item:
    category: Category
    steps: List[Step]


# --------------------------------------------------
# BASIC COMBINATORS (unchanged from original)
# --------------------------------------------------

def FA(l, r):
    # X/Y  Y  ⇒  X
    if l.category.slash == "/" and l.category.argument == r.category:
        X = ensure_category(l.category.result)
        return Item(X, l.steps + r.steps + [Step("FA", [l.category, r.category], X)])
    return None


def BA(l, r):
    # Y  X\Y  ⇒  X
    if r.category.slash == "\\" and r.category.argument == l.category:
        X = ensure_category(r.category.result)
        return Item(X, l.steps + r.steps + [Step("BA", [l.category, r.category], X)])
    return None


def FC(l, r):
    # X/Y  Y/Z  ⇒  X/Z
    if (
        l.category.slash == "/"
        and r.category.slash == "/"
        and l.category.argument == r.category.result
    ):
        XZ = Category(ensure_category(l.category.result), "/", r.category.argument)
        return Item(XZ, l.steps + r.steps + [Step("FC", [l.category, r.category], XZ)])
    return None


def BC(l, r):
    # Y\Z  X\Y  ⇒  X\Z
    if (
        l.category.slash == "\\"
        and r.category.slash == "\\"
        and r.category.argument == l.category.result
    ):
        XZ = Category(ensure_category(r.category.result), "\\", l.category.argument)
        return Item(XZ, l.steps + r.steps + [Step("BC", [l.category, r.category], XZ)])
    return None


def FS(l, r):
    # X/(Y/Z)  Y/Z  ⇒  X/Z
    if (
        l.category.slash == "/"
        and not l.category.argument.is_atomic()
        and l.category.argument.slash == "/"
        and r.category.slash == "/"
        and l.category.argument.result == r.category.result
    ):
        XZ = Category(ensure_category(l.category.result), "/", r.category.argument)
        return Item(XZ, l.steps + r.steps + [Step("FS", [l.category, r.category], XZ)])
    return None


def BS(l, r):
    # Y\Z  (X\Y)\Z  ⇒  X\Z
    if (
        r.category.slash == "\\"
        and not r.category.argument.is_atomic()
        and r.category.argument.slash == "\\"
        and r.category.argument.result == l.category.result
    ):
        XZ = Category(ensure_category(r.category.result), "\\", l.category.argument)
        return Item(XZ, l.steps + r.steps + [Step("BS", [l.category, r.category], XZ)])
    return None


def FXS(l, r):
    # X\(Y/Z)  Y/Z  ⇒  X\Z
    if (
        l.category.slash == "\\"
        and not l.category.argument.is_atomic()
        and l.category.argument.slash == "/"
        and r.category.slash == "/"
        and l.category.argument.result == r.category.result
    ):
        XZ = Category(ensure_category(l.category.result), "\\", r.category.argument)
        return Item(XZ, l.steps + r.steps + [Step("FXS", [l.category, r.category], XZ)])
    return None


def BXS(l, r):
    # Y\Z  X/(Y\Z)  ⇒  X/Z
    if (
        r.category.slash == "/"
        and not r.category.argument.is_atomic()
        and r.category.argument.slash == "\\"
        and r.category.argument.result == l.category.result
    ):
        XZ = Category(ensure_category(r.category.result), "/", l.category.argument)
        return Item(XZ, l.steps + r.steps + [Step("BXS", [l.category, r.category], XZ)])
    return None


# --------------------------------------------------
# STRUCTURAL COORDINATION
# --------------------------------------------------

def COORD(l, r, coordinable_categories):
    if (
        l.category.is_atomic()
        and r.category.is_atomic()
        and l.category == r.category
        and l.category.result in coordinable_categories
    ):
        X = l.category
        return Item(X, l.steps + r.steps + [Step("COORD", [l.category, r.category, coordinable_categories], X)])
    return None


# --------------------------------------------------
# TYPE RAISING
# --------------------------------------------------

def type_raise(item, targets, rule_priorities):
    if not item.category.is_atomic():
        return []

    raised = []
    for T in targets:
        if rule_priorities.get("FTR", float("inf")) >= 0:
            ftr = Category(T, "/", Category(T, "\\", item.category))
            raised.append(Item(ftr, item.steps + [Step("FTR", [item.category], ftr)]))

        if rule_priorities.get("BTR", float("inf")) >= 0:
            btr = Category(T, "\\", Category(T, "/", item.category))
            raised.append(Item(btr, item.steps + [Step("BTR", [item.category], btr)]))

    return raised


# --------------------------------------------------
# INDEXED LEXICAL LOOKUP   (NEW)
# --------------------------------------------------
# An input token of the form  word[index_expr]  is split into the bare
# word and an Index value.  The bare word is looked up in the lexicon to
# retrieve a scheme (a Category that may contain a single index
# variable).  The scheme is then instantiated by substituting its
# variable with the input expression.

_INDEXED_TOKEN_RE = re.compile(r"^([A-Za-z_][A-Za-z_0-9]*)\[([^\]]+)\]$")


def strip_index(token: str):
    """
    Split a surface token into (bare_word, index_expression).

    'g[t-1]'  ->  ('g', ('t', -1))
    'g[t]'    ->  ('g', ('t',  0))
    'i'       ->  ('i', None)
    """
    m = _INDEXED_TOKEN_RE.match(token)
    if m:
        return m.group(1), parse_index(m.group(2))
    return token, None


def instantiate_scheme(scheme: Category, input_idx) -> Category:
    """
    Instantiate a lexical scheme by substituting its (single) index
    variable with the input's index expression.

    If the input is unindexed (None), the scheme is returned as-is.
    If the scheme contains no index variable, the scheme is returned
    as-is.
    If the scheme contains more than one index variable, an error is
    raised (single-parameter schemes are assumed throughout).
    """
    if input_idx is None:
        return scheme
    free = scheme.free_variables()
    if not free:
        return scheme
    if len(free) > 1:
        raise ValueError(
            f"Lexical scheme {scheme} has multiple variables {free}; "
            f"only single-parameter schemes are supported."
        )
    scheme_var = next(iter(free))
    new_var, shift = input_idx
    return scheme.substitute(scheme_var, new_var, shift)


# --------------------------------------------------
# CKY PARSER
# --------------------------------------------------

class CCGParser:
    def __init__(self, lexicon, rule_priorities, coordinable_categories,
                 parse_target: Optional[Callable[[Category], bool]] = None):
        self.lexicon = lexicon
        self.rule_priorities = rule_priorities
        self.type_raise_targets = [Category("S")]
        self.coordinable_categories = coordinable_categories

        # Default acceptance criterion: atomic category whose result is "S".
        # (Atomic indexed categories like S[t] are accepted; complex S-headed
        # categories like S[t]\S[t-2] are not, unless a grammar overrides this.)
        self.parse_target = parse_target or (
            lambda c: c.is_atomic() and str(c.result) == "S"
        )

        all_rules: List[Callable] = [
            FA, BA, FC, BC, FS, BS, FXS, BXS  # , COORD
        ]

        self.rules = [
            r for r in all_rules
            if self.rule_priorities.get(r.__name__, float("inf")) >= 0
        ]

        self.rules.sort(key=lambda r: self.rule_priorities.get(r.__name__, float("inf")))

    def parse(self, words, target_filter: Optional[Callable[[Category], bool]] = None):
        if target_filter is None:
            target_filter = self.parse_target

        n = len(words)
        chart = [[[] for _ in range(n + 1)] for _ in range(n)]

        # ----- Lexical look-up with index instantiation -----
        for i, w in enumerate(words):
            bare, idx = strip_index(w)
            for scheme in self.lexicon.get(bare, []):
                cat = instantiate_scheme(scheme, idx)
                base = Item(cat, [Step("LEX", [w], cat)])
                chart[i][i + 1].append(base)
                chart[i][i + 1].extend(
                    type_raise(base, self.type_raise_targets, self.rule_priorities)
                )

        # ----- CKY -----
        for span in range(2, n + 1):
            for i in range(n - span + 1):
                j = i + span
                for k in range(i + 1, j):
                    for l in chart[i][k]:
                        for r in chart[k][j]:
                            for rule in self.rules:
                                res = rule(l, r)
                                if res:
                                    chart[i][j].append(res)
                                    chart[i][j].extend(
                                        type_raise(res, self.type_raise_targets, self.rule_priorities)
                                    )
                            coord = COORD(l, r, self.coordinable_categories)  # 3-arg combinator
                            if coord:
                                chart[i][j].append(coord)

        return [
            it.steps
            for it in chart[0][n]
            if target_filter(it.category)
        ]
