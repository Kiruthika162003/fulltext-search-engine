from __future__ import annotations

import pytest

from quarry.errors import Invalid
from quarry.schema import Schema
from quarry.schemamigrate import migrate_documents, plan_migration


def old_schema() -> Schema:
    schema = Schema()
    schema.add_text("body")
    schema.add_text("author")
    schema.add_numeric("year")
    schema.seal()
    return schema


def new_schema() -> Schema:
    schema = Schema()
    schema.add_text("body")
    schema.add_text("writer")
    schema.add_keyword("year")
    schema.add_numeric("pages")
    schema.seal()
    return schema


class TestPlanning:
    def test_identical_schemas_have_nothing_to_do(self):
        plan = plan_migration(old_schema(), old_schema())
        assert plan.describe() == (
            "schemas are identical; nothing to migrate"
        )
        assert plan.free()

    def test_every_change_is_classified(self):
        plan = plan_migration(
            old_schema(),
            new_schema(),
            renames={"author": "writer"},
        )
        actions = {
            step.field_name: step.action for step in plan.steps
        }
        assert actions["author"] == "rename"
        assert actions["year"] == "rebuild"
        assert actions["pages"] == "add"

    def test_undeclared_renames_become_drops_and_adds(self):
        plan = plan_migration(old_schema(), new_schema())
        actions = {
            step.field_name: step.action for step in plan.steps
        }
        assert actions["author"] == "drop"
        assert actions["writer"] == "add"
        assert plan.losses == ("author",)

    def test_rename_sources_must_exist(self):
        with pytest.raises(Invalid, match="not in the old schema"):
            plan_migration(
                old_schema(),
                new_schema(),
                renames={"ghost": "writer"},
            )

    def test_kind_changing_renames_need_two_migrations(self):
        schema = Schema()
        schema.add_keyword("author_tag")
        schema.add_text("body")
        schema.add_numeric("year")
        schema.seal()
        with pytest.raises(Invalid, match="two migrations"):
            plan_migration(
                old_schema(),
                schema,
                renames={"author": "author_tag"},
            )

    def test_the_plan_shouts_loss(self):
        plan = plan_migration(old_schema(), new_schema())
        assert "DATA LOSS: this drops author" in plan.describe()


def docs() -> list[dict[str, object]]:
    return [
        {"body": "a quiet cove", "author": "finch", "year": 1998},
        {"body": "the long walk", "author": "wren", "year": 2004},
    ]


class TestMigratingDocuments:

    def test_unacknowledged_loss_refuses_to_run(self):
        plan = plan_migration(old_schema(), new_schema())
        with pytest.raises(Invalid, match="nobody acknowledged"):
            migrate_documents(plan, docs())

    def test_acknowledged_loss_drops_the_field(self):
        plan = plan_migration(old_schema(), new_schema())
        moved = migrate_documents(
            plan, docs(), acknowledge_loss=True
        )
        assert moved[0] == {"body": "a quiet cove", "year": 1998}

    def test_declared_renames_carry_the_data(self):
        renames = {"author": "writer"}
        plan = plan_migration(
            old_schema(), new_schema(), renames=renames
        )
        moved = migrate_documents(plan, docs(), renames=renames)
        assert moved[1]["writer"] == "wren"
        assert "author" not in moved[1]

    def test_a_free_plan_is_only_additions(self):
        wider = Schema()
        wider.add_text("body")
        wider.add_text("author")
        wider.add_numeric("year")
        wider.add_stored("cover")
        wider.seal()
        plan = plan_migration(old_schema(), wider)
        assert plan.free()
        moved = migrate_documents(plan, docs())
        assert moved == docs()
