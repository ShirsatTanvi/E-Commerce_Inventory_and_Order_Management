from fastapi import FastAPI, Request, Form
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from database import Base, engine, SessionLocal
from models import User
from sqlalchemy.orm import Session
from passlib.context import CryptContext
from fastapi.responses import HTMLResponse,RedirectResponse

Base.metadata.create_all(bind=engine)

app = FastAPI()
templates = Jinja2Templates(directory="templates")
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Mount the static files directory
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/", response_class=HTMLResponse)
def read_root(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

@app.post("/login", response_class=HTMLResponse)
def login(username: str = Form(...), password: str = Form(...)):
    db: Session = SessionLocal()
    user = db.query(User).filter(User.username == username).first()
    
    if user and pwd_context.verify(password, user.password):
        # User is authenticated
        return RedirectResponse(url="/dashboard", status_code=303)  # Redirect to a dashboard or home page
    else:
        return {"error": "Invalid username or password"}
    # Implement login logic here
    return RedirectResponse(url="/", status_code=303)

@app.get("/register", response_class=HTMLResponse)
def register_page(request: Request):
    return templates.TemplateResponse("register.html", {"request": request})

@app.post("/register", response_class=HTMLResponse)
def register(
    username: str = Form(...), 
    email: str = Form(...), 
    role: str = Form(...), 
    # gender: str = Form(...), 
    password: str = Form(...), 
    confirm_password: str = Form(...)
    ):
    if password != confirm_password:
        return {"error": "Passwords do not match"}
    
    hashed_password = pwd_context.hash(password)
    
    db: Session = SessionLocal()
    try:
        new_user = User(username=username, email=email, role=role, password=hashed_password)
        db.add(new_user)
        db.commit()  
        db.refresh(new_user)
    except Exception as e:
        db.rollback()  # Rollback in case of error
        return {"error": str(e)}
    finally:
        db.close()
    
    return RedirectResponse(url="/login", status_code=303)

# dashboard
@app.get("/dashboard", response_class=HTMLResponse)
def dashboard(request: Request):
    return templates.TemplateResponse("dashboard.html", {"request": request})
