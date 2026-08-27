"""Index diffing: two indexes, one report of what actually differs.

After a migration, before a cutover, during a slow afternoon of
doubt, the question is always the same: do these two indexes hold
the same corpus, and if not, exactly where do they part. The diff
compares by external id: documents present in one and absent in
the other, documents present in both whose stored fields disagree,
and the count that agrees, because a diff that only lists trouble
leaves the reader to infer the size of the agreement. Field
disagreements name the field and both values, truncated for the
report but never for the verdict, and the empty diff earns the
sentence operators actually want to read: the corpora agree,
document for document, field for field.
"""

from __future__ import annotations

from dataclasses import dataclass

from quarry.errors import Invalid
from quarry.writer import Index

SHOWN = 40


@dataclass(frozen=True)
class FieldDisagreement:
    external: int
    field_name: str
    left_value: str
    right_value: str


@dataclass(frozen=True)
class IndexDiff:
    only_left: tuple[int, ...]
    only_right: tuple[int, ...]
    disagreements: tuple[FieldDisagreement, ...]
    agreeing: int

    def clean(self) -> bool:
        return not (
            self.only_left or self.only_right or self.disagreements
        )

    def report(self) -> str:
        if self.clean():
            return (
                f"the corpora agree, document for document, field "
                f"for field ({self.agreeing} documents)"
            )
        lines = [f"{self.agreeing} documents agree; the differences:"]
        if self.only_left:
            lines.append(
                f"  only left: {', '.join(map(str, self.only_left))}"
            )
        if self.only_right:
            lines.append(
                f"  only right: {', '.join(map(str, self.only_right))}"
            )
        for row in self.disagreements:
            left_shown = row.left_value[:SHOWN]
            right_shown = row.right_value[:SHOWN]
            lines.append(
                f"  doc {row.external} field {row.field_name}: "
                f"{left_shown!r} vs {right_shown!r}"
            )
        return "\n".join(lines)


def _live_documents(index: Index) -> dict[int, dict[str, object]]:
    index.flush()
    held: dict[int, dict[str, object]] = {}
    for external, (segment_name, local) in index.locations.items():
        segment = next(
            row for row in index.segments if row.name == segment_name
        )
        if segment.is_live(local):
            held[external] = segment.stored[local]
    return held


def diff_indexes(left: Index, right: Index) -> IndexDiff:
    if left.schema.identity() != right.schema.identity():
        raise Invalid(
            "the indexes were written under different schemas; diff "
            "the schemas first, the corpora second"
        )
    left_docs = _live_documents(left)
    right_docs = _live_documents(right)
    only_left = tuple(
        sorted(set(left_docs) - set(right_docs))
    )
    only_right = tuple(
        sorted(set(right_docs) - set(left_docs))
    )
    disagreements = []
    agreeing = 0
    for external in sorted(set(left_docs) & set(right_docs)):
        left_doc = left_docs[external]
        right_doc = right_docs[external]
        fields = set(left_doc) | set(right_doc)
        document_agrees = True
        for field_name in sorted(fields):
            left_value = left_doc.get(field_name)
            right_value = right_doc.get(field_name)
            if left_value != right_value:
                document_agrees = False
                disagreements.append(
                    FieldDisagreement(
                        external=external,
                        field_name=field_name,
                        left_value=repr(left_value),
                        right_value=repr(right_value),
                    )
                )
        if document_agrees:
            agreeing += 1
    return IndexDiff(
        only_left=only_left,
        only_right=only_right,
        disagreements=tuple(disagreements),
        agreeing=agreeing,
    )
