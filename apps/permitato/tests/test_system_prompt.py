"""Tests for Permitato system prompt construction."""

from __future__ import annotations


PROMPT_KWARGS = dict(
    current_mode="Work",
    mode_description="Social media, entertainment, news, and gaming blocked",
    exception_count=0,
    active_exceptions=[],
)


def test_prompt_without_context_has_no_recent_section():
    from apps.permitato.system_prompt import build_system_prompt

    prompt = build_system_prompt(**PROMPT_KWARGS)
    assert "## Recent Activity" not in prompt


def test_prompt_with_context_includes_section():
    from apps.permitato.system_prompt import build_system_prompt

    context = "- 15 min ago: denied unblock for twitter.com\nNote: twitter.com appears 2 times in recent activity."
    prompt = build_system_prompt(**PROMPT_KWARGS, recent_context=context)
    assert "## Recent Activity" in prompt
    assert "twitter.com" in prompt
    assert "calibrate" in prompt.lower() or "pattern" in prompt.lower()


def test_prompt_sections_in_correct_order():
    from apps.permitato.system_prompt import build_system_prompt

    context = "- 10 min ago: denied unblock for reddit.com"
    prompt = build_system_prompt(**PROMPT_KWARGS, recent_context=context)

    state_pos = prompt.index("## Current State")
    recent_pos = prompt.index("## Recent Activity")
    modes_pos = prompt.index("## Available Modes")
    assert state_pos < recent_pos < modes_pos
