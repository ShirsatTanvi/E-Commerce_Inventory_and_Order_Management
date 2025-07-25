from fastapi import FastAPI
from database import Base
from sqlalchemy import Column, Integer, String

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True)
    email = Column(String(100), unique=True, index=True)
    role = Column(String(20))
    # gender = Column(String(10))
    password = Column(String(100))  # Store hashed password
