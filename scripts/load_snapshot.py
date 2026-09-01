import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.db import load_snapshot

if __name__ == "__main__":
    load_snapshot()
    print("已加载离线快照：data/embodiedgraph.db")
