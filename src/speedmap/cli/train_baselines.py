"""Compare pooled-tile baselines and save the regional winner plus OOF reports.

Run: python -m speedmap.cli.train_baselines
First rebuild inputs with python -m speedmap.cli.run_pipeline --step towers, then --step features.
"""


def main():
    from speedmap.training import train_baselines

    train_baselines()


if __name__ == "__main__":
    main()
