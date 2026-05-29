"""Foundation services package.

Provides async file system operations, shell execution, and file discovery.
"""

from opengame.services.file_discovery import discover_files, glob_files, grep_files
from opengame.services.fs_service import delete_file, edit_file, list_directory, read_file, write_file
from opengame.services.shell_service import ShellReadOnlyChecker, run_command

__all__ = [
    "read_file",
    "write_file",
    "edit_file",
    "delete_file",
    "list_directory",
    "run_command",
    "ShellReadOnlyChecker",
    "discover_files",
    "glob_files",
    "grep_files",
]
