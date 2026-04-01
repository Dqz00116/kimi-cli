"""Memory formatter for converting fragments to structured markdown."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from loguru import logger

from kimi_cli.soul.memory.models import MemoryFragment

if TYPE_CHECKING:
    from kimi_cli.session import Session


class MemoryFormatter:
    """Formatter for converting memory fragments to structured markdown."""

    def __init__(self, session: Session) -> None:
        """Initialize formatter with session.
        
        Args:
            session: The current session for context.
        """
        self._session = session
        logger.debug("MemoryFormatter initialized")

    def format(self, fragments: list[MemoryFragment]) -> str:
        """Format fragments into structured markdown.
        
        Args:
            fragments: List of memory fragments to format.
            
        Returns:
            Formatted markdown string.
        """
        lines: list[str] = []
        
        # Header
        lines.append("# Session Memory")
        lines.append("")
        
        # Session Info Section
        lines.extend(self._format_session_info())
        
        if fragments:
            # Important Files Section
            lines.extend(self._format_important_files(fragments))
            
            # Recent Changes Section
            lines.extend(self._format_recent_changes(fragments))
            
            # Key Decisions Section
            lines.extend(self._format_key_decisions(fragments))
        
        result = "\n".join(lines)
        logger.debug(f"Formatted {len(fragments)} fragments into memory markdown")
        return result

    def _format_session_info(self) -> list[str]:
        """Format session information section."""
        lines: list[str] = []
        lines.append("## Session Info")
        
        # Session start time
        started_at = getattr(self._session, 'started_at', None)
        if started_at:
            if isinstance(started_at, datetime):
                started_str = started_at.strftime("%Y-%m-%d")
            else:
                started_str = str(started_at)
            lines.append(f"- Started: {started_str}")
        
        # Current task
        task = getattr(self._session, 'task', None) or getattr(self._session, 'current_task', None)
        if task:
            lines.append(f"- Current Task: {task}")
        
        lines.append("")
        return lines

    def _format_important_files(self, fragments: list[MemoryFragment]) -> list[str]:
        """Format important files section."""
        lines: list[str] = []
        
        # Collect all files with deduplication (preserve order)
        seen_files: set[str] = set()
        unique_files: list[str] = []
        for fragment in fragments:
            for file_path in fragment.files_modified:
                if file_path not in seen_files:
                    seen_files.add(file_path)
                    unique_files.append(file_path)
        
        if unique_files:
            lines.append("## Important Files")
            for file_path in unique_files:
                description = self._get_file_description(file_path)
                lines.append(f"- {file_path} - {description}")
            lines.append("")
        
        return lines

    def _format_recent_changes(self, fragments: list[MemoryFragment]) -> list[str]:
        """Format recent changes section."""
        lines: list[str] = []
        
        changes: list[str] = []
        for fragment in fragments:
            if fragment.event_type == "file_edit" and fragment.files_modified:
                for file_path in fragment.files_modified:
                    changes.append(f"Modified {file_path}")
            elif fragment.event_type == "tool_use" and fragment.tools_called:
                for tool in fragment.tools_called:
                    changes.append(f"Executed {tool}")
        
        # Remove duplicates while preserving order (keep most recent)
        seen: set[str] = set()
        unique_changes: list[str] = []
        for change in reversed(changes):
            if change not in seen:
                seen.add(change)
                unique_changes.insert(0, change)
        
        if unique_changes:
            lines.append("## Recent Changes")
            for change in unique_changes[-10:]:  # Keep last 10 changes
                lines.append(f"- {change}")
            lines.append("")
        
        return lines

    def _format_key_decisions(self, fragments: list[MemoryFragment]) -> list[str]:
        """Format key decisions section."""
        lines: list[str] = []
        
        # Collect keywords that might represent decisions
        all_keywords: set[str] = set()
        for fragment in fragments:
            all_keywords.update(fragment.keywords)
        
        # Filter for meaningful keywords (technology choices, patterns, etc.)
        decision_keywords = {
            kw for kw in all_keywords
            if len(kw) > 2 and not kw.startswith("-")
        }
        
        if decision_keywords:
            lines.append("## Key Decisions")
            for kw in sorted(decision_keywords)[:10]:  # Limit to 10 keywords
                lines.append(f"- Using {kw}")
            lines.append("")
        
        return lines

    def _get_file_description(self, file_path: str) -> str:
        """Get a description for a file based on its path.
        
        Args:
            file_path: Path to the file.
            
        Returns:
            Description string.
        """
        path_lower = file_path.lower()
        
        # Test files (check first to avoid matching test_main.py as main entry)
        if "test" in path_lower or "spec" in path_lower:
            return "Test file"
        
        # Main entry points
        if "main.py" in path_lower or "__main__" in path_lower or "entry" in path_lower:
            return "Main entry point"
        
        # Configuration files
        if "config" in path_lower or "settings" in path_lower or ".env" in path_lower:
            return "Configuration"
        
        # Documentation
        if path_lower.endswith(".md") or path_lower.endswith(".rst") or "readme" in path_lower:
            return "Documentation"
        
        # Models/Schemas
        if "model" in path_lower or "schema" in path_lower:
            return "Data models"
        
        # Service/Logic
        if "service" in path_lower:
            return "Service implementation"
        
        # Utils/Helpers
        if "util" in path_lower or "helper" in path_lower:
            return "Utilities"
        
        # API routes
        if "route" in path_lower or "api" in path_lower or "endpoint" in path_lower:
            return "API endpoints"
        
        # Default
        parts = file_path.replace("\\", "/").split("/")
        file_name = parts[-1] if parts else file_path
        return f"Source file"
