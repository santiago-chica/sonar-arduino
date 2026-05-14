from datetime import datetime
from sqlalchemy import create_engine, Column, Integer, Float, DateTime
from sqlalchemy.orm import declarative_base, sessionmaker

DATABASE_URL = "sqlite:///./sonar_data.db"

engine = create_engine(
    DATABASE_URL, connect_args={"check_same_thread": False}
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

class SonarEntry(Base):
    __tablename__ = "sonar_entries"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    distance = Column(Float, nullable=False)
    angle = Column(Integer, nullable=False)
    timestamp = Column(DateTime, default=datetime.now)

Base.metadata.create_all(bind=engine) 