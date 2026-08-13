"""
Entry point for ``python -m heretek_swarm.cli``.

Delegates to the canonical ``cli`` Click group imported from the parent
``cli.py`` module (loaded as ``heretek_swarm._cli_module`` by
``cli/__init__.py``).
"""

from heretek_swarm.cli import cli

if __name__ == "__main__":
    cli()
