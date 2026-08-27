"""Request tracing: one query's journey, reconstructed exactly.

When one search is slow the aggregate dashboards shrug, and the
trace answers for the individual: a root span for the request,
child spans for parse, retrieve, score, and render, each with
its own start and duration in the caller's clock, nesting
checked at the door so a child cannot start before its parent
or outlive it, because a trace whose arithmetic is impossible
poisons trust in every trace after it. Spans carry tags, small
named facts like segment counts and cache verdicts, and the
rendering indents children under parents with durations and
the share of the parent each child consumed, which makes the
slow stage visually undeniable. The gap line is the feature
dashboards cannot give: time inside the parent that no child
explains, named as such, because unexplained time is where the
next surprise lives.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from quarry.errors import Invalid


@dataclass
class Span:
    name: str
    start: int
    end: int | None = None
    tags: dict[str, str] = field(default_factory=dict)
    children: list[Span] = field(default_factory=list)

    def finish(self, end: int) -> None:
        if self.end is not None:
            raise Invalid(f"{self.name} already finished")
        if end < self.start:
            raise Invalid(
                f"{self.name} cannot end at {end} before its "
                f"start at {self.start}"
            )
        self.end = end

    def duration(self) -> int:
        if self.end is None:
            raise Invalid(f"{self.name} is still open")
        return self.end - self.start

    def tag(self, key: str, value: str) -> None:
        self.tags[key] = value

    def child(self, name: str, start: int) -> Span:
        if start < self.start:
            raise Invalid(
                f"{name} cannot start at {start} before its "
                f"parent {self.name} at {self.start}"
            )
        held = Span(name=name, start=start)
        self.children.append(held)
        return held

    def _check_closed(self) -> None:
        if self.end is None:
            raise Invalid(f"{self.name} is still open")
        for child in self.children:
            child._check_closed()
            if child.end > self.end:
                raise Invalid(
                    f"{child.name} outlives its parent "
                    f"{self.name}; that trace is impossible"
                )

    def unexplained(self) -> int:
        explained = sum(
            child.duration() for child in self.children
        )
        return self.duration() - explained

    def render(self, indent: int = 0) -> str:
        self._check_closed()
        pad = "  " * indent
        tagged = (
            " {" + ", ".join(
                f"{key}={value}"
                for key, value in sorted(self.tags.items())
            ) + "}"
            if self.tags
            else ""
        )
        lines = [
            f"{pad}{self.name}: {self.duration()}{tagged}"
        ]
        for child in self.children:
            share = (
                child.duration() / self.duration()
                if self.duration()
                else 0.0
            )
            block = child.render(indent + 1).splitlines()
            block[0] += f" ({share:.0%} of {self.name})"
            lines.extend(block)
        if self.children and self.unexplained() > 0:
            lines.append(
                f"{pad}  [unexplained: {self.unexplained()} "
                f"inside {self.name}; the next surprise lives "
                f"here]"
            )
        return "\n".join(lines)


def slowest_path(root: Span) -> list[str]:
    """Follow the fattest child down: the lane the latency took."""
    root._check_closed()
    path = [root.name]
    held = root
    while held.children:
        held = max(
            held.children,
            key=lambda child: (child.duration(), child.name),
        )
        path.append(held.name)
    return path
