from projektstyring.backend.database.connection import Base, engine

# Importerer alle database-modeller, så SQLAlchemy registrerer dem.
import projektstyring.backend.db_models


def create_tables():
    Base.metadata.create_all(bind=engine)


if __name__ == "__main__":
    create_tables()
    print("Database-tabeller oprettet.")