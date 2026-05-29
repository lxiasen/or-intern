"""Unit tests for doom_loop detector."""

import pytest
from litellm import Message


def _make_assistant_msg(tool_calls=None):
    msg = Message(role="assistant", content="")
    if tool_calls:
        msg.tool_calls = []
        for tc in tool_calls:
            fn = type("Function", (), {
                "name": tc["name"],
                "arguments": tc.get("arguments", "{}"),
            })()
            tc_obj = type("ToolCall", (), {
                "id": tc.get("id", "tc_1"),
                "function": fn,
            })()
            msg.tool_calls.append(tc_obj)
    return msg


def _make_tool_msg(tool_call_id, content="result"):
    return Message(role="tool", content=content, tool_call_id=tool_call_id)


class TestNormalizeArgs:
    """Test argument normalization."""

    def test_empty_string(self):
        from agent.core.doom_loop import _normalize_args
        assert _normalize_args("") == ""

    def test_valid_json_normalized(self):
        from agent.core.doom_loop import _normalize_args
        result = _normalize_args('{"b": 2, "a": 1}')
        assert result == '{"a":1,"b":2}'

    def test_invalid_json_fallback(self):
        from agent.core.doom_loop import _normalize_args
        result = _normalize_args("not json")
        assert result == "not json"


class TestHashArgs:
    """Test argument hashing."""

    def test_same_args_same_hash(self):
        from agent.core.doom_loop import _hash_args
        h1 = _hash_args('{"a": 1, "b": 2}')
        h2 = _hash_args('{"b": 2, "a": 1}')
        assert h1 == h2

    def test_different_args_different_hash(self):
        from agent.core.doom_loop import _hash_args
        h1 = _hash_args('{"a": 1}')
        h2 = _hash_args('{"a": 2}')
        assert h1 != h2


class TestExtractSignatures:
    """Test tool call signature extraction."""

    def test_empty_messages(self):
        from agent.core.doom_loop import extract_recent_tool_signatures
        sigs = extract_recent_tool_signatures([])
        assert len(sigs) == 0

    def test_assistant_with_tool_calls(self):
        from agent.core.doom_loop import extract_recent_tool_signatures
        msgs = [
            _make_assistant_msg([{"name": "bash", "id": "tc1", "arguments": '{"cmd":"ls"}'}]),
            _make_tool_msg("tc1", "file1.txt"),
        ]
        sigs = extract_recent_tool_signatures(msgs)
        assert len(sigs) == 1
        assert sigs[0].name == "bash"

    def test_user_messages_ignored(self):
        from agent.core.doom_loop import extract_recent_tool_signatures
        msgs = [Message(role="user", content="hello")]
        sigs = extract_recent_tool_signatures(msgs)
        assert len(sigs) == 0


class TestDetectIdenticalConsecutive:
    """Test identical consecutive call detection."""

    def test_no_repetition(self):
        from agent.core.doom_loop import detect_identical_consecutive, ToolCallSignature
        sigs = [
            ToolCallSignature("bash", "h1", "r1"),
            ToolCallSignature("read", "h2", "r2"),
        ]
        assert detect_identical_consecutive(sigs) is None

    def test_detects_repetition(self):
        from agent.core.doom_loop import detect_identical_consecutive, ToolCallSignature
        sig = ToolCallSignature("bash", "h1", "r1")
        sigs = [sig, sig, sig]
        assert detect_identical_consecutive(sigs) == "bash"

    def test_threshold(self):
        from agent.core.doom_loop import detect_identical_consecutive, ToolCallSignature
        sig = ToolCallSignature("bash", "h1", "r1")
        assert detect_identical_consecutive([sig, sig]) is None
        assert detect_identical_consecutive([sig, sig, sig]) == "bash"


class TestDetectRepeatingSequence:
    """Test repeating sequence detection."""

    def test_no_sequence(self):
        from agent.core.doom_loop import detect_repeating_sequence, ToolCallSignature
        sigs = [
            ToolCallSignature("a", "h1", "r1"),
            ToolCallSignature("b", "h2", "r2"),
            ToolCallSignature("c", "h3", "r3"),
        ]
        assert detect_repeating_sequence(sigs) is None

    def test_detects_ab_pattern(self):
        from agent.core.doom_loop import detect_repeating_sequence, ToolCallSignature
        a = ToolCallSignature("a", "h1", "r1")
        b = ToolCallSignature("b", "h2", "r2")
        sigs = [a, b, a, b, a, b]
        pattern = detect_repeating_sequence(sigs)
        assert pattern is not None
        assert len(pattern) == 2


class TestCheckForDoomLoop:
    """Test main doom loop check."""

    def test_empty_messages(self):
        from agent.core.doom_loop import check_for_doom_loop
        assert check_for_doom_loop([]) is None

    def test_no_doom_loop(self):
        from agent.core.doom_loop import check_for_doom_loop
        msgs = [
            Message(role="user", content="hello"),
            _make_assistant_msg([{"name": "bash", "id": "tc1", "arguments": '{"cmd":"ls"}'}]),
            _make_tool_msg("tc1", "result"),
        ]
        assert check_for_doom_loop(msgs) is None

    def test_detects_doom_loop(self):
        from agent.core.doom_loop import check_for_doom_loop
        msgs = []
        for i in range(5):
            msgs.append(_make_assistant_msg([{"name": "bash", "id": f"tc{i}", "arguments": '{"cmd":"ls"}'}]))
            msgs.append(_make_tool_msg(f"tc{i}", "same result"))
        result = check_for_doom_loop(msgs)
        assert result is not None
        assert "REPETITION GUARD" in result
