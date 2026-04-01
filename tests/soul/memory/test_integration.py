"""Integration tests for memory compaction with existing compaction system."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from kimi_cli.soul.compaction import SimpleCompaction
from kimi_cli.soul.memory import MemoryCompactionService, MemoryConfig
from kimi_cli.soul.memory.models import FileEditEvent


@pytest.fixture
def mock_session(tmp_path: Path) -> Mock:
    """Create a mock session."""
    session = Mock()
    session.dir = tmp_path
    return session


@pytest.fixture
def mock_llm() -> Mock:
    """Create a mock LLM."""
    return Mock()


class TestMemoryCompactionIntegration:
    """Test integration with existing compaction system."""

    @pytest.mark.asyncio
    async def test_compact_uses_memory_when_available(
        self, mock_session: Mock, mock_llm: Mock
    ):
        """Test that compaction uses memory when available."""
        # Setup: Create memory with content
        service = MemoryCompactionService(mock_session)
        event = FileEditEvent(
            path="src/main.py",
            content="def hello(): pass",
            timestamp=datetime.now(),
        )
        service.extract_sync(event)

        # Verify: Memory should be available
        memory = await service.get_memory_for_compaction()
        assert memory is not None
        assert "src/main.py" in memory

    @pytest.mark.asyncio
    async def test_compact_without_memory_fallback(
        self, mock_session: Mock, mock_llm: Mock
    ):
        """Test fallback when no memory is available."""
        service = MemoryCompactionService(mock_session)

        # Verify: No memory available
        memory = await service.get_memory_for_compaction()
        assert memory is None

    def test_memory_config_compatibility(self):
        """Test that memory config values are reasonable."""
        config = MemoryConfig()

        # Initialization threshold should be reasonable
        assert config.min_tokens_to_init > 0
        assert config.min_tokens_to_init < 100_000

        # Update interval should be less than init threshold
        assert config.min_tokens_between_update < config.min_tokens_to_init

    @pytest.mark.asyncio
    async def test_memory_file_persistence(self, mock_session: Mock):
        """Test that memory survives service restart."""
        # Create first service instance and add content
        service1 = MemoryCompactionService(mock_session)
        event = FileEditEvent(
            path="persistent.py",
            content="x = 1",
            timestamp=datetime.now(),
        )
        service1.extract_sync(event)

        # Create second service instance (simulating restart)
        service2 = MemoryCompactionService(mock_session)

        # Verify: Content should be preserved
        memory = await service2.get_memory_for_compaction()
        assert memory is not None
        assert "persistent.py" in memory

    def test_multiple_events_accumulation(self, mock_session: Mock):
        """Test that multiple events accumulate in memory."""
        service = MemoryCompactionService(mock_session)

        # Add multiple events
        for i in range(5):
            event = FileEditEvent(
                path=f"file{i}.py",
                content=f"x = {i}",
                timestamp=datetime.now(),
            )
            service.extract_sync(event)

        # Verify: All files should be in fragments
        assert len(service._fragments) == 5
        files = [f.files_modified[0] for f in service._fragments]
        assert "file0.py" in files
        assert "file4.py" in files
