import os

class Settings:
    # DATABASE_URL = os.getenv("DATABASE_URL", "mysql+pymysql://root:tanvi.2002@localhost/ecommerce_db")
    DATABASE_URL = "mysql+pymysql://root:tanvi.2002@host.docker.internal:3306/ecommerce_db"
    
settings = Settings()