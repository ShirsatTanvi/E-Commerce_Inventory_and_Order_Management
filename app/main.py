from fastapi import FastAPI
from database import Base, engine, SessionLocal
from models import User



Base.metadata.create_all(bind=engine)

app = FastAPI()