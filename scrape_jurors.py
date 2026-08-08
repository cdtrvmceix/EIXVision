import argparse
import os
import pandas as pd

from contest import Contest
from eurovision.scrapers import JurorsScraper


def to_csv(rows):
    if not rows:
        return
        
    # Unpack the JurorVote objects into a list of dictionaries
    data = [
        {
            "year": r.year,
            "round": r.contest_round,
            "from_country": r.from_country,
            "to_country": r.to_country,
            "televote_rank": r.televote_rank,
            "jury_rank": r.jury_rank,
            "juror_A": r.juror_a,
            "juror_B": r.juror_b,
            "juror_C": r.juror_c,
            "juror_D": r.juror_d,
            "juror_E": r.juror_e,
            "juror_F": r.juror_f,
            "juror_G": r.juror_g,
        }
        for r in rows
    ]

    df = pd.DataFrame(data)
    filename = "jurors.csv"

    if not os.path.exists(filename):
        df.to_csv(filename, index=False)
    else:
        df.to_csv(filename, mode="a", header=False, index=False)


def get_jurors(year, rounds, scraper):
    contest = Contest(year)
    rows = []

    for r in rounds:
        print(f"Scraping jurors: Eurovision Song Contest {year} {r}")
        result = scraper.scrape_year(contest, r)
        
        # PROGRESSIVE SAVE: Write to CSV immediately after every round
        to_csv(result)
        rows.extend(result)

    return rows


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Eurovision Juror Scraper")

    parser.add_argument("--start", type=int, default=2016)
    parser.add_argument("--end", type=int, default=2026)

    args = parser.parse_args()
    scraper = JurorsScraper()
    all_rows = []

    for year in range(args.start, args.end + 1):
        # Always attempt all rounds. If a round doesn't have jury data, the scraper will gracefully skip it.
        rounds = ["semi-final-1", "semi-final-2", "final"]
        rows = get_jurors(year, rounds, scraper)
        all_rows.extend(rows)

    print(f"Total juror rows scraped: {len(all_rows)}")