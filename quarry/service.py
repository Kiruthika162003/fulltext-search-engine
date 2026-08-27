"""The service surface: dict in, dict out, and errors become envelopes.

Whatever transport carries requests, the shape at this boundary is
plain dictionaries, because every framework can produce one and
every test can assert on one. The handler maps operations to
engine calls, and its real job is the error taxonomy: an Invalid
becomes a 400-shaped envelope carrying the refusal verbatim, a
Missing becomes 404 with the name that was not found, and anything
else becomes 500 with an opaque reference instead of a stack
trace, because internal wreckage shown to callers is a security
brief and shown to attackers is a gift. Every response carries the
operation echoed back and a served-by stamp, since the first
question during an incident is which node answered, and responses
that cannot say are archaeology.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from quarry.engine import Engine
from quarry.errors import Invalid, Missing, QuarryError


@dataclass
class SearchService:
    engine: Engine
    node_name: str = "node-0"
    served: int = 0
    failures: dict[str, int] = field(default_factory=dict)

    def _envelope(
        self, operation: str, status: int, body: dict
    ) -> dict:
        return {
            "operation": operation,
            "status": status,
            "served_by": self.node_name,
            **body,
        }

    def handle(self, request: dict) -> dict:
        operation = request.get("operation")
        if not operation:
            return self._envelope(
                "unknown",
                400,
                {"error": "every request names its operation"},
            )
        self.served += 1
        try:
            if operation == "search":
                return self._search(request)
            if operation == "add":
                return self._add(request)
            if operation == "delete":
                return self._delete(request)
            if operation == "commit":
                self.engine.commit()
                return self._envelope(operation, 200, {"committed": True})
            return self._envelope(
                operation,
                400,
                {
                    "error": (
                        f"unknown operation {operation!r}; the "
                        f"choices are search, add, delete, commit"
                    )
                },
            )
        except Invalid as refused:
            self.failures["400"] = self.failures.get("400", 0) + 1
            return self._envelope(
                operation, 400, {"error": str(refused)}
            )
        except Missing as absent:
            self.failures["404"] = self.failures.get("404", 0) + 1
            return self._envelope(
                operation, 404, {"error": str(absent)}
            )
        except QuarryError:
            self.failures["500"] = self.failures.get("500", 0) + 1
            reference = f"ref-{self.served}"
            return self._envelope(
                operation,
                500,
                {
                    "error": (
                        f"internal error; quote {reference} to "
                        f"whoever answers the pager"
                    )
                },
            )

    def _search(self, request: dict) -> dict:
        text = request.get("query")
        if not text:
            raise Invalid("a search request carries a query")
        limit = int(request.get("limit", 10))
        response = self.engine.search(text, limit=limit)
        return self._envelope(
            "search",
            200,
            {
                "hits": [
                    {"id": hit.external, "score": hit.score}
                    for hit in response.hits
                ],
                "suggestion": response.suggestion,
            },
        )

    def _add(self, request: dict) -> dict:
        document = request.get("document")
        if not isinstance(document, dict) or not document:
            raise Invalid("an add request carries a document object")
        external = self.engine.add(document)
        return self._envelope("add", 201, {"id": external})

    def _delete(self, request: dict) -> dict:
        if "id" not in request:
            raise Invalid("a delete request names its id")
        outcome = self.engine.delete(int(request["id"]))
        return self._envelope("delete", 200, {"outcome": outcome})

    def traffic_note(self) -> str:
        breakdown = ", ".join(
            f"{status}: {count}"
            for status, count in sorted(self.failures.items())
        )
        return (
            f"{self.served} request(s) served by {self.node_name}"
            + (f"; failures {breakdown}" if self.failures else "")
        )
