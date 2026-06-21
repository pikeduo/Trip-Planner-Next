"""Runtime console log capture."""

import sys
from pathlib import Path
from typing import TextIO


class ConsoleLogWriter:
    def __init__(self, console: TextIO, log_file: TextIO) -> None:
        self.console = console
        self.log_file = log_file

    def write(self, message: str) -> int:
        try:
            self.console.write(message)
        except UnicodeEncodeError:
            safe_message = message.encode(self.console.encoding or "utf-8", errors="replace").decode(
                self.console.encoding or "utf-8",
                errors="replace",
            )
            self.console.write(safe_message)
        self.log_file.write(message)
        return len(message)

    def flush(self) -> None:
        self.console.flush()
        self.log_file.flush()

    def __getattr__(self, name: str):
        return getattr(self.console, name)


def install_console_log(log_path: Path) -> None:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_file = log_path.open("w", encoding="utf-8")
    sys.stdout = ConsoleLogWriter(sys.stdout, log_file)
    sys.stderr = ConsoleLogWriter(sys.stderr, log_file)
