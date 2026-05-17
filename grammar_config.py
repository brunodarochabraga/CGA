from dataclasses import dataclass, field
from typing import Dict, List, Set, Type, ClassVar, Optional, Callable
from category import Category

# --------------------------------------------------
# Base GrammarConfig (abstract)
# --------------------------------------------------

@dataclass
class GrammarConfig:
    name: str
    lexicon: Dict[str, List[Category]]
    rule_priorities: Dict[str, int]
    coordinable_categories: Set[str]
    sentences: List[str]
    # Predicate that accepts/rejects full-span derivations.  None ⇒ the
    # parser falls back to its default (atomic S).
    parse_target: Optional[Callable[[Category], bool]] = None

    # class-level registry (NOT a dataclass field)
    _registry: ClassVar[Dict[str, Type["GrammarConfig"]]] = {}

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        grammar_name = getattr(cls, "name", cls.__name__.lower())
        GrammarConfig._registry[grammar_name] = cls

    # --------------------------------------------------
    # MODIFIER METHODS
    # --------------------------------------------------

    def set_rule_priority(self, rule: str, value: int):
        """Change priority of a single rule."""
        self.rule_priorities[rule] = value
        return self

    def disable_rule(self, rule: str):
        """Disable a rule by setting negative priority."""
        self.rule_priorities[rule] = -1
        return self

    def enable_rule(self, rule: str, priority: int = 0):
        """Enable a rule with a given priority."""
        self.rule_priorities[rule] = priority
        return self

    def set_coordinable_categories(self, categories):
        """Replace coordinable categories."""
        self.coordinable_categories = set(categories)
        return self

    def add_coordinable_category(self, category: str):
        """Allow coordination for one more category."""
        self.coordinable_categories.add(category)
        return self

    def remove_coordinable_category(self, category: str):
        """Disallow coordination for a category."""
        self.coordinable_categories.discard(category)
        return self

    def set_sentences(self, sentences):
        """Replace test sentences."""
        self.sentences = list(sentences)
        return self

    def add_sentence(self, sentence: str):
        """Append one test sentence."""
        self.sentences.append(sentence)
        return self

    def remove_sentence(self, sentence: str):
        """Remove a sentence from the grammar if it exists."""
        try:
            self.sentences.remove(sentence)
        except ValueError:
            pass
        return self

    def add_lexeme(self, token: str, categories):
        """Add or extend a lexical entry."""
        self.lexicon[token] = list(categories)
        return self
    
    def remove_lexeme(self, token: str):
        del self.lexicon[token]
        return self
    
    def remove_lexeme_category(self, token: str, category: Category):
        if token in self.lexicon:
            self.lexicon[token] = [
                c for c in self.lexicon[token] if c != category
            ]
            if not self.lexicon[token]:
                del self.lexicon[token]
        return self

    def print_grammar(self):
        print(f"Grammar: {self.name}")
        
        print("  Lexicon:")
        for token, categories in self.lexicon.items():
            cats = " | ".join(str(c) for c in categories)
            print(f"   {token:<2} : {cats}")

        print("\n  Rule priorities:")
        for rule, prio in sorted(self.rule_priorities.items()):
            status = "DISABLED" if prio < 0 else prio
            print(f"   {rule:<6} : {status}")

        print("\n  Coordinable categories:")
        print(f"   {sorted(self.coordinable_categories)}")

# --------------------------------------------------
# Factory
# --------------------------------------------------

def get_grammar_config(name: str) -> GrammarConfig:
    try:
        return GrammarConfig._registry[name]()
    except KeyError:
        raise ValueError(
            f"Unknown grammar '{name}'. "
            f"Available grammars: {list(GrammarConfig._registry.keys())}"
        )
