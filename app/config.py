import os

class Settings:
    DATABASE_URL = os.getenv("DATABASE_URL", "mysql+pymysql://root:redhat@localhost/ecommerce_db")
settings = Settings()