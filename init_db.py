
from database import init_database, seed_sample_data, DB_PATH

init_database()
seed_sample_data()

print("Database initialized successfully!")
print(f"Database location: {DB_PATH}")
