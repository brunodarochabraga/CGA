"""
grammar_loader.py
=================
Dynamically load a GrammarConfig subclass from a user-specified .py file.

Used by the driver scripts to accept a grammar file as a command-line
argument:

    python main_parser.py GrammarTemplate.py
    python main_inferencer.py GrammarIndexed.py

The loader imports the file as a module, scans its namespace for the
unique GrammarConfig subclass defined *in that file* (imported
subclasses are filtered out), and returns an instance.

The loader is independent of GrammarConfig._registry: even if two
grammar files share the same `name` attribute, the loader still
returns the class defined in the requested file.
"""

import importlib.util
import inspect
import os

from grammar_config import GrammarConfig


def load_grammar_from_file(path):
    """
    Import the .py file at `path` and return an instance of the
    GrammarConfig subclass defined inside it.

    Raises:
        FileNotFoundError: if the file does not exist.
        ImportError:       if the file cannot be imported.
        ValueError:        if the file contains zero or multiple
                           GrammarConfig subclasses.
    """
    if not os.path.isfile(path):
        raise FileNotFoundError(f"Grammar file not found: {path}")

    module_name = os.path.splitext(os.path.basename(path))[0]
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Could not load module spec from: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    # Keep only GrammarConfig subclasses *defined in this module*
    # (so an `from grammar_config import GrammarConfig` does not
    # show up as a candidate).
    subclasses = [
        cls for _, cls in inspect.getmembers(module, inspect.isclass)
        if issubclass(cls, GrammarConfig)
        and cls is not GrammarConfig
        and cls.__module__ == module.__name__
    ]

    if not subclasses:
        raise ValueError(
            f"No GrammarConfig subclass defined in {path}. "
            f"The file should contain exactly one class extending "
            f"GrammarConfig."
        )
    if len(subclasses) > 1:
        names = ", ".join(c.__name__ for c in subclasses)
        raise ValueError(
            f"Multiple GrammarConfig subclasses defined in {path}: "
            f"{names}. Each grammar file should define exactly one."
        )

    return subclasses[0]()
