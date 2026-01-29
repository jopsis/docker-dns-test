import json
import asyncio
from pathlib import Path
from typing import List, Dict
from datetime import datetime


class JSONLLogger:
    """Asynchronous JSONL logger with file rotation support."""

    def __init__(
        self,
        file_path: str,
        max_file_size_mb: int = 100,
        rotation_count: int = 5,
        enabled: bool = True
    ):
        """
        Initialize the JSONL logger.

        Args:
            file_path: Path to the log file
            max_file_size_mb: Maximum file size in MB before rotation
            rotation_count: Number of rotated files to keep
            enabled: Whether logging is enabled
        """
        self.file_path = Path(file_path)
        self.max_file_size_bytes = max_file_size_mb * 1024 * 1024
        self.rotation_count = rotation_count
        self.enabled = enabled
        self.lock = asyncio.Lock()

        # Ensure log directory exists
        if self.enabled:
            self.file_path.parent.mkdir(parents=True, exist_ok=True)

    async def log(self, results: List[Dict]):
        """
        Log DNS test results to JSONL file.

        Args:
            results: List of DNS test result dictionaries
        """
        if not self.enabled:
            return

        async with self.lock:
            try:
                # Check if rotation is needed
                if self.file_path.exists():
                    file_size = self.file_path.stat().st_size
                    if file_size >= self.max_file_size_bytes:
                        await self._rotate()

                # Write results to file (append mode)
                with open(self.file_path, 'a', encoding='utf-8') as f:
                    for result in results:
                        json_line = json.dumps(result, ensure_ascii=False)
                        f.write(json_line + '\n')

            except Exception as e:
                print(f"Error writing to log file: {e}")

    async def _rotate(self):
        """Rotate log files (file.log -> file.log.1 -> file.log.2 -> ...)."""
        try:
            # Remove oldest file if it exists
            oldest_file = Path(f"{self.file_path}.{self.rotation_count}")
            if oldest_file.exists():
                oldest_file.unlink()

            # Rotate existing files
            for i in range(self.rotation_count - 1, 0, -1):
                old_file = Path(f"{self.file_path}.{i}")
                new_file = Path(f"{self.file_path}.{i + 1}")
                if old_file.exists():
                    old_file.rename(new_file)

            # Rotate current file to .1
            if self.file_path.exists():
                self.file_path.rename(f"{self.file_path}.1")

        except Exception as e:
            print(f"Error during log rotation: {e}")

    async def read_recent(self, lines: int = 100) -> List[Dict]:
        """
        Read recent log entries.

        Args:
            lines: Number of recent lines to read

        Returns:
            List of parsed JSON objects
        """
        if not self.enabled or not self.file_path.exists():
            return []

        try:
            async with self.lock:
                with open(self.file_path, 'r', encoding='utf-8') as f:
                    # Read all lines
                    all_lines = f.readlines()

                    # Get last N lines
                    recent_lines = all_lines[-lines:] if len(all_lines) > lines else all_lines

                    # Parse JSON
                    results = []
                    for line in recent_lines:
                        try:
                            results.append(json.loads(line.strip()))
                        except json.JSONDecodeError:
                            continue

                    return results

        except Exception as e:
            print(f"Error reading log file: {e}")
            return []

    def get_file_info(self) -> Dict:
        """
        Get information about the log file.

        Returns:
            Dictionary with file info (size, exists, path)
        """
        if not self.enabled:
            return {
                "enabled": False,
                "path": str(self.file_path),
                "exists": False,
                "size_bytes": 0,
                "size_mb": 0.0
            }

        exists = self.file_path.exists()
        size_bytes = self.file_path.stat().st_size if exists else 0

        return {
            "enabled": True,
            "path": str(self.file_path),
            "exists": exists,
            "size_bytes": size_bytes,
            "size_mb": round(size_bytes / (1024 * 1024), 2),
            "max_size_mb": self.max_file_size_bytes / (1024 * 1024),
            "rotation_count": self.rotation_count
        }
