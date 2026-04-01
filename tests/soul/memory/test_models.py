"""Tests for memory compaction models."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest

from kimi_cli.soul.memory.models import (
    FileEditEvent,
    MemoryConfig,
    MemoryFragment,
    MemoryStore,
    ToolUseEvent,
)


class TestMemoryFragment:
    """Test MemoryFragment dataclass."""

    def test_create_file_edit_fragment(self):
        """Test creating a fragment from file edit event."""
        event = FileEditEvent(
            path="src/main.py",
            content="def hello(): pass",
            timestamp=datetime.now(),
        )
        
        fragment = MemoryFragment.from_event(event)
        
        assert fragment.files_modified == ["src/main.py"]
        assert fragment.event_type == "file_edit"
        assert fragment.timestamp == event.timestamp

    def test_create_tool_use_fragment(self):
        """Test creating a fragment from tool use event."""
        event = ToolUseEvent(
            tool_name="Shell",
            params={"command": "git status"},
            result={"exit_code": 0},
            timestamp=datetime.now(),
        )
        
        fragment = MemoryFragment.from_event(event)
        
        assert fragment.tools_called == ["Shell"]
        assert fragment.event_type == "tool_use"
        assert "git" in fragment.keywords

    def test_merge_fragments(self):
        """Test merging multiple fragments."""
        fragments = [
            MemoryFragment(
                files_modified=["a.py"],
                tools_called=["Read"],
                timestamp=datetime.now(),
            ),
            MemoryFragment(
                files_modified=["b.py"],
                tools_called=["Write"],
                timestamp=datetime.now(),
            ),
        ]
        
        merged = MemoryFragment.merge(fragments)
        
        assert set(merged.files_modified) == {"a.py", "b.py"}
        assert set(merged.tools_called) == {"Read", "Write"}


class TestMemoryConfig:
    """Test MemoryConfig."""

    def test_default_config(self):
        """Test default configuration values."""
        config = MemoryConfig()
        
        assert config.min_tokens_to_init == 10_000
        assert config.min_tokens_between_update == 5_000
        assert config.tool_calls_between_updates == 3

    def test_custom_config(self):
        """Test custom configuration."""
        config = MemoryConfig(
            min_tokens_to_init=5_000,
            tool_calls_between_updates=5,
        )
        
        assert config.min_tokens_to_init == 5_000
        assert config.tool_calls_between_updates == 5


class TestMemoryStore:
    """Test MemoryStore file operations."""

    def test_append_and_read(self, tmp_path: Path):
        """Test appending fragment and reading back."""
        store = MemoryStore(tmp_path / "memory.md")
        
        fragment = MemoryFragment(
            files_modified=["test.py"],
            timestamp=datetime.now(),
        )
        
        store.append(fragment)
        content = store.read()
        
        assert "test.py" in content

    def test_read_empty_store(self, tmp_path: Path):
        """Test reading from empty store."""
        store = MemoryStore(tmp_path / "memory.md")
        
        content = store.read()
        
        assert content == ""

    def test_multiple_appends(self, tmp_path: Path):
        """Test appending multiple fragments."""
        store = MemoryStore(tmp_path / "memory.md")
        
        store.append(MemoryFragment(files_modified=["a.py"], timestamp=datetime.now()))
        store.append(MemoryFragment(files_modified=["b.py"], timestamp=datetime.now()))
        
        content = store.read()
        
        assert "a.py" in content
        assert "b.py" in content

    def test_overwrite(self, tmp_path: Path):
        """Test overwriting store content."""
        store = MemoryStore(tmp_path / "memory.md")
        
        store.append(MemoryFragment(files_modified=["old.py"], timestamp=datetime.now()))
        store.write("# New Content")
        
        content = store.read()
        
        assert content == "# New Content"
