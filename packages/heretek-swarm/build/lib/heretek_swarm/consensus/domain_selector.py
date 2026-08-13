"""
Domain-based agent selection for consensus.

Selects agents whose topics overlap with a question's keywords.
No LLM calls — deterministic keyword scoring, <100ms typical.
Falls back to triad + arbiter (alpha, beta, charlie, arbiter)
when fewer than min_votes agents match.
"""

import json
import logging
import os
import re
from pathlib import Path

import structlog

logger = structlog.get_logger(__name__)

logger = logging.getLogger("domain_selector")

# Default fallback agents when topic matching yields too few results
DEFAULT_FALLBACK_AGENTS = ["alpha", "beta", "charlie", "arbiter"]

# Characters directory — relative to this file's package root
_CHARACTERS_DIR = os.path.join(  # noqa: PTH118
    os.path.dirname(os.path.dirname(__file__)),  # noqa: PTH120
    "runtime",
    "characters",
)


class DomainSelector:
    """Selects agents by keyword overlap between question and agent topics."""

    def __init__(
        self,
        characters_dir: str | None = None,
        default_top_n: int = 6,
        min_votes: int = 4,
        fallback_agents: list[str] | None = None,
    ) -> None:
        self.characters_dir = characters_dir or _CHARACTERS_DIR
        self.default_top_n = default_top_n
        self.min_votes = min_votes
        self.fallback_agents = fallback_agents or list(DEFAULT_FALLBACK_AGENTS)
        self._agents: dict[str, list[str]] = {}
        self._load_characters()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def score_agents(
        self,
        question: str,
        top_n: int | None = None,
    ) -> list[str]:
        """
        Score all agents by keyword overlap with *question* and return
        the top *top_n* agent ids (default ``self.default_top_n``).

        Falls back to ``self.fallback_agents`` when fewer than
        ``self.min_votes`` agents match.
        """
        if top_n is None:
            top_n = self.default_top_n

        tokens = self._tokenize(question)
        if not tokens:
            logger.info("Empty question after tokenization — using fallback")
            return list(self.fallback_agents)

        token_set = set(tokens)
        scores: dict[str, int] = {}

        for agent_id, topics in self._agents.items():
            topic_words = set()
            for topic in topics:
                topic_words.update(self._tokenize(topic))
            overlap = len(token_set & topic_words)
            if overlap > 0:
                scores[agent_id] = overlap

        if not scores:
            logger.info("No agents matched question keywords — using fallback")
            return list(self.fallback_agents)

        ranked = sorted(scores, key=lambda a: scores[a], reverse=True)

        # Ensure at least min_votes agents in the result
        if len(ranked) < self.min_votes:
            for fb in self.fallback_agents:
                if fb not in ranked:
                    ranked.append(fb)
                if len(ranked) >= self.min_votes:
                    break

        selected = ranked[:top_n]
        logger.debug("Selected agents: %s", selected)
        return selected

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _load_characters(self) -> None:
        """Load all character JSON files from the characters directory."""
        char_dir = Path(self.characters_dir)
        if not char_dir.is_dir():
            logger.warning("Characters directory not found: %s", char_dir)
            return

        for path in sorted(char_dir.glob("*.json")):
            agent_id = path.stem
            try:
                with open(path, encoding="utf-8") as fh:  # noqa: PTH123
                    data = json.load(fh)
            except (json.JSONDecodeError, OSError) as exc:
                logger.warning("Failed to load %s: %s", path.name, exc)
                continue

            topics = data.get("topics")
            if not topics:
                logger.info(
                    "Agent %s has no topics — excluded from domain matching",
                    agent_id,
                )
                continue

            self._agents[agent_id] = list(topics)

        logger.info(
            "Loaded %d agents with topics from %s",
            len(self._agents),
            char_dir,
        )

    @staticmethod
    def _tokenize(text: str) -> list[str]:
        """Lowercase-alphanumeric tokenization."""
        return re.findall(r"[a-z0-9]+", text.lower())
