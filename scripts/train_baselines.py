"""Compare pooled-tile baselines and save the regional winner plus OOF reports.

Run: python scripts/train_baselines.py
First rebuild inputs with scripts/run_pipeline.py --step towers, then --step features.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

def main():
    from speedmap.training import train_baselines

    train_baselines()

if __name__ == "__main__":
    main()
