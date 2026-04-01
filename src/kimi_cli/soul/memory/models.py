"""Data models for memory compaction."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any


@dataclass
class FileEditEvent:
    """Event representing a file edit operation."""

    path: str
    content: str
    timestamp: datetime


@dataclass
class ToolUseEvent:
    """Event representing a tool use operation."""

    tool_name: str
    params: dict[str, Any]
    result: dict[str, Any] | None = None
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class MemoryFragment:
    """A fragment of extracted memory."""

    files_modified: list[str] = field(default_factory=list)
    tools_called: list[str] = field(default_factory=list)
    keywords: list[str] = field(default_factory=list)
    event_type: str = ""
    timestamp: datetime = field(default_factory=datetime.now)

    @classmethod
    def from_event(cls, event: FileEditEvent | ToolUseEvent) -> MemoryFragment:
        """Create a fragment from an event."""
        if isinstance(event, FileEditEvent):
            return cls(
                files_modified=[event.path],
                event_type="file_edit",
                timestamp=event.timestamp,
            )
        elif isinstance(event, ToolUseEvent):
            keywords = []
            if "command" in event.params:
                cmd = event.params["command"]
                keywords.extend(cmd.split()[:3])  # First 3 words as keywords
            return cls(
                tools_called=[event.tool_name],
                keywords=keywords,
                event_type="tool_use",
                timestamp=event.timestamp,
            )
        raise ValueError(f"Unknown event type: {type(event)}")

    @classmethod
    def merge(cls, fragments: list[MemoryFragment]) -> MemoryFragment:
        """Merge multiple fragments into one."""
        all_files = []
        all_tools = []
        all_keywords = []
        
        for f in fragments:
            all_files.extend(f.files_modified)
            all_tools.extend(f.tools_called)
            all_keywords.extend(f.keywords)
        
        return cls(
            files_modified=list(dict.fromkeys(all_files)),  # Preserve order, remove dups
            tools_called=list(dict.fromkeys(all_tools)),
            keywords=list(dict.fromkeys(all_keywords)),
            event_type="merged",
            timestamp=fragments[-1].timestamp if fragments else datetime.now(),
        )


@dataclass
class MemoryConfig:
    """Configuration for memory compaction."""

    min_tokens_to_init: int = 10_000
    min_tokens_between_update: int = 5_000
    tool_calls_between_updates: int = 3


class MemoryStore:
    """File-based storage for memory fragments."""

    def __init__(self, path: Path) -> None:
        self._path = Path(path)
        self._ensure_dir()

    def _ensure_dir(self) -> None:
        """Ensure parent directory exists."""
        self._path.parent.mkdir(parents=True, exist_ok=True)

    def append(self, fragment: MemoryFragment) -> None:
        """Append a fragment to the memory file."""
        content = self._format_fragment(fragment)
        mode = "a" if self._path.exists() else "w"
        with open(self._path, mode, encoding="utf-8") as f:
            if mode == "a":
                f.write("\n")
            f.write(content)

    def _format_fragment(self, fragment: MemoryFragment) -> str:
        """Format a fragment as markdown."""
        lines = [f"## {fragment.event_type.upper()} - {fragment.timestamp.isoformat()}"]
        
        if fragment.files_modified:
            lines.append("### Files Modified")
            for f in fragment.files_modified:
                lines.append(f"- {f}")
        
        if fragment.tools_called:
            lines.append("### Tools Called")
            for t in fragment.tools_called:
                lines.append(f"- {t}")
        
        if fragment.keywords:
            lines.append(f"**Keywords**: {', '.join(fragment.keywords)}")
        
        return "\n".join(lines)

    def read(self) -> str:
        """Read the memory file content."""
        if not self._path.exists():
            return ""
        with open(self._path, encoding="utf-8") as f:
            return f.read()

    def write(self, content: str) -> None:
        """Overwrite the memory file."""
        self._ensure_dir()
        with open(self._path, "w", encoding="utf-8") as f:
            f.write(content)
