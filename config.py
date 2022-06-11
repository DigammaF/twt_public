
import json

from pathlib import Path

plugins_package = "plugins"
plugins_file = Path("plugins.json")
if not plugins_file.exists(): json.dump([], open(plugins_file, "r", encoding="utf-8"))
