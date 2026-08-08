import argparse
import os
import time

import pandas as pd

from contest import Contest
from eurovision.scrapers import OddsScraper


def to_csv(contest):
    """Append betting odds to betting_offices.csv"""

    all_bets = contest.betting_offices_to_list()

    if len(all_bets) == 0:
        print("No betting odds found for this year.")
        return

    df = pd.DataFrame(all_bets)

    filename = "betting_offices.csv"

    if not os.path.exists(filename):
        df.to_csv(filename, index=False)
    else:
        df.to_csv(filename, mode="a", header=False, index=False)


def get_odds(year, rounds, max_attempts=5):
    """Scrape one Eurovision year with retries."""

    attempts = 0

    while attempts < max_attempts:

        try:

            contest = Contest(year)

            for rnd in rounds:

                print(f"Scraping: Eurovision {year} ({rnd})")

                result = scraper.scrape_year(contest, rnd)

                if result is not None:
                    contest = result

            return contest

        except Exception as e:

            attempts += 1

            print(f"\nAttempt {attempts}/{max_attempts} failed for {year}")
            print(e)

            time.sleep(5)

    print(f"\nSkipping {year} after {max_attempts} failed attempts.")
    return None


if __name__ == "__main__":

    parser = argparse.ArgumentParser(description="Eurovision Betting Odds Scraper")

    parser.add_argument(
        "--start",
        type=int,
        default=2015,
        help="First Eurovision year",
    )

    parser.add_argument(
        "--end",
        type=int,
        default=2026,
        help="Last Eurovision year",
    )

    args = parser.parse_args()

    if args.start < 2015:
        raise Exception("Betting odds only exist from 2015 onward.")

    scraper = OddsScraper()

    rounds = [
        "final",
        "semi-final-1",
        "semi-final-2",
    ]

    # -----------------------------------------
    # Resume support
    # -----------------------------------------

    scraped_years = set()

    if os.path.exists("betting_offices.csv"):

        try:

            old = pd.read_csv("betting_offices.csv")

            if "year" in old.columns:
                scraped_years = set(old["year"].dropna().astype(int).unique())

        except Exception:
            print("Existing betting_offices.csv could not be read.")
            print("Starting from scratch.")

    # -----------------------------------------
    # Main scraping loop
    # -----------------------------------------

    for year in range(args.start, args.end + 1):

        if year in scraped_years:
            print(f"Skipping {year} (already scraped)")
            continue

        print(f"\n========== {year} ==========")

        contest = get_odds(year, rounds)

        if contest is not None:

            to_csv(contest)

            print(f"Finished {year}")

    print("\nAll requested years have been processed.")

    if scraper.driver:
        scraper.driver.quit()