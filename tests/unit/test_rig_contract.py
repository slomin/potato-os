"""Contract tests for the RIG step envelope validation."""

import pytest


# ---------------------------------------------------------------------------
# Envelope validation tests
# ---------------------------------------------------------------------------


def _valid_envelope(**overrides):
    base = {
        "step_id": "check_status",
        "type": "ts",
        "result": {"ok": True},
        "next": {"mode": "direct", "step_id": "apply_mode", "args": {}},
    }
    base.update(overrides)
    return base


def test_valid_envelope_passes():
    from core.rig_envelope import validate_envelope

    assert validate_envelope(_valid_envelope()) == []


def test_valid_envelope_terminal_step():
    from core.rig_envelope import validate_envelope

    assert validate_envelope(_valid_envelope(next=None)) == []


@pytest.mark.parametrize("field", ["step_id", "type", "result", "next"])
def test_envelope_missing_required_field(field):
    from core.rig_envelope import validate_envelope

    env = _valid_envelope()
    del env[field]
    errors = validate_envelope(env)
    assert any(field in e for e in errors), f"Expected error mentioning '{field}'"


def test_envelope_invalid_type():
    from core.rig_envelope import validate_envelope

    errors = validate_envelope(_valid_envelope(type="unknown"))
    assert any("type" in e for e in errors)


def test_envelope_result_must_be_dict():
    from core.rig_envelope import validate_envelope

    errors = validate_envelope(_valid_envelope(result="not a dict"))
    assert any("result" in e for e in errors)


def test_envelope_next_direct_requires_step_id():
    from core.rig_envelope import validate_envelope

    errors = validate_envelope(_valid_envelope(next={"mode": "direct", "args": {}}))
    assert any("step_id" in e for e in errors)


def test_envelope_next_model_requires_prompt_id():
    from core.rig_envelope import validate_envelope

    errors = validate_envelope(_valid_envelope(next={"mode": "model", "inputs": {}}))
    assert any("prompt_id" in e for e in errors)


def test_envelope_next_invalid_mode():
    from core.rig_envelope import validate_envelope

    errors = validate_envelope(_valid_envelope(next={"mode": "bogus"}))
    assert any("mode" in e for e in errors)


def test_envelope_unhashable_type_returns_error():
    from core.rig_envelope import validate_envelope

    errors = validate_envelope(_valid_envelope(type=["not", "a", "string"]))
    assert any("type" in e for e in errors)


def test_envelope_unhashable_next_mode_returns_error():
    from core.rig_envelope import validate_envelope

    errors = validate_envelope(_valid_envelope(next={"mode": {"nested": True}}))
    assert any("mode" in e for e in errors)
