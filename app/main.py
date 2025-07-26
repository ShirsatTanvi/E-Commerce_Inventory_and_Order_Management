from fastapi import FastAPI, Request, Form
from fastapi.responses import RedirectResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
from database import Base, engine, SessionLocal
from models import User, Product
from passlib.context import CryptContext

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
def login(request: Request, username: str = Form(...), password: str = Form(...)):
    db: Session = SessionLocal()
    user = db.query(User).filter(User.username == username).first()

    if user is None:
        return templates.TemplateResponse("login.html", {"request": request, "error": "Username does not exist"})

    if not pwd_context.verify(password, user.password):
        return templates.TemplateResponse("login.html", {"request": request, "error": "Incorrect password"})

    if user.role == "admin":
        return RedirectResponse(url=f"/admin-dashboard?user={user.username}", status_code=303)
    elif user.role == "customer":
        return RedirectResponse(url=f"/customer-dashboard?user={user.username}", status_code=303)
    else:
        return templates.TemplateResponse("login.html", {"request": request, "error": "Invalid role"})

@app.post("/logout", name="logout")
def logout(request: Request):
    response = RedirectResponse(url="/", status_code=302)
    # Optional: clear cookies/session
    return response

@app.get("/register", response_class=HTMLResponse)
def register_page(request: Request):
    return templates.TemplateResponse("register.html", {"request": request})

@app.post("/register", response_class=HTMLResponse)
def register(
    request: Request,
    username: str = Form(...), 
    email: str = Form(...), 
    role: str = Form(...), 
    # gender: str = Form(...), 
    password: str = Form(...), 
    confirm_password: str = Form(...)
):
    if password != confirm_password:
        return templates.TemplateResponse("register.html", {"request": request, "error": "Passwords do not match"})
    
    hashed_password = pwd_context.hash(password)
    db: Session = SessionLocal()
    existing_user = db.query(User).filter((User.username == username) | (User.email == email)).first()

    if existing_user:
        return templates.TemplateResponse("register.html", {"request": request, "error": "User or email already exists"})

    try:
        new_user = User(username=username, email=email, role=role, password=hashed_password)
        db.add(new_user)
        db.commit()
        db.refresh(new_user)
    except Exception as e:
        db.rollback()
        return templates.TemplateResponse("register.html", {"request": request, "error": str(e)})
    finally:
        db.close()

    return RedirectResponse(url="/login", status_code=303)

@app.get("/admin-dashboard", response_class=HTMLResponse, name="admin_dashboard")
def admin_dashboard(request: Request, user: str):
    return templates.TemplateResponse("admin_dashboard.html", {"request": request, "username": user})

# @app.get("/view-products", response_class=HTMLResponse)
# def view_products(request: Request, user: str):
#     db: Session = SessionLocal()
#     products = db.query(Product).all()  # or filter/search as needed
#     return templates.TemplateResponse("view_products.html", {
#         "request": request,
#         "username": user,
#         "products": products,
#         "search": ""
#     })

# @app.get("/view-products", response_class=HTMLResponse)
# def view_products(request: Request, user: str):
#     return templates.TemplateResponse("view_products.html", {"request": request, "username": user})


@app.get("/view-products", response_class=HTMLResponse)
def view_products(request: Request, user: str, search: str = ""):
    db: Session = SessionLocal()
    try:
        if search:
            products = db.query(Product).filter(Product.name.ilike(f"%{search}%")).all()
        else:
            products = db.query(Product).all()

        return templates.TemplateResponse("view_products.html", {
            "request": request,
            "username": user,
            "products": products,
            "search": search
        })
    finally:
        db.close()


@app.get("/add-product", response_class=HTMLResponse)
def add_product(request: Request, user: str):
    return templates.TemplateResponse("add_product.html", {"request": request, "username": user})

@app.post("/add-product", response_class=HTMLResponse)
def save_product(
    request: Request,
    user: str = Form(...),
    productName: str = Form(...),
    productDesc: str = Form(...),
    quantity: int = Form(...),
    price: float = Form(...)
):
    db: Session = SessionLocal()
    try:
        new_product = Product(
            name=productName,
            desc=productDesc,
            quantity=quantity,
            price=price
        )
        db.add(new_product)
        db.commit()
        db.refresh(new_product)
        message = "Product added successfully!"
        return templates.TemplateResponse("add_product.html", {
            "request": request,
            "username": user,
            "success": message
        })
    except Exception as e:
        db.rollback()
        return templates.TemplateResponse("add_product.html", {
            "request": request,
            "username": user,
            "error": "Error adding product: " + str(e)
        })
    finally:
        db.close()


@app.get("/customer-dashboard", response_class=HTMLResponse)
def customer_dashboard(request: Request, user: str):
    return templates.TemplateResponse("customer_dashboard.html", {"request": request, "username": user})
