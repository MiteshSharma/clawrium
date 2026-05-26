"""Unit tests for the provider-attachment data model (issue #501).

Covers normalization between the legacy list-of-strings shape and the
new list-of-objects shape, plus per-agent-type invariant validation.
"""

from __future__ import annotations

import pytest

from clawrium.core import provider_attachments as pa


class TestSupportsMultiProvider:
    def test_hermes_supports_multi(self):
        assert pa.supports_multi_provider("hermes") is True

    def test_singleton_agent_types(self):
        assert pa.supports_multi_provider("openclaw") is False
        assert pa.supports_multi_provider("zeroclaw") is False
        assert pa.supports_multi_provider(None) is False


class TestNormalizeHermes:
    def test_empty_list_returns_empty(self):
        assert pa.normalize([], "hermes") == []

    def test_non_list_returns_empty(self):
        assert pa.normalize(None, "hermes") == []
        assert pa.normalize("not-a-list", "hermes") == []
        assert pa.normalize({"name": "x"}, "hermes") == []

    def test_legacy_strings_migrate_first_as_primary(self):
        out = pa.normalize(["my-anth"], "hermes")
        assert out == [{"name": "my-anth", "role": "primary", "model": ""}]

    def test_legacy_strings_additional_have_empty_role(self):
        # Multi-string legacy shape only arises from hand-edited hosts.json.
        # First string becomes primary; the rest land with empty role and
        # will fail validate(), surfacing the bad state to the operator.
        out = pa.normalize(["a", "b"], "hermes")
        assert out[0] == {"name": "a", "role": "primary", "model": ""}
        assert out[1] == {"name": "b", "role": "", "model": ""}

    def test_object_shape_preserved(self):
        raw = [
            {"name": "anth", "role": "primary", "model": "claude-opus"},
            {"name": "dgx", "role": "compression", "model": "qwen"},
        ]
        assert pa.normalize(raw, "hermes") == raw

    def test_object_missing_fields_default_to_empty(self):
        raw = [{"name": "anth"}]
        out = pa.normalize(raw, "hermes")
        assert out == [{"name": "anth", "role": "", "model": ""}]

    def test_object_without_name_dropped(self):
        raw = [{"role": "primary"}, {"name": "ok", "role": "primary"}]
        out = pa.normalize(raw, "hermes")
        assert out == [{"name": "ok", "role": "primary", "model": ""}]


class TestNormalizeSingleton:
    def test_strings_passthrough(self):
        assert pa.normalize(["p1"], "openclaw") == ["p1"]
        assert pa.normalize(["p1"], "zeroclaw") == ["p1"]

    def test_objects_downgrade_to_names(self):
        raw = [{"name": "p1", "role": "primary", "model": "x"}]
        assert pa.normalize(raw, "openclaw") == ["p1"]

    def test_non_list_returns_empty(self):
        assert pa.normalize(None, "openclaw") == []


class TestValidateHermes:
    def test_empty_ok(self):
        pa.validate([], "hermes")

    def test_exactly_one_primary_ok(self):
        pa.validate(
            [{"name": "a", "role": "primary", "model": ""}],
            "hermes",
        )

    def test_primary_plus_auxiliary_ok(self):
        pa.validate(
            [
                {"name": "a", "role": "primary", "model": ""},
                {"name": "b", "role": "compression", "model": ""},
                {"name": "c", "role": "vision", "model": ""},
            ],
            "hermes",
        )

    def test_missing_primary_rejected(self):
        with pytest.raises(pa.AttachmentError, match="exactly one primary"):
            pa.validate(
                [{"name": "a", "role": "compression", "model": ""}],
                "hermes",
            )

    def test_two_primaries_rejected(self):
        with pytest.raises(pa.AttachmentError, match="exactly one primary"):
            pa.validate(
                [
                    {"name": "a", "role": "primary", "model": ""},
                    {"name": "b", "role": "primary", "model": ""},
                ],
                "hermes",
            )

    def test_duplicate_auxiliary_slot_rejected(self):
        with pytest.raises(pa.AttachmentError, match="already filled"):
            pa.validate(
                [
                    {"name": "a", "role": "primary", "model": ""},
                    {"name": "b", "role": "compression", "model": ""},
                    {"name": "c", "role": "compression", "model": ""},
                ],
                "hermes",
            )

    def test_invalid_role_rejected(self):
        with pytest.raises(pa.AttachmentError, match="invalid role"):
            pa.validate(
                [{"name": "a", "role": "bogus", "model": ""}],
                "hermes",
            )

    def test_empty_role_rejected(self):
        with pytest.raises(pa.AttachmentError, match="invalid role"):
            pa.validate(
                [{"name": "a", "role": "", "model": ""}],
                "hermes",
            )

    def test_empty_name_rejected(self):
        with pytest.raises(pa.AttachmentError, match="non-empty 'name'"):
            pa.validate(
                [{"name": "", "role": "primary", "model": ""}],
                "hermes",
            )

    def test_non_dict_entry_rejected(self):
        with pytest.raises(pa.AttachmentError, match="must be an object"):
            pa.validate(["just-a-string"], "hermes")


class TestValidateSingleton:
    def test_empty_ok(self):
        pa.validate([], "openclaw")

    def test_one_attachment_ok(self):
        pa.validate(["p1"], "openclaw")

    def test_two_attachments_rejected(self):
        with pytest.raises(pa.AttachmentError, match="single-provider invariant"):
            pa.validate(["a", "b"], "zeroclaw")


class TestPrimaryAccessors:
    def test_get_primary_returns_entry(self):
        items = [
            {"name": "a", "role": "primary", "model": "m"},
            {"name": "b", "role": "compression", "model": ""},
        ]
        assert pa.get_primary(items) == items[0]

    def test_get_primary_none_when_absent(self):
        assert pa.get_primary([]) is None
        assert pa.get_primary([{"name": "x", "role": "compression"}]) is None

    def test_get_auxiliary_returns_non_primary(self):
        items = [
            {"name": "a", "role": "primary", "model": ""},
            {"name": "b", "role": "compression", "model": ""},
            {"name": "c", "role": "vision", "model": ""},
        ]
        aux = pa.get_auxiliary(items)
        assert [e["name"] for e in aux] == ["b", "c"]

    def test_get_auxiliary_skips_empty_role(self):
        items = [{"name": "x", "role": "", "model": ""}]
        assert pa.get_auxiliary(items) == []


class TestSlotEnumeration:
    def test_nine_upstream_slots(self):
        # Locked against hermes v2026.5.7 hermes_cli/config.py:716-794.
        # If upstream adds a slot, this test should fail loudly so the
        # contract is re-verified explicitly.
        assert len(pa.AUXILIARY_SLOTS) == 9
        assert "compression" in pa.AUXILIARY_SLOTS
        assert "title_generation" in pa.AUXILIARY_SLOTS
        assert "curator" in pa.AUXILIARY_SLOTS

    def test_valid_roles_includes_primary_and_all_slots(self):
        assert pa.PRIMARY_ROLE in pa.VALID_ROLES
        for slot in pa.AUXILIARY_SLOTS:
            assert slot in pa.VALID_ROLES
        assert len(pa.VALID_ROLES) == 10
