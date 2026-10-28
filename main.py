"""Run the whole project: clean the raw MoMA data, then run the analysis."""

import analysis
import data_cleaning


def main() -> None:
    df = data_cleaning.clean()
    analysis.run(df)


if __name__ == "__main__":
    main()
