"""Answer the five project questions and save a chart for each to images/."""

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mtick
import pandas as pd
import seaborn as sns

IMAGES = Path(__file__).parent / "images"
sns.set_theme(style="whitegrid")
ACCENT, GREY = "#c2410c", "#9aa5b1"
MIN_WORKS_PER_DECADE = 1000   # the 1920s (only 1929: 9 works) are too small to compare


def save(fig, name: str) -> None:
    IMAGES.mkdir(exist_ok=True)
    fig.tight_layout()
    fig.savefig(IMAGES / name, dpi=120)
    plt.close(fig)


def header(text: str) -> None:
    print("\n" + "-" * 60)
    print(text)
    print("-" * 60)


def decades_with_enough_data(df: pd.DataFrame) -> list[int]:
    counts = df.decade_acquired.value_counts()
    return sorted(counts[counts >= MIN_WORKS_PER_DECADE].index)


def decade_labels(decades) -> list[str]:
    return [f"{d}s" if d < 2020 else "2020s*" for d in decades]


# --------------------------------------------------------------------------- #
# Q1. Women artists over time
# --------------------------------------------------------------------------- #
def women_over_time(df: pd.DataFrame) -> None:
    header("Q1. What share of the collection is by women?")
    known = df[df.single_artist & df.gender.isin(["Male", "Female", "Non-binary"])]
    print(f"Works by women: {(known.gender == 'Female').mean():.1%} of {len(known):,} single-artist works "
          f"with known gender")

    # Works vs. artists: one prolific artist can add hundreds of works
    artists = known.drop_duplicates("artist_id")
    print(f"Artists who are women: {(artists.gender == 'Female').mean():.1%} of {len(artists):,} artists")

    decades = decades_with_enough_data(known)
    share = (known[known.decade_acquired.isin(decades)]
             .groupby("decade_acquired")["gender"].apply(lambda g: (g == "Female").mean() * 100))
    print("\nShare of acquired works by women, by decade acquired:")
    print(share.round(1).rename(index=dict(zip(decades, decade_labels(decades)))).to_string())

    fig, ax = plt.subplots(figsize=(9, 4.5))
    ax.plot(decade_labels(share.index), share.values, marker="o", lw=2.5, color=ACCENT)
    for x, y in zip(decade_labels(share.index), share.values):
        ax.annotate(f"{y:.0f}%", (x, y), textcoords="offset points", xytext=(0, 9), ha="center", fontsize=9)
    ax.axhline(50, ls="--", color=GREY)
    ax.text(0, 51.5, "Equal representation (50%)", color="dimgray", fontsize=9)
    ax.set(title="Women's share of MoMA acquisitions rose from under 10% to about 1 in 4",
           xlabel="Decade acquired (*2020-2026 so far)", ylabel="Works by women", ylim=(0, 58))
    ax.yaxis.set_major_formatter(mtick.PercentFormatter())
    save(fig, "q1_women_share_by_decade.png")


# --------------------------------------------------------------------------- #
# Q2. Nationality and region
# --------------------------------------------------------------------------- #
def nationality(df: pd.DataFrame) -> None:
    header("Q2. Which nationalities dominate? Is the collection becoming more global?")
    known = df[df.single_artist & (df.nationality != "Unknown")]

    top = known.nationality.value_counts().head(10)
    top_share = top / len(known) * 100
    print("Top 10 nationalities (% of single-artist works with known nationality):")
    print(top_share.round(1).to_string())
    print(f"\nAmerican + French together: {top_share.iloc[:2].sum():.1f}%")

    fig, ax = plt.subplots(figsize=(8, 4.5))
    colours = [ACCENT if i < 2 else GREY for i in range(len(top))]
    ax.barh(top.index[::-1], top_share.values[::-1], color=colours[::-1])
    for i, v in enumerate(top_share.values[::-1]):
        ax.text(v + 0.5, i, f"{v:.1f}%", va="center", fontsize=9)
    ax.set(title="American and French artists make up over 60% of the collection",
           xlabel="Share of works (%)", xlim=(0, top_share.max() * 1.15))
    save(fig, "q2_top_nationalities.png")

    # Share of works from outside North America and Western Europe, by decade
    decades = decades_with_enough_data(known)
    known = known[known.decade_acquired.isin(decades)]
    region_share = pd.crosstab(known.decade_acquired, known.region, normalize="index") * 100
    order = ["North America", "Western Europe", "Eastern Europe", "Latin America & Caribbean",
             "Asia & Oceania", "Africa & Middle East", "Other"]
    region_share = region_share.reindex(columns=[c for c in order if c in region_share.columns])
    outside = 100 - region_share[["North America", "Western Europe"]].sum(axis=1)
    print("\nShare of works from OUTSIDE North America and Western Europe, by decade acquired:")
    print(outside.round(1).rename(index=dict(zip(decades, decade_labels(decades)))).to_string())

    fig, ax = plt.subplots(figsize=(9, 5))
    palette = ["#cbd2d9", "#9aa5b1", "#7b8794", "#c2410c", "#ea580c", "#fb923c", "#fed7aa"]
    ax.stackplot(decade_labels(region_share.index), region_share.T.values, labels=region_share.columns,
                 colors=palette[:len(region_share.columns)])
    ax.set(title="Artists from outside North America and Western Europe: a growing slice",
           xlabel="Decade acquired (*2020-2026 so far)", ylabel="Share of works", ylim=(0, 100))
    ax.yaxis.set_major_formatter(mtick.PercentFormatter())
    ax.legend(loc="upper left", bbox_to_anchor=(1.01, 1), frameon=False, fontsize=9)
    save(fig, "q2_region_share_by_decade.png")


# --------------------------------------------------------------------------- #
# Q3. Women by department
# --------------------------------------------------------------------------- #
def women_by_department(df: pd.DataFrame) -> None:
    header("Q3. Does representation of women differ by department?")
    known = df[df.single_artist & df.gender.isin(["Male", "Female", "Non-binary"])]
    t = (known.groupby("department")["gender"]
         .agg(women=lambda g: (g == "Female").mean() * 100, works="size")
         .sort_values("women"))
    print(t.assign(women=t.women.round(1).astype(str) + "%").to_string())

    overall = (known.gender == "Female").mean() * 100
    fig, ax = plt.subplots(figsize=(8, 4.5))
    ax.barh(t.index, t.women, color=[ACCENT if v == t.women.max() else GREY for v in t.women])
    for i, (v, n) in enumerate(zip(t.women, t.works)):
        ax.text(v + 0.5, i, f"{v:.0f}%  ({n:,} works)", va="center", fontsize=9,
                bbox=dict(facecolor="white", edgecolor="none", pad=1))
    ax.axvline(overall, ls="--", color="dimgray", zorder=0)
    ax.text(overall, -0.85, f"All departments {overall:.0f}%", fontsize=9, color="dimgray", ha="center")
    ax.set(title="Women are best represented in Media and Performance",
           xlabel="Works by women (%)", xlim=(0, t.women.max() * 1.45), ylim=(-1.2, len(t) - 0.5))
    save(fig, "q3_women_by_department.png")


# --------------------------------------------------------------------------- #
# Q4. How old is art when MoMA acquires it?
# --------------------------------------------------------------------------- #
def age_at_acquisition(df: pd.DataFrame) -> None:
    header("Q4. How old is a work when MoMA acquires it?")
    a = df.dropna(subset=["age_at_acquisition"])
    print(f"Median age at acquisition: {a.age_at_acquisition.median():.0f} years")
    print(f"Acquired within 5 years of being made: {(a.age_at_acquisition <= 5).mean():.1%}")
    print(f"Acquired 50+ years after being made: {(a.age_at_acquisition >= 50).mean():.1%}")

    decades = decades_with_enough_data(a)
    by_decade = a[a.decade_acquired.isin(decades)].groupby("decade_acquired").age_at_acquisition.median()
    print("\nMedian age at acquisition, by decade acquired:")
    print(by_decade.rename(index=dict(zip(decades, decade_labels(decades)))).to_string())

    fig, axes = plt.subplots(1, 2, figsize=(12, 4.5), gridspec_kw={"width_ratios": [1.2, 1]})
    ax = axes[0]
    ax.hist(a.age_at_acquisition.clip(upper=120), bins=60, color=GREY)
    ax.axvline(a.age_at_acquisition.median(), color=ACCENT, lw=2)
    ax.text(a.age_at_acquisition.median() + 2, ax.get_ylim()[1] * 0.9,
            f"Median {a.age_at_acquisition.median():.0f} years", color=ACCENT)
    ax.set(title="Most works are acquired young, with a long tail",
           xlabel="Years between creation and acquisition (120+ grouped)", ylabel="Works")
    ax = axes[1]
    ax.plot(decade_labels(by_decade.index), by_decade.values, marker="o", lw=2.5, color=ACCENT)
    ax.set(title="Since 2000, MoMA has been buying older work",
           xlabel="Decade acquired (*2020-2026 so far)", ylabel="Median age (years)", ylim=(0, None))
    ax.tick_params(axis="x", rotation=45)
    save(fig, "q4_age_at_acquisition.png")


# --------------------------------------------------------------------------- #
# Q5. How old are artists when they make the work?
# --------------------------------------------------------------------------- #
def artist_age(df: pd.DataFrame) -> None:
    header("Q5. How old are artists when they make the works MoMA collects?")
    a = df.dropna(subset=["artist_age_when_made"])
    print(f"Median artist age: {a.artist_age_when_made.median():.0f} "
          f"(based on {len(a):,} works with a known birth year and creation year)")
    by_gender = a[a.gender.isin(["Male", "Female"])].groupby("gender").artist_age_when_made.median()
    print("Median artist age by gender:", by_gender.to_dict())

    fig, ax = plt.subplots(figsize=(9, 4.5))
    ax.hist(a.artist_age_when_made, bins=range(10, 101, 2), color=GREY)
    median = a.artist_age_when_made.median()
    ax.axvline(median, color=ACCENT, lw=2)
    ax.text(median + 1.5, ax.get_ylim()[1] * 0.9, f"Median {median:.0f}", color=ACCENT)
    ax.set(title="Most collected works were made by artists in their 30s and 40s",
           xlabel="Artist's age when the work was made", ylabel="Works")
    save(fig, "q5_artist_age.png")


def run(df: pd.DataFrame) -> None:
    print("\n" + "=" * 60)
    print("ANALYSIS")
    print("=" * 60)
    women_over_time(df)
    nationality(df)
    women_by_department(df)
    age_at_acquisition(df)
    artist_age(df)
    print(f"\nCharts saved to {IMAGES.name}/")
