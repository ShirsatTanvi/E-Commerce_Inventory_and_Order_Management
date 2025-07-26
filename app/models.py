from fastapi import FastAPI
from database import Base
from datetime import date
from sqlalchemy import Column, Integer, String, Float, Date

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True)
    email = Column(String(100), unique=True, index=True)
    role = Column(String(20))
    # gender = Column(String(10))
    password = Column(String(100))  # Store hashed password

class Product(Base):
    __tablename__ = "products"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    desc = Column(String(255), nullable=False)
    quantity = Column(Integer, default=0)
    price = Column(Float, nullable=False)
    date = Column(Date, default=date.today)
