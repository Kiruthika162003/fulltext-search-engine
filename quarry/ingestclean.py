"""Ingest cleaning: the text is scrubbed before the analyzer sees it.

Real feeds arrive dirty: markup fragments from a CMS, control
characters from a bad export, soft hyphens invisible to eyes
and fatal to term matching, and whitespace in every flavor
Unicode sells. Cleaning is a pipeline of named stages, each
narrow enough to reason about: markup strips tags but keeps
their inner text since the words were the point, control
characters drop except the whitespace family, soft hyphens and
zero-width characters vanish because they split words
invisibly, and whitespace collapses last so the earlier stages
can be sloppy about what they leave behind. The report counts
what each stage changed on this corpus, which is how a feed
that suddenly ships doubled markup gets noticed the week it
happens, and cleaning is idempotent by test, clean of clean is
clean, because a scrubber that keeps finding dirt in its own
output is manufacturing it.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from quarry.errors import Invalid

TAG = re.compile(r"<[^>]{1,200}>")
CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
INVISIBLES = re.compile("[­\u200b‌‍﻿]")
WHITESPACE = re.compile(r"\s+")


@dataclass
class CleanLedger:
    counts: dict[str, int] = field(default_factory=dict)
    documents: int = 0

    def _note(self, stage: str, changed: bool) -> None:
        if changed:
            self.counts[stage] = self.counts.get(stage, 0) + 1

    def clean(self, text: str) -> str:
        if text is None:
            raise Invalid("None is not text; the feed sent a hole")
        self.documents += 1
        after_markup = TAG.sub(" ", text)
        self._note("markup", after_markup != text)
        after_control = CONTROL.sub("", after_markup)
        self._note("control", after_control != after_markup)
        after_invisible = INVISIBLES.sub("", after_control)
        self._note("invisibles", after_invisible != after_control)
        collapsed = WHITESPACE.sub(" ", after_invisible).strip()
        self._note("whitespace", collapsed != after_invisible)
        return collapsed

    def report(self) -> str:
        if self.documents == 0:
            return "nothing cleaned yet"
        lines = [f"{self.documents} document(s) cleaned"]
        for stage in ("markup", "control", "invisibles", "whitespace"):
            count = self.counts.get(stage, 0)
            share = count / self.documents
            lines.append(
                f"  {stage}: touched {count} ({share:.0%})"
            )
        markup_share = self.counts.get("markup", 0) / self.documents
        if markup_share > 0.5:
            lines.append(
                "over half the feed carries markup; the exporter "
                "changed, go look at it"
            )
        return "\n".join(lines)


def is_idempotent(ledger: CleanLedger, text: str) -> bool:
    once = ledger.clean(text)
    twice = ledger.clean(once)
    return once == twice
