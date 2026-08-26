from __future__ import annotations

import pytest

from quarry.errors import Frozen, Invalid, Missing
from quarry.schema import Field, Schema
from quarry.tokenize import Analyzer


def article_schema() -> Schema:
    schema = Schema()
    schema.add_text("title")
    schema.add_text("body", analyzer=Analyzer(stemming=False))
    schema.add_keyword("author")
    schema.add_numeric("year")
    schema.add_stored("thumbnail")
    return schema


class TestDeclarations:
    def test_text_fields_carry_their_analyzer(self):
        schema = article_schema()
        assert schema.get("title").analyzer is not None
        assert schema.get("body").analyzer.stemming is False

    def test_a_text_field_without_an_analyzer_is_refused_at_field_level(self):
        with pytest.raises(Invalid, match="same one"):
            Field(name="t", kind="text", analyzer=None)

    def test_only_text_fields_analyze(self):
        with pytest.raises(Invalid, match="category error"):
            Field(name="k", kind="keyword", analyzer=Analyzer())

    def test_unknown_kinds_list_the_choices(self):
        with pytest.raises(Invalid, match="the choices"):
            Field(name="x", kind="fancy")

    def test_double_declaration_is_refused(self):
        schema = article_schema()
        with pytest.raises(Invalid):
            schema.add_keyword("author")

    def test_stored_fields_are_not_searchable(self):
        schema = article_schema()
        assert not schema.get("thumbnail").searchable()
        assert schema.get("year").searchable()


class TestTheSeal:
    def test_sealed_schemas_refuse_growth_with_the_reason(self):
        schema = article_schema()
        schema.seal()
        with pytest.raises(Frozen, match="two vocabularies"):
            schema.add_keyword("tag")

    def test_an_empty_schema_cannot_seal(self):
        with pytest.raises(Invalid):
            Schema().seal()

    def test_missing_fields_name_the_declared_ones(self):
        with pytest.raises(Missing, match="author"):
            article_schema().get("ghost")


class TestIdentity:
    def test_the_identity_freezes_every_choice(self):
        identity = article_schema().identity()
        assert "body:text:lower=1|stop=1|stem=0" in identity
        assert "author:keyword:none" in identity

    def test_same_declarations_same_identity(self):
        assert article_schema().identity() == article_schema().identity()
