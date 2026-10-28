"""Clean MoMA's collection data for analysis.

Input : data/raw/Artworks.csv.gz      (160,928 artworks, MoMA's own data)
Output: data/processed/artworks_clean.csv

Every step that removes rows is logged, so the cleaning report shows exactly
what happened to the data.
"""

import re
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).parent
RAW_DATA = ROOT / "data" / "raw" / "Artworks.csv.gz"
CLEAN_DATA = ROOT / "data" / "processed" / "artworks_clean.csv"

LATEST_YEAR = 2026  # nothing in the collection can be made after this

# Rare gender values, written by hand after looking at every distinct value.
# Anything not listed here (and not plain "male" / "female") becomes "Unknown".
GENDER_FIXES = {
    "female (transwoman": "Female",
    "transgender woman": "Female",
    "male (trans? ftm?": "Male",
    "non-binary": "Non-binary",
    "gender non-conforming": "Non-binary",
    "woman, non-binary": "Non-binary",
}

# Nationality -> world region. Covers every nationality with 5+ works;
# anything missing falls into "Other".
REGIONS = {
    "North America": ["American", "Canadian", "Native American", "Canadian Inuit", "Oneida", "Hopi",
                      "Spirit Lake Dakota", "Chippewa", "Six Nations", "Kalaaleq [Greenland]"],
    "Western Europe": ["French", "German", "British", "Spanish", "Italian", "Swiss", "Dutch", "Belgian",
                       "Austrian", "Danish", "Swedish", "Finnish", "Norwegian", "Portuguese", "Greek",
                       "Scottish", "Luxembourger", "Icelandic", "Irish", "English", "Welsh", "Catalan"],
    "Eastern Europe": ["Russian", "Czech", "Polish", "Croatian", "Serbian", "Hungarian", "Romanian",
                       "Ukrainian", "Latvian", "Slovenian", "Georgian", "Albanian", "Bosnian", "Lithuanian",
                       "Slovak", "Bulgarian", "Macedonian", "Czechoslovakian", "Estonian", "Yugoslavian",
                       "Azerbaijani", "Uzbekistani"],
    "Latin America & Caribbean": ["Mexican", "Argentine", "Brazilian", "Colombian", "Chilean", "Venezuelan",
                                  "Cuban", "Trinidad and Tobagonian", "Peruvian", "Uruguayan", "Guatemalan",
                                  "Puerto Rican", "Costa Rican", "Haitian", "Ecuadorian", "Panamanian",
                                  "Bolivian", "Nicaraguan", "Bahamian", "Salvadoran", "Jamaican",
                                  "Paraguayan", "Dominican", "Caribbean"],
    "Asia & Oceania": ["Japanese", "Chinese", "Indian", "Korean", "South Korean", "Pakistani", "Thai",
                       "Sri Lankan", "Vietnamese", "Bangladeshi", "Malaysian", "Taiwanese", "Indonesian",
                       "Singaporean", "Filipino", "Nepali", "Hmong", "Ivatan", "Australian",
                       "New Zealander", "Anmatyerr [Australian]"],
    "Africa & Middle East": ["Ivorian", "South African", "Israeli", "Egyptian", "Nigerian", "Sudanese",
                             "Turkish", "Lebanese", "Iranian", "Burkinabé", "Congolese", "Malian",
                             "Moroccan", "Zimbabwean", "Tanzanian", "Cameroonian", "Kenyan", "Senegalese",
                             "Central African", "Iraqi", "Tunisian", "Palestinian", "Ethiopian", "Ghanaian",
                             "Emirati", "Algerian", "Jordanian", "Mozambican", "Angolan", "Beninese",
                             "Namibian", "Persian", "Kuwaiti", "Afghan", "Ugandan", "Sierra Leonean",
                             "Syrian", "Coptic"],
}
NATIONALITY_TO_REGION = {nat: region for region, nats in REGIONS.items() for nat in nats}


# --------------------------------------------------------------------------- #
# Small helper functions — each cleans ONE value
# --------------------------------------------------------------------------- #
def strip_brackets(value) -> str:
    """'(American)' -> 'American'. MoMA wraps most artist fields in brackets."""
    if pd.isna(value):
        return ""
    value = str(value).strip()
    if value.startswith("(") and value.endswith(")"):
        value = value[1:-1]
    return value.strip()


def clean_gender(value) -> str:
    g = strip_brackets(value).lower()
    if g == "male":
        return "Male"
    if g == "female":
        return "Female"
    return GENDER_FIXES.get(g, "Unknown")


def clean_nationality(value) -> str:
    n = strip_brackets(value)
    if n in ("", "Nationality unknown"):
        return "Unknown"
    return n


def parse_year(value) -> float:
    """Pull one year out of a free-text date.

    '1958' -> 1958 · 'c. 1910' -> 1910 · '1961-72' -> 1961 · '(2004)' -> 2004
    'June 1946' -> 1946 · '1976–92, printed 2007' -> 1976 · 'n.d.' -> missing
    Rule: take the FIRST four-digit number between 1000 and LATEST_YEAR.
    """
    if pd.isna(value):
        return float("nan")
    for match in re.findall(r"\d{4}", str(value)):
        year = int(match)
        if 1000 <= year <= LATEST_YEAR:
            return float(year)
    return float("nan")


def parse_life_year(value) -> float:
    """BeginDate / EndDate look like '(1887)'. MoMA writes '(0)' when the year
    is unknown, so 0 is a hidden missing value, not a real year."""
    year = pd.to_numeric(strip_brackets(value), errors="coerce")
    return float("nan") if pd.isna(year) or year == 0 else float(year)


# --------------------------------------------------------------------------- #
# Main cleaning function
# --------------------------------------------------------------------------- #
def clean(verbose: bool = True) -> pd.DataFrame:
    df = pd.read_csv(RAW_DATA, low_memory=False)
    log = [("Raw data", len(df))]

    if verbose:
        print("=" * 60)
        print("DATA CLEANING")
        print("=" * 60)
        print(f"Loaded {len(df):,} artworks x {df.shape[1]} columns")
        missing = (df.isna().mean() * 100).round(1)
        print("Columns with missing values (%):", missing[missing > 0].sort_values(ascending=False).to_dict())

    # 1. Remove the Mies van der Rohe Archive -------------------------------
    # ~17,000 architecture drawings by ONE architect: about a tenth of the
    # collection. Kept in, they would dominate every count by artist.
    df = df[df.Classification != "Mies van der Rohe Archive"]
    log.append(("Removed Mies van der Rohe Archive", len(df)))

    # 2. Remove works with no artist information -----------------------------
    df = df[df.ConstituentID.notna()]
    log.append(("Removed works with no artist", len(df)))

    # 3. Remove works with no acquisition date --------------------------------
    df["date_acquired"] = pd.to_datetime(df.DateAcquired, errors="coerce")
    df = df[df.date_acquired.notna()]
    log.append(("Removed works with no acquisition date", len(df)))

    # 4. Number of artists per work -------------------------------------------
    # ConstituentID holds one ID per artist, comma-separated: '6210' or '6210, 7470'
    df["n_artists"] = df.ConstituentID.astype(str).str.count(",") + 1
    df["single_artist"] = df.n_artists == 1

    # 5. Artist fields (only meaningful for single-artist works) --------------
    single = df.single_artist
    df["gender"] = df.Gender.map(clean_gender).where(single, "Multiple artists")
    df["nationality"] = df.Nationality.map(clean_nationality).where(single, "Multiple artists")
    df["region"] = df.nationality.map(NATIONALITY_TO_REGION).fillna("Other")
    df.loc[df.nationality == "Unknown", "region"] = "Unknown"
    df.loc[~single, "region"] = "Multiple artists"
    df["artist_birth_year"] = df.BeginDate.map(parse_life_year).where(single)
    df["artist_death_year"] = df.EndDate.map(parse_life_year).where(single)

    # 6. Dates ------------------------------------------------------------------
    df["year_made"] = df.Date.map(parse_year)
    df["year_acquired"] = df.date_acquired.dt.year
    df["decade_acquired"] = (df.year_acquired // 10 * 10).astype(int)

    # A work cannot be made after MoMA acquired it. A few rows break this rule
    # (data-entry errors, or a print made later from an old plate), so their
    # creation year is treated as unreliable.
    impossible = df.year_made > df.year_acquired
    df.loc[impossible, "year_made"] = float("nan")
    if verbose:
        print(f"\nCreation year after acquisition year (set to missing): {impossible.sum():,} works")

    df["age_at_acquisition"] = df.year_acquired - df.year_made
    df["artist_age_when_made"] = df.year_made - df.artist_birth_year
    # Ages outside 10-100 are almost certainly errors (e.g. a wrong birth year)
    bad_age = ~df.artist_age_when_made.between(10, 100)
    df.loc[bad_age, "artist_age_when_made"] = float("nan")

    # 7. Tidy department names --------------------------------------------------
    df["department"] = df.Department.replace(
        {"Architecture & Design - Image Archive": "Architecture & Design"})

    # 8. Keep only the columns the analysis uses --------------------------------
    df["artist_id"] = df.ConstituentID.astype(str).where(single)
    df = df.rename(columns={"ObjectID": "object_id", "Title": "title", "Artist": "artist",
                            "Classification": "classification", "Medium": "medium"})
    df = df[["object_id", "title", "artist", "artist_id", "n_artists", "single_artist", "gender", "nationality", "region",
             "artist_birth_year", "artist_death_year", "year_made", "date_acquired", "year_acquired",
             "decade_acquired", "age_at_acquisition", "artist_age_when_made", "department",
             "classification", "medium"]]

    assert df.object_id.is_unique, "Each artwork should appear once"

    if verbose:
        print("\nCleaning steps:")
        prev = None
        for step, rows in log:
            removed = "" if prev is None else f"(-{prev - rows:,})"
            print(f"  {step:<40} {rows:>8,} rows {removed}")
            prev = rows
        s = df[df.single_artist]
        print(f"\nFinal dataset: {len(df):,} artworks, {df.single_artist.mean():.1%} by a single artist")
        print(f"Creation year found for {df.year_made.notna().mean():.1%} of works")
        print(f"Gender known for {(s.gender != 'Unknown').mean():.1%} of single-artist works")
        print(f"Nationality known for {(s.nationality != 'Unknown').mean():.1%} of single-artist works")

    CLEAN_DATA.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(CLEAN_DATA, index=False)
    return df


if __name__ == "__main__":
    clean()
