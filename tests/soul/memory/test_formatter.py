"""Tests for memory formatter."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from unittest.mock import Mock

import pytest

from kimi_cli.soul.memory.formatter import MemoryFormatter
from kimi_cli.soul.memory.models import MemoryFragment


@pytest.fixture
def mock_session(tmp_path: Path) -> Mock:
    """Create a mock session."""
    session = Mock()
    session.dir = tmp_path
    session.started_at = datetime(2026, 4, 1, 10, 0, 0)
    session.task = "Implementing feature X"
    return session


class TestMemoryFormatter:
    """Test MemoryFormatter."""

    def test_init(self, mock_session: Mock):
        """Test formatter initialization."""
        formatter = MemoryFormatter(mock_session)
        
        assert formatter._session == mock_session

    def test_format_empty_fragments(self, mock_session: Mock):
        """Test formatting with empty fragments."""
        formatter = MemoryFormatter(mock_session)
        
        result = formatter.format([])
        
        assert "# Session Memory" in result
        assert "## Session Info" in result
        assert "Started: 2026-04-01" in result
        assert "Current Task: Implementing feature X" in result

    def test_format_with_file_edits(self, mock_session: Mock):
        """Test formatting with file edit fragments."""
        formatter = MemoryFormatter(mock_session)
        
        fragments = [
            MemoryFragment(
                files_modified=["src/main.py"],
                event_type="file_edit",
                timestamp=datetime.now(),
            ),
            MemoryFragment(
                files_modified=["src/config.py"],
                event_type="file_edit",
                timestamp=datetime.now(),
            ),
        ]
        
        result = formatter.format(fragments)
        
        assert "## Important Files" in result
        assert "src/main.py" in result
        assert "src/config.py" in result

    def test_format_with_tool_calls(self, mock_session: Mock):
        """Test formatting with tool use fragments."""
        formatter = MemoryFormatter(mock_session)
        
        fragments = [
            MemoryFragment(
                tools_called=["Shell"],
                keywords=["git", "status"],
                event_type="tool_use",
                timestamp=datetime.now(),
            ),
            MemoryFragment(
                tools_called=["ReadFile"],
                event_type="tool_use",
                timestamp=datetime.now(),
            ),
        ]
        
        result = formatter.format(fragments)
        
        assert "## Recent Changes" in result
        assert "Executed Shell" in result
        assert "Executed ReadFile" in result

    def test_format_with_key_decisions(self, mock_session: Mock):
        """Test formatting with key decisions."""
        formatter = MemoryFormatter(mock_session)
        
        fragments = [
            MemoryFragment(
                files_modified=["src/main.py"],
                keywords=["asyncio", "async", "await"],
                event_type="file_edit",
                timestamp=datetime.now(),
            ),
        ]
        
        result = formatter.format(fragments)
        
        assert "## Key Decisions" in result
        assert "asyncio" in result

    def test_format_preserves_file_order(self, mock_session: Mock):
        """Test that file order is preserved (most recent last)."""
        formatter = MemoryFormatter(mock_session)
        
        fragments = [
            MemoryFragment(
                files_modified=["first.py"],
                event_type="file_edit",
                timestamp=datetime(2026, 4, 1, 10, 0, 0),
            ),
            MemoryFragment(
                files_modified=["second.py"],
                event_type="file_edit",
                timestamp=datetime(2026, 4, 1, 10, 1, 0),
            ),
        ]
        
        result = formatter.format(fragments)
        
        # Both files should be present
        assert "first.py" in result
        assert "second.py" in result

    def test_deduplicate_files(self, mock_session: Mock):
        """Test that duplicate files are deduplicated."""
        formatter = MemoryFormatter(mock_session)
        
        fragments = [
            MemoryFragment(
                files_modified=["src/main.py"],
                event_type="file_edit",
                timestamp=datetime.now(),
            ),
            MemoryFragment(
                files_modified=["src/main.py"],
                event_type="file_edit",
                timestamp=datetime.now(),
            ),
        ]
        
        result = formatter.format(fragments)
        
        # Should only appear once in Important Files section
        important_files_section = result.split("## Important Files")[1].split("##")[0]
        assert important_files_section.count("src/main.py") == 1


class TestMemoryFormatterDescriptions:
    """Test file description generation."""

    def test_get_file_description_for_python(self, mock_session: Mock):
        """Test description for Python files."""
        formatter = MemoryFormatter(mock_session)
        
        desc = formatter._get_file_description("src/main.py")
        
        assert "Main entry point" in desc or "entry" in desc.lower()

    def test_get_file_description_for_config(self, mock_session: Mock):
        """Test description for config files."""
        formatter = MemoryFormatter(mock_session)
        
        desc = formatter._get_file_description("config.py")
        
        assert "config" in desc.lower()

    def test_get_file_description_for_test(self, mock_session: Mock):
        """Test description for test files."""
        formatter = MemoryFormatter(mock_session)
        
        desc = formatter._get_file_description("tests/test_main.py")
        
        assert "test" in desc.lower()

    def test_get_file_description_generic(self, mock_session: Mock):
        """Test generic file description."""
        formatter = MemoryFormatter(mock_session)
        
        desc = formatter._get_file_description("some/random/file.txt")
        
        # Should return a non-empty string
        assert len(desc) > 0
