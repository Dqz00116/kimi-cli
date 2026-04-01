"""Memory compaction service."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

from loguru import logger

from kimi_cli.soul.memory.formatter import MemoryFormatter
from kimi_cli.soul.memory.models import (
    FileEditEvent,
    MemoryConfig,
    MemoryFragment,
    MemoryStore,
    ToolUseEvent,
)

if TYPE_CHECKING:
    from kimi_cli.session import Session


class MemoryCompactionService:
    """Service for incremental memory compaction."""

    def __init__(
        self,
        session: Session,
        config: MemoryConfig | None = None,
    ) -> None:
        self._session = session
        self._config = config or MemoryConfig()
        self._store = MemoryStore(session.dir / "memory.md")
        self._fragments: list[MemoryFragment] = []
        self._formatter = MemoryFormatter(session)
        self._tokens_at_last_extraction = 0
        self._tool_calls_since_last = 0
        self._initialized = False
        logger.debug("MemoryCompactionService initialized")

    def extract_sync(self, event: FileEditEvent | ToolUseEvent) -> MemoryFragment:
        """Extract a memory fragment from an event (synchronous)."""
        fragment = MemoryFragment.from_event(event)
        self._fragments.append(fragment)
        
        # Persist to store
        self._store.append(fragment)
        
        # Update counters
        if isinstance(event, ToolUseEvent):
            self._tool_calls_since_last += 1
        
        logger.debug(f"Extracted fragment: {fragment.event_type}")
        return fragment

    def on_step_complete(self, current_tokens: int) -> MemoryFragment | None:
        """Handle step completion.
        
        Called after each conversation step. Triggers memory extraction
        if thresholds are met.
        
        Args:
            current_tokens: Current token count in the conversation.
            
        Returns:
            MemoryFragment if extraction was triggered, None otherwise.
        """
        if self.should_trigger(current_tokens):
            logger.info(f"Triggering memory extraction at {current_tokens} tokens")
            
            # Merge all recent fragments into a single summary fragment
            if self._fragments:
                merged = MemoryFragment.merge(self._fragments)
                self.record_extraction(current_tokens)
                return merged
            else:
                # No fragments yet, create an initialization fragment
                self._initialized = True
                fragment = MemoryFragment(
                    event_type="initialization",
                    timestamp=datetime.now(),
                )
                self._fragments.append(fragment)
                self.record_extraction(current_tokens)
                return fragment
        
        return None

    def on_file_edit(self, path: str, content: str) -> MemoryFragment:
        """Handle file edit event.
        
        Args:
            path: Path to the edited file.
            content: New content of the file.
            
        Returns:
            Created memory fragment.
        """
        event = FileEditEvent(
            path=path,
            content=content,
            timestamp=datetime.now(),
        )
        fragment = self.extract_sync(event)
        logger.debug(f"Recorded file edit: {path}")
        return fragment

    def on_tool_use(
        self,
        tool_name: str,
        params: dict,
        result: dict | None = None
    ) -> MemoryFragment:
        """Handle tool use event.
        
        Args:
            tool_name: Name of the tool used.
            params: Tool parameters.
            result: Optional tool result.
            
        Returns:
            Created memory fragment.
        """
        event = ToolUseEvent(
            tool_name=tool_name,
            params=params,
            result=result,
            timestamp=datetime.now(),
        )
        fragment = self.extract_sync(event)
        logger.debug(f"Recorded tool use: {tool_name}")
        return fragment

    def should_trigger(self, current_tokens: int) -> bool:
        """Check if memory extraction should be triggered.
        
        Uses smart triggering based on:
        - Token growth since last extraction
        - Number of tool calls since last extraction
        - Initialization threshold
        
        Args:
            current_tokens: Current token count.
            
        Returns:
            True if extraction should be triggered.
        """
        # Check initialization threshold
        if not self._initialized:
            if current_tokens >= self._config.min_tokens_to_init:
                self._initialized = True
                return True
            return False

        # Check token growth threshold
        tokens_since_last = current_tokens - self._tokens_at_last_extraction
        has_met_token_threshold = tokens_since_last >= self._config.min_tokens_between_update

        # Check tool call threshold
        has_met_tool_threshold = self._tool_calls_since_last >= self._config.tool_calls_between_updates

        return has_met_token_threshold or has_met_tool_threshold

    async def get_memory_for_compaction(self) -> str | None:
        """Get memory content for compaction.
        
        Returns formatted memory if available, None otherwise.
        """
        if not self._fragments:
            # Check if there's persisted content
            persisted = self._store.read()
            if persisted:
                return persisted
            return None
        
        # Format using the formatter
        formatted = self._formatter.format(self._fragments)
        return formatted

    def record_extraction(self, current_tokens: int) -> None:
        """Record that extraction occurred.
        
        Resets counters and updates token tracking.
        
        Args:
            current_tokens: Current token count.
        """
        self._tokens_at_last_extraction = current_tokens
        self._tool_calls_since_last = 0
        logger.debug(f"Recorded extraction at {current_tokens} tokens")
