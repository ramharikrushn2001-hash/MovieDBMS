
import sqlite3
import pandas as pd
import streamlit as st

from database import (
    init_database,
    seed_sample_data,
    get_connection,
    add_movie,
    update_movie,
    delete_movie,
    add_rating,
)

st.set_page_config(
    page_title="MovieDBMS",
    page_icon="🎬",
    layout="wide"
)

init_database()
seed_sample_data()

st.title("🎬 MovieDBMS")
st.caption("Advanced Database Management System Mini Project")

page = st.sidebar.radio(
    "Navigation",
    [
        "Dashboard",
        "Movie Catalog",
        "Add Movie",
        "Update / Delete",
        "Ratings",
        "SQL Analytics",
        "Database Schema",
    ]
)


def read_query(sql, params=()):
    with get_connection() as con:
        return pd.read_sql_query(sql, con, params=params)


def get_movie_genres(movie_id):
    rows = read_query(
        """SELECT g.genre_name
           FROM genres g
           JOIN movie_genres mg ON g.genre_id = mg.genre_id
           WHERE mg.movie_id = ?
           ORDER BY g.genre_name""",
        (movie_id,)
    )
    return rows["genre_name"].tolist()


if page == "Dashboard":
    st.header("Dashboard")

    counts = read_query("""
        SELECT
          (SELECT COUNT(*) FROM movies) AS movies,
          (SELECT COUNT(*) FROM users) AS users,
          (SELECT COUNT(*) FROM ratings) AS ratings,
          (SELECT COUNT(*) FROM genres) AS genres
    """).iloc[0]

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Movies", int(counts["movies"]))
    c2.metric("Total Users", int(counts["users"]))
    c3.metric("Total Ratings", int(counts["ratings"]))
    c4.metric("Total Genres", int(counts["genres"]))

    st.subheader("Top Rated Movies")

    top = read_query("""
        SELECT m.title,
               ROUND(AVG(r.rating), 2) AS avg_rating,
               COUNT(r.rating) AS rating_count
        FROM movies m
        JOIN ratings r ON m.movie_id = r.movie_id
        GROUP BY m.movie_id, m.title
        HAVING COUNT(r.rating) >= 1
        ORDER BY avg_rating DESC, rating_count DESC, m.title
        LIMIT 10
    """)

    st.dataframe(top, use_container_width=True, hide_index=True)

    st.subheader("Movie Collection")
    recent = read_query("""
        SELECT movie_id, title, year, description
        FROM movies
        ORDER BY movie_id DESC
        LIMIT 10
    """)
    st.dataframe(recent, use_container_width=True, hide_index=True)




elif page == "Movie Catalog":
    st.header("🎬 Movie Catalog")
    st.caption("Browse, search and filter movies in your database.")

    # Search
    search = st.text_input(
        "🔍 Search movie by title",
        placeholder="Enter a movie name..."
    )

    # Genre filter
    genre_options = read_query(
        "SELECT genre_name FROM genres ORDER BY genre_name"
    )["genre_name"].tolist()

    selected_genres = st.multiselect(
        "Filter by genre",
        genre_options
    )

    # Rating filter and sorting
    c1, c2 = st.columns(2)

    with c1:
        min_rating = st.slider(
            "Minimum TMDB Rating",
            min_value=0.0,
            max_value=10.0,
            value=0.0,
            step=0.5
        )

    with c2:
        sort_option = st.selectbox(
            "Sort movies by",
            [
                "Title (A-Z)",
                "Highest TMDB Rating",
                "Most Popular",
                "Latest Release"
            ]
        )

    # Fetch movie details
    sql = """
        SELECT
            m.movie_id,
            m.title,
            m.year,
            m.description,
            m.poster_path,
            GROUP_CONCAT(DISTINCT g.genre_name) AS genres,
            m.vote_average AS tmdb_rating,
            m.vote_count,
            m.popularity,
            m.original_language,
            m.cast_names,
            ROUND(AVG(r.rating), 2) AS user_rating,
            COUNT(DISTINCT r.rating_id) AS rating_count
        FROM movies m
        LEFT JOIN movie_genres mg
            ON m.movie_id = mg.movie_id
        LEFT JOIN genres g
            ON mg.genre_id = g.genre_id
        LEFT JOIN ratings r
            ON m.movie_id = r.movie_id
        WHERE m.title LIKE ?
    """

    params = [f"%{search}%"]

    # Apply selected genre filter
    if selected_genres:
        placeholders = ",".join(
            "?" for _ in selected_genres
        )

        sql += f"""
            AND EXISTS (
                SELECT 1
                FROM movie_genres mg2
                JOIN genres g2
                    ON mg2.genre_id = g2.genre_id
                WHERE mg2.movie_id = m.movie_id
                  AND g2.genre_name IN ({placeholders})
            )
        """
        params.extend(selected_genres)

    # Apply minimum TMDB rating
    sql += """
        AND COALESCE(m.vote_average, 0) >= ?
        GROUP BY
            m.movie_id,
            m.title,
            m.year,
            m.description,
            m.poster_path,
            m.vote_average,
            m.vote_count,
            m.popularity,
            m.original_language,
            m.cast_names
    """

    params.append(min_rating)

    # Sorting
    if sort_option == "Highest TMDB Rating":
        sql += " ORDER BY m.vote_average DESC, m.title ASC"
    elif sort_option == "Most Popular":
        sql += " ORDER BY m.popularity DESC, m.title ASC"
    elif sort_option == "Latest Release":
        sql += " ORDER BY m.year DESC, m.title ASC"
    else:
        sql += " ORDER BY m.title ASC"

    catalog = read_query(sql, tuple(params))
    # Build poster image URLs when a poster path exists
    if not catalog.empty:
        catalog["poster_url"] = catalog["poster_path"].apply(
            lambda path: (
                str(path).strip()
                if pd.notna(path)
                and str(path).strip().startswith(("https://", "http://"))
                else (
                    "https://image.tmdb.org/t/p/w185" + str(path).strip()
                    if pd.notna(path) and str(path).strip()
                    else None
                )
            )
        )

# Build poster image URLs when a poster path exists

    # Summary
    st.write(f"🎞️ Movies found: {len(catalog):,}")

    # Display poster and movie details in a table
    if catalog.empty:
        st.info("No movies found. Try changing your search or filters.")
    else:
        display_columns = [
            "poster_url",
            "title",
            "year",
            "genres",
            "tmdb_rating",
            "vote_count",
            "user_rating",
            "rating_count",
            "popularity",
            "original_language",
            "cast_names",
            "description"
        ]

        display_data = catalog[display_columns].rename(
            columns={
                "poster_url": "Poster",
                "title": "Movie Title",
                "year": "Release Year",
                "genres": "Genres",
                "tmdb_rating": "TMDB Rating / 10",
                "vote_count": "TMDB Vote Count",
                "user_rating": "Your App's Average Rating / 5",
                "rating_count": "App Rating Count",
                "popularity": "Popularity",
                "original_language": "Language Code",
                "cast_names": "Cast",
                "description": "Description"
            }
        )

        st.dataframe(
            display_data,
            use_container_width=True,
            hide_index=True,
            height=600,
            column_config={
                "Poster": st.column_config.ImageColumn(
                    "Poster",
                    help="Movie poster image"
                ),
                "Description": st.column_config.TextColumn(
                    "Description",
                    width="large"
                ),
                "Movie Title": st.column_config.TextColumn(
                    "Movie Title",
                    width="medium"
                ),
                "Cast": st.column_config.TextColumn(
                    "Cast",
                    width="medium"
                )
            }
        )

        # Allow filtered results to be downloaded
        csv_data = display_data.to_csv(index=False).encode("utf-8")

        st.download_button(
            "⬇️ Download Movie Catalog as CSV",
            data=csv_data,
            file_name="movie_catalog.csv",
            mime="text/csv"
        )


elif page == "Add Movie":
    st.header("Add a New Movie")

    with st.form("add_movie_form"):
        title = st.text_input("Movie title *")
        year = st.number_input(
            "Release year", min_value=1888, max_value=2100,
            value=2020
        )
        description = st.text_area("Description")
        genres_text = st.text_input(
            "Genres (comma-separated)",
            placeholder="Action, Drama, Sci-Fi"
        )

        submitted = st.form_submit_button("Add Movie")

    if submitted:
        if not title.strip():
            st.error("Please enter a movie title.")
        else:
            genres = [
                x.strip() for x in genres_text.split(",") if x.strip()
            ]
            try:
                movie_id = add_movie(
                    title, int(year), description, genres
                )
                st.success(f"Movie added successfully! ID: {movie_id}")
            except sqlite3.IntegrityError as e:
                st.error(f"Database error: {e}")
            except ValueError as e:
                st.error(str(e))


elif page == "Update / Delete":
    st.header("Update or Delete a Movie")

    movies = read_query(
        "SELECT movie_id, title, year, description FROM movies ORDER BY title"
    )

    if movies.empty:
        st.info("No movies available.")
    else:
        movie_ids = movies["movie_id"].astype(int).tolist()
        selected_id = st.selectbox(
            "Choose movie ID",
            movie_ids,
            format_func=lambda x: (
                f"{x} — {movies.loc[movies.movie_id == x, 'title'].iloc[0]}"
            )
        )

        selected = movies[movies.movie_id == selected_id].iloc[0]
        current_genres = get_movie_genres(int(selected_id))

        st.subheader("Edit Movie")

        with st.form("update_movie_form"):
            new_title = st.text_input(
                "Title", value=str(selected["title"])
            )
            old_year = selected["year"]
            new_year = st.number_input(
                "Year",
                min_value=1888,
                max_value=2100,
                value=int(old_year) if pd.notna(old_year) else 2020
            )
            new_description = st.text_area(
                "Description",
                value=str(selected["description"] or "")
            )
            new_genres = st.text_input(
                "Genres (comma-separated)",
                value=", ".join(current_genres)
            )

            update_clicked = st.form_submit_button("Save Changes")

        if update_clicked:
            try:
                update_movie(
                    int(selected_id),
                    new_title,
                    int(new_year),
                    new_description,
                    [g.strip() for g in new_genres.split(",") if g.strip()]
                )
                st.success("Movie updated successfully.")
            except (ValueError, sqlite3.IntegrityError) as e:
                st.error(str(e))

        st.divider()
        st.subheader("Delete Movie")
        st.warning("Deleting a movie also deletes its linked ratings and genre relationships.")

        confirm = st.checkbox(
            f"I confirm deletion of movie ID {selected_id}"
        )

        if st.button("Delete Selected Movie", type="primary"):
            if not confirm:
                st.error("Please confirm before deleting.")
            else:
                delete_movie(int(selected_id))
                st.success("Movie deleted.")
                st.rerun()


elif page == "Ratings":
    st.header("Movie Ratings")

    movies = read_query(
        "SELECT movie_id, title FROM movies ORDER BY title"
    )

    if movies.empty:
        st.info("Add a movie before recording ratings.")
    else:
        with st.form("rating_form"):
            username = st.text_input("Username")
            movie_id = st.selectbox(
                "Select movie",
                movies["movie_id"].astype(int).tolist(),
                format_func=lambda x: (
                    f"{x} — {movies.loc[movies.movie_id == x, 'title'].iloc[0]}"
                )
            )
            rating = st.slider(
                "Rating", min_value=0.5, max_value=5.0,
                value=4.0, step=0.5
            )
            submitted = st.form_submit_button("Save Rating")

        if submitted:
            try:
                add_rating(username, int(movie_id), float(rating))
                st.success(
                    "Rating saved. A new rating from the same user "
                    "for the same movie updates the existing rating."
                )
            except (ValueError, sqlite3.IntegrityError) as e:
                st.error(str(e))

    st.subheader("All Ratings")

    ratings_df = read_query("""
        SELECT u.username, m.title, r.rating
        FROM ratings r
        JOIN users u ON r.user_id = u.user_id
        JOIN movies m ON r.movie_id = m.movie_id
        ORDER BY m.title, u.username
    """)

    st.dataframe(ratings_df, use_container_width=True, hide_index=True)


elif page == "SQL Analytics":
    st.header("SQL Analytics")
    st.write("These reports use SQL queries on the SQLite database.")

    st.subheader("1. Average Rating and Number of Ratings")

    q1 = read_query("""
        SELECT m.title,
               ROUND(AVG(r.rating), 2) AS average_rating,
               COUNT(r.rating) AS total_ratings
        FROM movies m
        LEFT JOIN ratings r ON m.movie_id = r.movie_id
        GROUP BY m.movie_id, m.title
        ORDER BY average_rating DESC, total_ratings DESC
    """)
    st.dataframe(q1, use_container_width=True, hide_index=True)

    st.subheader("2. Genre-wise Movie Count")

    q2 = read_query("""
        SELECT g.genre_name, COUNT(mg.movie_id) AS movie_count
        FROM genres g
        LEFT JOIN movie_genres mg ON g.genre_id = mg.genre_id
        GROUP BY g.genre_id, g.genre_name
        ORDER BY movie_count DESC, g.genre_name
    """)
    st.dataframe(q2, use_container_width=True, hide_index=True)

    st.subheader("3. Movies Rated Above Average")

    q3 = read_query("""
        SELECT m.title, ROUND(AVG(r.rating), 2) AS average_rating
        FROM movies m
        JOIN ratings r ON m.movie_id = r.movie_id
        GROUP BY m.movie_id, m.title
        HAVING AVG(r.rating) > (
            SELECT AVG(rating) FROM ratings
        )
        ORDER BY average_rating DESC
    """)
    st.dataframe(q3, use_container_width=True, hide_index=True)

    st.subheader("4. Movies and Their Genres — JOIN")

    q4 = read_query("""
        SELECT m.title,
               GROUP_CONCAT(g.genre_name, ', ') AS genres
        FROM movies m
        LEFT JOIN movie_genres mg ON m.movie_id = mg.movie_id
        LEFT JOIN genres g ON mg.genre_id = g.genre_id
        GROUP BY m.movie_id, m.title
        ORDER BY m.title
    """)
    st.dataframe(q4, use_container_width=True, hide_index=True)

    st.subheader("5. Indexes")

    indexes = read_query("""
        SELECT name, tbl_name, sql
        FROM sqlite_master
        WHERE type = 'index'
          AND name NOT LIKE 'sqlite_%'
        ORDER BY tbl_name, name
    """)
    st.dataframe(indexes, use_container_width=True, hide_index=True)

elif page == "Recommendations":
    st.header("Movie Recommendations")

    movies = read_query(
        "SELECT movie_id, title FROM movies ORDER BY title"
    )

    if movies.empty:
        st.info("Please add movies first.")
    else:
        selected_id = st.selectbox(
            "Choose a movie",
            movies["movie_id"].astype(int).tolist(),
            format_func=lambda x: (
                f"{x} — "
                f"{movies.loc[movies.movie_id == x, 'title'].iloc[0]}"
            )
        )

        sql = """
        SELECT
            m.movie_id,
            m.title,
            GROUP_CONCAT(DISTINCT g.genre_name) AS shared_genres,
            ROUND(AVG(r.rating), 2) AS average_rating,
            COUNT(DISTINCT mg.genre_id) AS matching_genres
        FROM movies m
        JOIN movie_genres mg ON m.movie_id = mg.movie_id
        JOIN genres g ON mg.genre_id = g.genre_id
        LEFT JOIN ratings r ON m.movie_id = r.movie_id
        WHERE mg.genre_id IN (
            SELECT genre_id
            FROM movie_genres
            WHERE movie_id = ?
        )
        AND m.movie_id != ?
        GROUP BY m.movie_id, m.title
        ORDER BY matching_genres DESC,
                 average_rating DESC,
                 m.title
        LIMIT 5
        """

        recommendations = read_query(
            sql, (int(selected_id), int(selected_id))
        )

        st.subheader("Recommended Movies")

        if recommendations.empty:
            st.info("No similar movies found.")
        else:
            st.dataframe(
                recommendations,
                use_container_width=True,
                hide_index=True
            )

    
    st.header("Movie Recommendations")
    st.write(
        "SQL-based recommendations using shared genres "
        "and average movie ratings."
    )

    movies = read_query(
        "SELECT movie_id, title FROM movies ORDER BY title"
    )

    if movies.empty:
        st.info("Add movies before requesting recommendations.")
    else:
        selected_id = st.selectbox(
            "Choose a movie",
            movies["movie_id"].astype(int).tolist(),
            format_func=lambda x: (
                f"{x} — "
                f"{movies.loc[movies.movie_id == x, 'title'].iloc[0]}"
            ),
            key="recommend_movie"
        )

        recommendations = read_query("""
            SELECT
                m.movie_id,
                m.title,
                GROUP_CONCAT(DISTINCT g.genre_name) AS shared_genres,
                ROUND(AVG(r.rating), 2) AS average_rating,
                COUNT(DISTINCT mg.genre_id) AS matching_genres
            FROM movies m
            JOIN movie_genres mg
                ON m.movie_id = mg.movie_id
            JOIN genres g
                ON mg.genre_id = g.genre_id
            WHERE mg.genre_id IN (
                SELECT genre_id
                FROM movie_genres
                WHERE movie_id = ?
            )
            AND m.movie_id != ?
            LEFT JOIN ratings r
                ON m.movie_id = r.movie_id
            GROUP BY m.movie_id, m.title
            ORDER BY matching_genres DESC,
                     average_rating DESC,
                     m.title
            LIMIT 5
        """, (int(selected_id), int(selected_id)))

        st.subheader("Recommended Movies")

        if recommendations.empty:
            st.info("No similar movies found. Add more movies and genres.")
        else:
            st.dataframe(
                recommendations,
                use_container_width=True,
                hide_index=True
            )

elif page == "Database Schema":
    st.header("Database Schema")
    st.write("Relational database design with primary and foreign keys.")

    schema = {
        "movies": "movie_id (PK), title, year, description",
        "genres": "genre_id (PK), genre_name (UNIQUE)",
        "movie_genres": "movie_id (PK, FK), genre_id (PK, FK)",
        "users": "user_id (PK), username (UNIQUE)",
        "ratings": "rating_id (PK), user_id (FK), movie_id (FK), rating",
    }

    for table, columns in schema.items():
        with st.expander(table):
            st.code(columns)

    st.subheader("Relationship Explanation")
    st.markdown("""
    - One movie can belong to many genres.
    - One genre can be associated with many movies.
    - The movie_genres junction table represents this many-to-many relationship.
    - A user can rate multiple movies.
    - Each user can have one current rating per movie.
    - Foreign keys maintain referential integrity.
    """)

    st.subheader("Database Integrity Check")
    with get_connection() as con:
        fk_issues = con.execute(
            "PRAGMA foreign_key_check"
        ).fetchall()

    if fk_issues:
        st.error("Foreign key issues found.")
        st.write([tuple(row) for row in fk_issues])
    else:
        st.success("No foreign key violations found.")
