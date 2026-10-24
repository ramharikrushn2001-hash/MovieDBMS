
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent / "moviedb.db"


def get_connection():
    con = sqlite3.connect(DB_PATH, timeout=10)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    return con


def init_database():
    with get_connection() as con:
        con.executescript("""
        CREATE TABLE IF NOT EXISTS movies (
            movie_id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            year INTEGER,
            description TEXT DEFAULT '',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS genres (
            genre_id INTEGER PRIMARY KEY AUTOINCREMENT,
            genre_name TEXT NOT NULL UNIQUE
        );

        CREATE TABLE IF NOT EXISTS movie_genres (
            movie_id INTEGER NOT NULL,
            genre_id INTEGER NOT NULL,
            PRIMARY KEY (movie_id, genre_id),
            FOREIGN KEY (movie_id)
                REFERENCES movies(movie_id) ON DELETE CASCADE,
            FOREIGN KEY (genre_id)
                REFERENCES genres(genre_id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE
        );

        CREATE TABLE IF NOT EXISTS ratings (
            rating_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            movie_id INTEGER NOT NULL,
            rating REAL NOT NULL CHECK(rating >= 0.5 AND rating <= 5),
            FOREIGN KEY (user_id)
                REFERENCES users(user_id) ON DELETE CASCADE,
            FOREIGN KEY (movie_id)
                REFERENCES movies(movie_id) ON DELETE CASCADE,
            UNIQUE (user_id, movie_id)
        );

        CREATE INDEX IF NOT EXISTS idx_movies_title
        ON movies(title);

        CREATE INDEX IF NOT EXISTS idx_ratings_movie
        ON ratings(movie_id);
        """)


def seed_sample_data():
    sample_movies = [
        ("Inception", 2010, "A science fiction thriller", ["Sci-Fi", "Action"]),
        ("Interstellar", 2014, "A space exploration drama", ["Sci-Fi", "Drama"]),
        ("The Dark Knight", 2008, "A superhero crime thriller", ["Action", "Crime"]),
        ("Toy Story", 1995, "An animated adventure", ["Animation", "Family"]),
        ("Finding Nemo", 2003, "An underwater animated adventure", ["Animation", "Family"]),
        ("The Matrix", 1999, "A science fiction action film", ["Sci-Fi", "Action"]),
        ("Titanic", 1997, "A romantic drama", ["Romance", "Drama"]),
        ("Jurassic Park", 1993, "A dinosaur adventure", ["Adventure", "Sci-Fi"]),
    ]

    with get_connection() as con:
        count = con.execute(
            "SELECT COUNT(*) FROM movies"
        ).fetchone()[0]

        if count > 0:
            return

        for title, year, description, genres in sample_movies:
            cur = con.execute(
                """INSERT INTO movies (title, year, description)
                   VALUES (?, ?, ?)""",
                (title, year, description)
            )
            movie_id = cur.lastrowid

            for genre in genres:
                con.execute(
                    "INSERT OR IGNORE INTO genres (genre_name) VALUES (?)",
                    (genre,)
                )
                genre_id = con.execute(
                    "SELECT genre_id FROM genres WHERE genre_name = ?",
                    (genre,)
                ).fetchone()["genre_id"]

                con.execute(
                    """INSERT INTO movie_genres (movie_id, genre_id)
                       VALUES (?, ?)""",
                    (movie_id, genre_id)
                )

        con.execute(
            "INSERT OR IGNORE INTO users (username) VALUES (?)",
            ("demo_user",)
        )
        user_id = con.execute(
            "SELECT user_id FROM users WHERE username = ?",
            ("demo_user",)
        ).fetchone()["user_id"]

        ratings = [
            ("Inception", 5.0),
            ("Interstellar", 4.5),
            ("The Dark Knight", 4.5),
            ("Toy Story", 4.0),
            ("Finding Nemo", 4.5),
            ("The Matrix", 5.0),
            ("Titanic", 4.0),
            ("Jurassic Park", 4.5),
        ]

        for title, rating in ratings:
            movie_id = con.execute(
                "SELECT movie_id FROM movies WHERE title = ?",
                (title,)
            ).fetchone()["movie_id"]

            con.execute(
                """INSERT OR IGNORE INTO ratings
                   (user_id, movie_id, rating)
                   VALUES (?, ?, ?)""",
                (user_id, movie_id, rating)
            )


def add_movie(title, year, description, genres):
    title = title.strip()
    if not title:
        raise ValueError("Movie title is required.")

    with get_connection() as con:
        cur = con.execute(
            """INSERT INTO movies (title, year, description)
               VALUES (?, ?, ?)""",
            (title, year, description.strip())
        )
        movie_id = cur.lastrowid

        for name in genres:
            name = name.strip()
            if not name:
                continue

            con.execute(
                "INSERT OR IGNORE INTO genres (genre_name) VALUES (?)",
                (name,)
            )
            genre_id = con.execute(
                "SELECT genre_id FROM genres WHERE genre_name = ?",
                (name,)
            ).fetchone()["genre_id"]

            con.execute(
                """INSERT INTO movie_genres (movie_id, genre_id)
                   VALUES (?, ?)""",
                (movie_id, genre_id)
            )

    return movie_id


def update_movie(movie_id, title, year, description, genres):
    title = title.strip()
    if not title:
        raise ValueError("Movie title is required.")

    with get_connection() as con:
        cur = con.execute(
            """UPDATE movies
               SET title = ?, year = ?, description = ?
               WHERE movie_id = ?""",
            (title, year, description.strip(), movie_id)
        )

        if cur.rowcount == 0:
            raise ValueError("Movie not found.")

        con.execute(
            "DELETE FROM movie_genres WHERE movie_id = ?",
            (movie_id,)
        )

        for name in genres:
            name = name.strip()
            if not name:
                continue

            con.execute(
                "INSERT OR IGNORE INTO genres (genre_name) VALUES (?)",
                (name,)
            )
            genre_id = con.execute(
                "SELECT genre_id FROM genres WHERE genre_name = ?",
                (name,)
            ).fetchone()["genre_id"]

            con.execute(
                """INSERT INTO movie_genres (movie_id, genre_id)
                   VALUES (?, ?)""",
                (movie_id, genre_id)
            )


def delete_movie(movie_id):
    with get_connection() as con:
        con.execute(
            "DELETE FROM movies WHERE movie_id = ?",
            (movie_id,)
        )


def add_rating(username, movie_id, rating):
    username = username.strip()
    if not username:
        raise ValueError("Username is required.")

    with get_connection() as con:
        con.execute(
            "INSERT OR IGNORE INTO users (username) VALUES (?)",
            (username,)
        )
        user_id = con.execute(
            "SELECT user_id FROM users WHERE username = ?",
            (username,)
        ).fetchone()["user_id"]

        con.execute(
            """INSERT INTO ratings (user_id, movie_id, rating)
               VALUES (?, ?, ?)
               ON CONFLICT(user_id, movie_id)
               DO UPDATE SET rating = excluded.rating""",
            (user_id, movie_id, rating)
        )
