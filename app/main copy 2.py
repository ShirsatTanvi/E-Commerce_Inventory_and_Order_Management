from fastapi import FastAPI, Request, Form, Depends, Query
from fastapi.responses import RedirectResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func, desc
from sqlalchemy.orm import Session
from database import Base, engine, SessionLocal
from models import User, Product, Order, OrderItem
import models
from fastapi.staticfiles import StaticFiles
from passlib.context import CryptContext
from datetime import date

Base.metadata.create_all(bind=engine)

app = FastAPI()
templates = Jinja2Templates(directory="templates")
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Mount the static files directory
app.mount("/static", StaticFiles(directory="static"), name="static")

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def get_user_context(username: str, db: Session):
    user_obj = db.query(User).filter(User.username == username).first()
    return {"username": user_obj.username, "role": user_obj.role}

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
    return response

@app.get("/register", response_class=HTMLResponse)
def register_page(request: Request):
    return templates.TemplateResponse("register.html", {"request": request})

@app.post("/register", response_class=HTMLResponse)
def register(request: Request, username: str = Form(...), email: str = Form(...), role: str = Form(...), password: str = Form(...), confirm_password: str = Form(...)):
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
def admin_dashboard(request: Request, user: str, db: Session = Depends(get_db)):
    context = get_user_context(user, db)
    total_products = db.query(func.count(Product.id)).scalar()

    today = date.today()
    today_orders = db.query(OrderItem).join(Order).filter(Order.date == today).all()
    todays_sales = sum(item.quantity * item.product.price for item in today_orders)
    low_stock_items = db.query(Product).filter(Product.quantity < 5).all()

    recent_activities = []
    latest_orders = db.query(Order).order_by(desc(Order.date)).limit(5).all()
    for order in latest_orders:
        for item in order.items:
            recent_activities.append(f"Sold {item.quantity} units of {item.product.name} on {order.date.strftime('%d %B %Y')}")

    recent_products = db.query(Product).order_by(desc(Product.date)).limit(5).all()
    for product in recent_products:
        recent_activities.append(f"Added new product: {product.name}")

    return templates.TemplateResponse("admin_dashboard.html", {
        "request": request,
        "username": context["username"],
        "role": context["role"],
        "total_products": total_products,
        "todays_sales": todays_sales,
        "low_stock_count": len(low_stock_items),
        "recent_activities": recent_activities[:5]
    })

@app.get("/customer-dashboard", response_class=HTMLResponse)
def customer_dashboard(request: Request, user: str, db: Session = Depends(get_db)):
    context = get_user_context(user, db)
    user_obj = db.query(User).filter(User.username == user).first()

    today = date.today()
    today_orders = db.query(OrderItem).join(Order).filter(Order.user_id == user_obj.id, Order.date == today).all()
    todays_total = sum(item.quantity * item.product.price for item in today_orders)
    todays_products = [item.product.name for item in today_orders]

    all_orders = db.query(OrderItem).join(Order).filter(Order.user_id == user_obj.id).all()
    total_quantity = sum(item.quantity for item in all_orders)
    total_products = len({item.product_id for item in all_orders})

    recent_purchases = []
    latest_orders = db.query(Order).filter(Order.user_id == user_obj.id).order_by(desc(Order.date)).limit(5).all()
    for order in latest_orders:
        for item in order.items:
            recent_purchases.append(f"You purchased {item.quantity} x {item.product.name} on {order.date.strftime('%d %B %Y')} (Status: {order.status})")

    return templates.TemplateResponse("customer_dashboard.html", {
        "request": request,
        "username": context["username"],
        "role": context["role"],
        "total_quantity": total_quantity,
        "total_products": total_products,
        "todays_total": todays_total,
        "todays_products": todays_products,
        "recent_purchases": recent_purchases
    })


@app.get("/view-products")
def view_products(request: Request, search: str = "", user: str = Query(...), db: Session = Depends(get_db)):
    context = get_user_context(user, db)
    products = db.query(models.Product).filter(models.Product.name.contains(search)).all() if search else db.query(models.Product).all()
    return templates.TemplateResponse("view_products.html", {
        "request": request,
        "products": products,
        "search": search,
        "username": context["username"],
        "role": context["role"]
    })

@app.get("/edit-product/{product_id}")
def edit_product_form(product_id: int, request: Request, user: str = Query(...), db: Session = Depends(get_db)):
    context = get_user_context(user, db)
    product = db.query(models.Product).filter(models.Product.id == product_id).first()
    return templates.TemplateResponse("edit_product.html", {"request": request, "product": product, "username": context["username"], "role": context["role"]})

@app.post("/edit-product/{product_id}")
def update_product(product_id: int, name: str = Form(...), desc: str = Form(...), quantity: int = Form(...), price: float = Form(...), db: Session = Depends(get_db)):
    product = db.query(models.Product).filter(models.Product.id == product_id).first()
    product.name = name
    product.desc = desc
    product.quantity = quantity
    product.price = price
    db.commit()
    return RedirectResponse("/view-products", status_code=303)

@app.post("/delete-product/{product_id}")
def delete_product(product_id: int, db: Session = Depends(get_db)):
    product = db.query(models.Product).filter(models.Product.id == product_id).first()
    db.delete(product)
    db.commit()
    return RedirectResponse("/view-products", status_code=303)

@app.get("/add-product", response_class=HTMLResponse)
def add_product(request: Request, user: str, db: Session = Depends(get_db)):
    context = get_user_context(user, db)
    return templates.TemplateResponse("add_product.html", {"request": request, "username": context["username"], "role": context["role"]})

@app.post("/add-product", response_class=HTMLResponse)
def save_product(request: Request, user: str = Form(...), productName: str = Form(...), productDesc: str = Form(...), quantity: int = Form(...), price: float = Form(...)):
    db: Session = SessionLocal()
    try:
        new_product = Product(name=productName, desc=productDesc, quantity=quantity, price=price)
        db.add(new_product)
        db.commit()
        db.refresh(new_product)
        message = "Product added successfully!"
        context = get_user_context(user, db)
        return templates.TemplateResponse("add_product.html", {"request": request, "username": context["username"], "role": context["role"], "success": message})
    except Exception as e:
        db.rollback()
        context = get_user_context(user, db)
        return templates.TemplateResponse("add_product.html", {"request": request, "username": context["username"], "role": context["role"], "error": str(e)})
    finally:
        db.close()

@app.get("/admin-orders", response_class=HTMLResponse)
def view_all_orders(request: Request, user: str, db: Session = Depends(get_db)):
    context = get_user_context(user, db)
    orders = db.query(Order).all()
    return templates.TemplateResponse("admin_orders.html", {"request": request, "orders": orders, "username": context["username"], "role": context["role"]})

@app.post("/update-order-status/{order_id}", response_class=HTMLResponse)
def update_order_status(order_id: int, status: str = Form(...), db: Session = Depends(get_db)):
    order = db.query(Order).filter(Order.id == order_id).first()
    order.status = status
    db.commit()
    return RedirectResponse("/admin-orders?user=admin", status_code=303)

# @app.get("/customer-dashboard", response_class=HTMLResponse)
# def customer_dashboard(request: Request, user: str, db: Session = Depends(get_db)):
#     context = get_user_context(user, db)
#     return templates.TemplateResponse("customer_dashboard.html", {"request": request, "username": context["username"], "role": context["role"]})

@app.get("/browse-products", response_class=HTMLResponse)
def browse_products(request: Request, user: str, db: Session = Depends(get_db)):
    context = get_user_context(user, db)
    products = db.query(Product).all()
    return templates.TemplateResponse("browse_products.html", {"request": request, "products": products, "username": context["username"], "role": context["role"]})

@app.post("/place-order", response_class=HTMLResponse)
def place_order(request: Request, user: str = Form(...), product_id: int = Form(...), quantity: int = Form(...), db: Session = Depends(get_db)):
    user_obj = db.query(User).filter(User.username == user).first()
    product = db.query(Product).filter(Product.id == product_id).first()

    context = get_user_context(user, db)

    if not user_obj:
        return templates.TemplateResponse("browse_products.html", {"request": request, "username": context["username"], "role": context["role"], "error": f"User '{user}' not found"})

    if not product:
        return templates.TemplateResponse("browse_products.html", {"request": request, "username": context["username"], "role": context["role"], "error": f"Product ID {product_id} not found"})

    if product.quantity < quantity:
        return templates.TemplateResponse("browse_products.html", {"request": request, "username": context["username"], "role": context["role"], "error": f"Only {product.quantity} units available"})

    order = Order(user_id=user_obj.id)
    db.add(order)
    db.commit()
    db.refresh(order)

    order_item = OrderItem(order_id=order.id, product_id=product.id, quantity=quantity)
    db.add(order_item)
    product.quantity -= quantity
    db.commit()

    return templates.TemplateResponse("browse_products.html", {"request": request, "username": context["username"], "role": context["role"], "success": "Order placed successfully!"})

@app.get("/order-history", response_class=HTMLResponse)
def order_history(request: Request, user: str = Query(...), db: Session = Depends(get_db)):
    context = get_user_context(user, db)
    user_obj = db.query(User).filter(User.username == user).first()

    if not user_obj:
        return templates.TemplateResponse("message.html", {"request": request, "message": f"User '{user}' not found!", "redirect_url": "/login"})

    orders = db.query(Order).filter(Order.user_id == user_obj.id).all()
    return templates.TemplateResponse("order_history.html", {"request": request, "orders": orders, "username": context["username"], "role": context["role"]})
