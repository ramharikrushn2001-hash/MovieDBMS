
import ast
import json
import sqlite3
from pathlib import Path

import pandas as pd

# Project folders and files
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
DB_PATH = BASE_DIR / "moviedb.db"

MOVIES_FILE = DATA_DIR / "tmdb_5000_movies.csv"
CREDITS_FILE = DATA_DIR / "tmdb_5000_credits.csv"


def parse_json(value):
    """Convert CSV JSON text into a Python list."""
    if pd.isna(value) or not str(value).strip():
        return []

    try:
        result = json.loads(value)
        return result if isinstance(result, list) else []
    except (json.JSONDecodeError, TypeError):
        try:
            result = ast.literal_eval(value)
            return result if isinstance(result, list) else []
        except (ValueError, SyntaxError):
            return []


def main():
    # Check that the CSV files exist
    if not MOVIES_FILE.exists():
        raise FileNotFoundError(
            f"Missing file: {MOVIES_FILE}"
        )

    if not CREDITS_FILE.exists():
        raise FileNotFoundError(
            f"Missing file: {CREDITS_FILE}"
        )

    movies_df = pd.read_csv(MOVIES_FILE)
    credits_df = pd.read_csv(CREDITS_FILE)

    required_columns = {
        "id",
        "title",
        "release_date",
        "overview",
        "genres",
        "vote_average",
        "vote_count",
        "popularity",
        "original_language",
    }

    missing = required_columns - set(movies_df.columns)

    if missing:
        raise ValueError(
            f"Missing columns in movies CSV: {missing}"
        )

    # Read cast names from credits CSV
    credits_map = {}

    if {"movie_id", "cast"}.issubset(credits_df.columns):
        for _, row in credits_df.iterrows():
            try:
                tmdb_id = int(row["movie_id"])
            except (ValueError, TypeError):
                continue

            cast_list = parse_json(row["cast"])

            names = [
                person.get("name", "")
                for person in cast_list[:5]
                if isinstance(person, dict)
            ]

            credits_map[tmdb_id] = ", ".join(
                name for name in names if name
            )

    # Connect to the existing database
    con = sqlite3.connect(DB_PATH)
    con.execute("PRAGMA foreign_keys = ON")

    try:
        cur = con.cursor()

        # Add missing columns without deleting existing data
        columns = {
            row[1]
            for row in cur.execute(
                "PRAGMA table_info(movies)"
            )
        }

        new_columns = {
            "tmdb_id": "INTEGER",
            "poster_path": "TEXT",
            "vote_average": "REAL",
            "vote_count": "INTEGER",
            "popularity": "REAL",
            "original_language": "TEXT",
            "cast_names": "TEXT",
        }

        for name, definition in new_columns.items():
            if name not in columns:
                cur.execute(
                    f"ALTER TABLE movies ADD COLUMN "
                    f"{name} {definition}"
                )

        # Prevent duplicate TMDB IDs
        cur.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS
            idx_movies_tmdb_id
            ON movies(tmdb_id)
            WHERE tmdb_id IS NOT NULL
        """)

        imported = 0

        for _, row in movies_df.iterrows():
            try:
                tmdb_id = int(row["id"])
            except (ValueError, TypeError):
                continue

            title = str(row["title"]).strip()

            if not title or title.lower() == "nan":
                continue

            release_date = (
                str(row["release_date"])
                if pd.notna(row["release_date"])
                else ""
            )

            year = None

            if (
                len(release_date) >= 4
                and release_date[:4].isdigit()
            ):
                year = int(release_date[:4])

            overview = (
                str(row["overview"])
                if pd.notna(row["overview"])
                else ""
            )

            try:
                vote_average = float(row["vote_average"])
            except (ValueError, TypeError):
                vote_average = 0.0

            try:
                vote_count = int(row["vote_count"])
            except (ValueError, TypeError):
                vote_count = 0

            try:
                popularity = float(row["popularity"])
            except (ValueError, TypeError):
                popularity = 0.0

            language = (
                str(row["original_language"])
                if pd.notna(row["original_language"])
                else ""
            )

            cast_names = credits_map.get(tmdb_id, "")

            # First, look for an existing TMDB ID
            cur.execute(
                "SELECT movie_id FROM movies WHERE tmdb_id = ?",
                (tmdb_id,),
            )
            found = cur.fetchone()

            # Reuse a sample movie with the same title and year
            if not found:
                cur.execute("""
                    SELECT movie_id
                    FROM movies
                    WHERE LOWER(title) = LOWER(?)
                      AND year IS ?
                    ORDER BY movie_id
                    LIMIT 1
                """, (title, year))

                found = cur.fetchone()

            if found:
                local_id = found[0]

                cur.execute("""
                    UPDATE movies
                    SET title = ?,
                        year = ?,
                        description = ?,
                        tmdb_id = ?,
                        vote_average = ?,
                        vote_count = ?,
                        popularity = ?,
                        original_language = ?,
                        cast_names = ?
                    WHERE movie_id = ?
                """, (
                    title,
                    year,
                    overview,
                    tmdb_id,
                    vote_average,
                    vote_count,
                    popularity,
                    language,
                    cast_names,
                    local_id,
                ))

            else:
                cur.execute("""
                    INSERT INTO movies (
                        title,
                        year,
                        description,
                        tmdb_id,
                        vote_average,
                        vote_count,
                        popularity,
                        original_language,
                        cast_names
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    title,
                    year,
                    overview,
                    tmdb_id,
                    vote_average,
                    vote_count,
                    popularity,
                    language,
                    cast_names,
                ))

                local_id = cur.lastrowid

            # Import movie genres
            for genre in parse_json(row["genres"]):
                if not isinstance(genre, dict):
                    continue

                genre_name = str(
                    genre.get("name", "")
                ).strip()

                if not genre_name:
                    continue

                cur.execute("""
                    INSERT OR IGNORE INTO genres (genre_name)
                    VALUES (?)
                """, (genre_name,))

                cur.execute(
                    "SELECT genre_id FROM genres "
                    "WHERE genre_name = ?",
                    (genre_name,),
                )

                genre_result = cur.fetchone()

                if genre_result:
                    cur.execute("""
                        INSERT OR IGNORE INTO movie_genres
                            (movie_id, genre_id)
                        VALUES (?, ?)
                    """, (local_id, genre_result[0]))

            imported += 1

        con.commit()

        total = cur.execute(
            "SELECT COUNT(*) FROM movies"
        ).fetchone()[0]

        tmdb_total = cur.execute(
            "SELECT COUNT(*) FROM movies "
            "WHERE tmdb_id IS NOT NULL"
        ).fetchone()[0]

        print("\nImport completed successfully!")
        print(f"Rows processed: {imported}")
        print(f"Total movies in database: {total}")
        print(f"Movies with TMDB IDs: {tmdb_total}")
        print(f"Database: {DB_PATH}")

    except Exception:
        con.rollback()
        raise

    finally:
        con.close()


if __name__ == "__main__":
    main()
