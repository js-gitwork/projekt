from projektstyring.backend.database.connection import Base, engine
from projektstyring.backend.db_models.conversation import ConversationState


def create_tables():
    Base.metadata.create_all(bind=engine)


if __name__ == "__main__":
    create_tables()
    print("Database-tabeller oprettet.")