#!/usr/bin/env python3
"""Unified CLI for barren-order — workflow engine."""
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))


def main() -> None:
    """Show barren-order product info and available modules."""
    info = {
        "product": "barren-order",
        "type": "workflow engine",
        "modules": [
            "scripts/workflow_engine.py",
            "scripts/task_executor.py",
            "scripts/agent_manager.py",
            "modules/crew/flow_engine.py",
        ],
        "status": "ok",
    }
    if len(sys.argv) > 1 and sys.argv[1] == "--help":
        print("barren-order — workflow engine")
        print()
        print("Commands:")
        print("  (no args)    Show product info")
        print("  --help       Show this help")
        print()
        print("Modules:")
        for m in info["modules"]:
            print(f"  {m}")
    else:
        print(json.dumps(info, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
