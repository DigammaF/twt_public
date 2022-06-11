
from pathlib import Path

tasks_file = Path("tasks.json")
tasks_archive_dir = Path("tasks_archive")
if not tasks_archive_dir.exists(): tasks_archive_dir.mkdir()

keywords: list[str] = [
]
