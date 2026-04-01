"""Tests for memory compaction service."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from unittest.mock import Mock

import pytest

from kimi_cli.soul.memory.models import FileEditEvent, MemoryConfig, MemoryFragment, ToolUseEvent
from kimi_cli.soul.memory.service import MemoryCompactionService


@pytest.fixture
def mock_session(tmp_path: Path) -> Mock:
    """Create a mock session."""
    session = Mock()
    session.dir = tmp_path
    return session


class TestMemoryCompactionService:
    """Test MemoryCompactionService."""

    def test_init_with_default_config(self, mock_session: Mock):
        """Test initialization with default config."""
        service = MemoryCompactionService(mock_session)
        
        assert service._config.min_tokens_to_init == 10_000
        assert service._store is not None

    def test_init_with_custom_config(self, mock_session: Mock):
        """Test initialization with custom config."""
        config = MemoryConfig(min_tokens_to_init=5_000)
        service = MemoryCompactionService(mock_session, config)
        
        assert service._config.min_tokens_to_init == 5_000

    def test_extract_file_edit(self, mock_session: Mock):
        """Test extracting file edit event."""
        service = MemoryCompactionService(mock_session)
        
        event = FileEditEvent(
            path="src/main.py",
            content="def hello(): pass",
            timestamp=datetime.now(),
        )
        
        fragment = service.extract_sync(event)
        
        assert fragment.files_modified == ["src/main.py"]
        assert fragment.event_type == "file_edit"
        assert len(service._fragments) == 1

    def test_extract_tool_use(self, mock_session: Mock):
        """Test extracting tool use event."""
        service = MemoryCompactionService(mock_session)
        
        event = ToolUseEvent(
            tool_name="Shell",
            params={"command": "git status"},
            result={"exit_code": 0},
            timestamp=datetime.now(),
        )
        
        fragment = service.extract_sync(event)
        
        assert fragment.tools_called == ["Shell"]
        assert "git" in fragment.keywords
        assert len(service._fragments) == 1

    def test_should_trigger_initialization(self, mock_session: Mock):
        """Test trigger on initialization threshold."""
        service = MemoryCompactionService(mock_session)
        
        # Below threshold
        assert not service.should_trigger(5_000)
        
        # At threshold
        assert service.should_trigger(10_000)
        assert service._initialized

    def test_should_trigger_token_growth(self, mock_session: Mock):
        """Test trigger on token growth."""
        service = MemoryCompactionService(mock_session)
        service._initialized = True
        service._tokens_at_last_extraction = 10_000
        
        # Below growth threshold
        assert not service.should_trigger(14_000)
        
        # At growth threshold
        assert service.should_trigger(15_000)

    def test_should_trigger_tool_calls(self, mock_session: Mock):
        """Test trigger on tool call count."""
        service = MemoryCompactionService(mock_session)
        service._initialized = True
        service._tool_calls_since_last = 3
        
        # Should trigger due to tool calls
        assert service.should_trigger(10_001)

    @pytest.mark.asyncio
    async def test_get_memory_empty(self, mock_session: Mock):
        """Test getting memory when empty."""
        service = MemoryCompactionService(mock_session)
        
        result = await service.get_memory_for_compaction()
        
        assert result is None

    @pytest.mark.asyncio
    async def test_get_memory_with_content(self, mock_session: Mock):
        """Test getting memory with content."""
        service = MemoryCompactionService(mock_session)
        
        # Add some content
        event = FileEditEvent(
            path="src/main.py",
            content="def hello(): pass",
            timestamp=datetime.now(),
        )
        service.extract_sync(event)
        
        result = await service.get_memory_for_compaction()
        
        assert result is not None
        assert "src/main.py" in result

    def test_record_extraction(self, mock_session: Mock):
        """Test recording extraction."""
        service = MemoryCompactionService(mock_session)
        service._tool_calls_since_last = 5
        
        service.record_extraction(15_000)
        
        assert service._tokens_at_last_extraction == 15_000
        assert service._tool_calls_since_last == 0


class TestMemoryCompactionServiceEventHandlers:
    """Test event handler methods."""

    def test_on_step_complete_triggers_extraction(self, mock_session: Mock):
        """Test on_step_complete triggers extraction when threshold met."""
        service = MemoryCompactionService(mock_session)
        service._initialized = True
        service._tokens_at_last_extraction = 10_000
        
        # Below threshold - should not trigger
        result = service.on_step_complete(current_tokens=14_000)
        assert result is None
        
        # At threshold - should trigger
        result = service.on_step_complete(current_tokens=15_000)
        assert result is not None
        assert isinstance(result, MemoryFragment)

    def test_on_step_complete_initialization(self, mock_session: Mock):
        """Test on_step_complete handles initialization."""
        service = MemoryCompactionService(mock_session)
        
        # First call initializes
        result = service.on_step_complete(current_tokens=10_000)
        assert result is not None
        assert service._initialized

    def test_on_file_edit(self, mock_session: Mock):
        """Test on_file_edit creates fragment."""
        service = MemoryCompactionService(mock_session)
        
        fragment = service.on_file_edit(
            path="src/main.py",
            content="def hello(): pass"
        )
        
        assert fragment.files_modified == ["src/main.py"]
        assert fragment.event_type == "file_edit"
        assert len(service._fragments) == 1
        assert service._fragments[0] == fragment

    def test_on_file_edit_persists(self, mock_session: Mock):
        """Test on_file_edit persists to store."""
        service = MemoryCompactionService(mock_session)
        
        service.on_file_edit(path="test.py", content="x = 1")
        
        content = service._store.read()
        assert "test.py" in content
        assert "FILE_EDIT" in content

    def test_on_tool_use(self, mock_session: Mock):
        """Test on_tool_use creates fragment."""
        service = MemoryCompactionService(mock_session)
        
        fragment = service.on_tool_use(
            tool_name="Shell",
            params={"command": "git status"},
            result={"exit_code": 0}
        )
        
        assert fragment.tools_called == ["Shell"]
        assert "git" in fragment.keywords
        assert fragment.event_type == "tool_use"

    def test_on_tool_use_increments_counter(self, mock_session: Mock):
        """Test on_tool_use increments tool call counter."""
        service = MemoryCompactionService(mock_session)
        assert service._tool_calls_since_last == 0
        
        service.on_tool_use(tool_name="ReadFile", params={"path": "test.py"})
        assert service._tool_calls_since_last == 1
        
        service.on_tool_use(tool_name="WriteFile", params={"path": "test.py"})
        assert service._tool_calls_since_last == 2

    def test_smart_trigger_combined_thresholds(self, mock_session: Mock):
        """Test smart trigger with combined token and tool thresholds."""
        service = MemoryCompactionService(mock_session)
        service._initialized = True
        service._tokens_at_last_extraction = 10_000
        service._tool_calls_since_last = 2
        
        # Not enough tokens (4k < 5k), not enough tools (2 < 3)
        assert not service.should_trigger(14_000)
        
        # Enough tokens, should trigger
        service._tool_calls_since_last = 0
        assert service.should_trigger(15_000)
        
        # Reset and check tool threshold
        service._tokens_at_last_extraction = 15_000
        service._tool_calls_since_last = 3
        assert service.should_trigger(15_100)

    def test_smart_trigger_after_extraction(self, mock_session: Mock):
        """Test that counters reset after extraction."""
        service = MemoryCompactionService(mock_session)
        service._initialized = True
        service._tokens_at_last_extraction = 10_000
        service._tool_calls_since_last = 3
        
        # Should trigger due to tool calls
        assert service.should_trigger(10_100)
        
        # Record extraction
        service.record_extraction(10_100)
        
        # Should not trigger immediately after
        assert not service.should_trigger(10_100)
        assert service._tool_calls_since_last == 0

    @pytest.mark.asyncio
    async def test_get_formatted_memory(self, mock_session: Mock):
        """Test getting formatted memory."""
        service = MemoryCompactionService(mock_session)
        mock_session.task = "Test task"
        
        service.on_file_edit(path="src/main.py", content="x = 1")
        
        result = await service.get_memory_for_compaction()
        
        assert result is not None
        assert "src/main.py" in result
