
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy import Column, Integer, String, JSON

# Define minimal model just for checking
Base = declarative_base()

class Team(Base):
    __tablename__ = "teams"
    id = Column(String, primary_key=True)
    name = Column(String)
    member_ids = Column(JSON)

DATABASE_URL = "sqlite:///data/debate.db"
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)

def check_teams():
    session = SessionLocal()
    try:
        teams = session.query(Team).all()
        print(f"Total Teams found: {len(teams)}")
        for t in teams:
            print(f"Team: {t.name}, Members: {t.member_ids}")
            
        if len(teams) == 0:
            print("WARNING: No teams found in database.")
    except Exception as e:
        print(f"Error checking teams: {e}")
    finally:
        session.close()

if __name__ == "__main__":
    check_teams()
