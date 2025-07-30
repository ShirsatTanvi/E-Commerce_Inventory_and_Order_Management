from fastapi import FastAPI, Request, Form, Depends, Query
from fastapi.responses import RedirectResponse, HTMLResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func, desc, or_, cast, String
from sqlalchemy.orm import Session
from database import Base, engine, SessionLocal
from models import User, Product, Order, OrderItem, CartItem
import models
from fastapi.staticfiles import StaticFiles
from passlib.context import CryptContext
from datetime import date

# Binding with database
Base.metadata.create_all(bind=engine)

app = FastAPI()

# Connects Templates
templates = Jinja2Templates(directory="templates")


pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Mount the static files directory
app.mount("/static", StaticFiles(directory="static"), name="static")

# session 
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def get_user_context(username: str, db: Session):
    user_obj = db.query(User).filter(User.username == username).first()
    return {"username": user_obj.username, "role": user_obj.role}


# main route
@app.get("/", response_class=HTMLResponse)
def read_root(request: Request):
    return templates.TemplateResponse(request, "login.html", {})

# login route
@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    return templates.TemplateResponse(request, "login.html", {})

@app.post("/login", response_class=HTMLResponse)
def login(request: Request, username: str = Form(...), password: str = Form(...)):
    db: Session = SessionLocal()
    user = db.query(User).filter(User.username == username).first()

    if user is None:
        return templates.TemplateResponse(request, "login.html", {"error": "Username does not exist"})

    if not pwd_context.verify(password, user.password):
        return templates.TemplateResponse(request,"login.html", {"error": "Incorrect password"})

    return RedirectResponse(url=f"/dashboard?user={user.username}", status_code=303)

# logout route
@app.post("/logout", name="logout")
def logout(request: Request):
    return RedirectResponse(url="/", status_code=302)

# registration route
@app.get("/register", response_class=HTMLResponse)
def register_page(request: Request):
    return templates.TemplateResponse(request, "register.html", {})

@app.post("/register", response_class=HTMLResponse)
def register(request: Request, username: str = Form(...), email: str = Form(...), role: str = Form(...), password: str = Form(...), confirm_password: str = Form(...)):

    if password != confirm_password:
        return templates.TemplateResponse(request, "register.html", {"error": "Passwords do not match"})
    
    hashed_password = pwd_context.hash(password)
    db: Session = SessionLocal()
    existing_user = db.query(User).filter((User.username == username) | (User.email == email)).first()

    if existing_user:
        return templates.TemplateResponse(request, "register.html", {"error": "User or email already exists"})

    try:
        new_user = User(username=username, email=email, role=role, password=hashed_password)
        db.add(new_user)
        db.commit()
        db.refresh(new_user)
    except Exception as e:
        db.rollback()
        return templates.TemplateResponse(request, "register.html", {"error": str(e)})
    finally:
        db.close()

    return RedirectResponse(url="/login", status_code=303)

# Dashboard route -> role based access
@app.get("/dashboard", response_class=HTMLResponse)
def dashboard(request: Request, user: str, db: Session = Depends(get_db)):
    context = get_user_context(user, db)
    
    # Return if Admin login
    if context["role"] == "admin":
        total_products = db.query(func.count(Product.id)).scalar()
        today = date.today()
        today_orders = db.query(OrderItem).join(Order).filter(Order.date == today).all()
        todays_sales = sum(item.quantity * item.product.price for item in today_orders)
        low_stock_items = db.query(Product).filter(Product.quantity < 5).all()

        recent_activities = []
        latest_orders = db.query(Order).order_by(desc(Order.date)).limit(5).all()
        for order in latest_orders:
            for item in order.items:
                recent_activities.append(f"Sold {item.quantity} units of {item.product.subcategory} on {order.date.strftime('%d %B %Y')}")
        recent_products = db.query(Product).order_by(desc(Product.date)).limit(5).all()
        for product in recent_products:
            recent_activities.append(f"Added new product: {product.subcategory}")

        return templates.TemplateResponse(request,"dashboard.html", {
            "username": context["username"],
            "role": context["role"],
            "total_products": total_products,
            "todays_sales": todays_sales,
            "low_stock_count": len(low_stock_items),
            "recent_activities": recent_activities[:5]
        })
    
    # Returns if Customer Login
    elif context["role"] == "customer":
        user_obj = db.query(User).filter(User.username == user).first()
        today = date.today()
        today_orders = db.query(OrderItem).join(Order).filter(Order.user_id == user_obj.id, Order.date == today).all()
        todays_total = sum(item.quantity * item.product.price for item in today_orders)
        todays_products = [item.product.subcategory for item in today_orders]

        all_orders = db.query(OrderItem).join(Order).filter(Order.user_id == user_obj.id).all()
        total_quantity = sum(item.quantity for item in all_orders)
        total_products = len({item.product_id for item in all_orders})

        recent_purchases = []
        latest_orders = db.query(Order).filter(Order.user_id == user_obj.id).order_by(desc(Order.date)).limit(5).all()
        for order in latest_orders:
            for item in order.items:
                recent_purchases.append(f"You purchased {item.quantity} x {item.product.subcategory} on {order.date.strftime('%d %B %Y')} (Status: {order.status})")

        return templates.TemplateResponse(request, "dashboard.html", {
            "username": context["username"],
            "role": context["role"],
            "total_quantity": total_quantity,
            "total_products": total_products,
            "todays_total": todays_total,
            "todays_products": todays_products,
            "recent_purchases": recent_purchases
        })

# View products route -> role based access
@app.get("/view-products")
def view_products(request: Request, search: str = "", user: str = Query(...), message: str = "", db: Session = Depends(get_db)):
    context = get_user_context(user, db)

    if search:
        search_pattern = f"%{search}%"
        products = db.query(Product).filter(
            or_(
                cast(Product.id, String).ilike(search_pattern),
                Product.category.ilike(search_pattern),
                Product.subcategory.ilike(search_pattern),
                Product.brand.ilike(search_pattern),
                Product.desc.ilike(search_pattern),
                cast(Product.price, String).ilike(search_pattern),
                cast(Product.quantity, String).ilike(search_pattern),
                cast(Product.date, String).ilike(search_pattern)
            )
        ).all()
    else:
        products = db.query(Product).all()

    return templates.TemplateResponse("view_products.html", {
        "request": request,
        "products": products,
        "search": search,
        "username": context["username"],
        "role": context["role"],
        "message": message
    })

# Edit product -> Role: Admin 
@app.get("/edit-product/{product_id}")
def edit_product_form(product_id: int, request: Request, user: str = Query(...), db: Session = Depends(get_db)):
    context = get_user_context(user, db)
    product = db.query(models.Product).filter(models.Product.id == product_id).first()
    return templates.TemplateResponse(request, "edit_product.html", {"product": product, "username": context["username"], "role": context["role"]})

@app.post("/edit-product/{product_id}")
def update_product(
    product_id: int,
    user: str = Query(...),  # ✅ Fix: Get user from query param
    category: str = Form(...),
    subcategory: str = Form(...),
    brand: str = Form(...),
    desc: str = Form(...),
    quantity: int = Form(...),
    price: float = Form(...),
    db: Session = Depends(get_db)
):
    product = db.query(models.Product).filter(models.Product.id == product_id).first()
    product.category = category
    product.subcategory = subcategory
    product.brand = brand
    product.desc = desc
    product.quantity = quantity
    product.price = price
    db.commit()
    return RedirectResponse(f"/view-products?user={user}", status_code=303)

# Delete Product -> Role: Admin
@app.post("/delete-product/{product_id}")
def delete_product(
    request: Request,   
    product_id: int,
    user: str = Form(...),
    db: Session = Depends(get_db)
):
    product = db.query(Product).filter(Product.id == product_id ).first()
    if not product:
        return templates.TemplateResponse(request, "message.html", {
            "message": "Product not found."
        })

    # Get all related order items
    order_items = db.query(OrderItem).filter(OrderItem.product_id == product_id).all()

    # Check if any order linked to this product is not delivered
    for item in order_items:
        order = db.query(Order).filter(Order.id == item.order_id).first()
        if order and order.status != "Delivered":
            return RedirectResponse(
            f"/view-products?user={user}&message=Cannot+delete:+Order+in+progress.",
            status_code=303
        )

    # All linked orders are delivered, safe to delete order items
    for item in order_items:
        db.delete(item)

        # Optional: Check if the order now has 0 items, then delete the order too
        remaining_items = db.query(OrderItem).filter(OrderItem.order_id == item.order_id).count()
        if remaining_items == 1:  # current item is the last one
            order = db.query(Order).filter(Order.id == item.order_id).first()
            if order:
                db.delete(order)

    # Finally, delete the product
    db.delete(product)
    db.commit()
    return RedirectResponse(f"/view-products?user={user}", status_code=303)

# Add new product -> Role: Admin
@app.get("/add-product", response_class=HTMLResponse)
def add_product(request: Request, user: str, db: Session = Depends(get_db)):
    context = get_user_context(user, db)
    return templates.TemplateResponse(request, "add_product.html", {"username": context["username"], "role": context["role"]})

@app.post("/add-product", response_class=HTMLResponse)
def save_product(
    request: Request,
    user: str = Form(...),
    category: str = Form(...),
    subcategory: str = Form(...),
    brand: str = Form(...),
    productDesc: str = Form(...),
    quantity: int = Form(...),
    price: float = Form(...)
):
    db: Session = SessionLocal()
    try:
        new_product = Product(category=category, subcategory=subcategory, brand=brand, desc=productDesc, quantity=quantity, price=price)
        db.add(new_product)
        db.commit()
        db.refresh(new_product)
        message = "Product added successfully!"
        context = get_user_context(user, db)
        return templates.TemplateResponse(request, "add_product.html", { "username": context["username"], "role": context["role"], "success": message
        })
    except Exception as e:
        db.rollback()
        context = get_user_context(user, db)
        return templates.TemplateResponse(request, "add_product.html", { "username": context["username"], "role": context["role"], "error": str(e)
        })
    finally:
        db.close()

# Restock Product -> Role: Admin
@app.get("/restock-products", response_class=HTMLResponse)
def restock_products_page(request: Request, user: str = Query(...), db: Session = Depends(get_db)):
    context = get_user_context(user, db)
    products = db.query(Product).all()
    return templates.TemplateResponse(request, "restock_products.html", {
        "username": context["username"],
        "role": context["role"],
        "products": products
    })

@app.post("/restock-products", response_class=HTMLResponse)
def restock_product(
    request: Request,
    user: str = Form(...),
    product_id: int = Form(...),
    added_quantity: int = Form(...),
    db: Session = Depends(get_db)
):
    context = get_user_context(user, db)
    product = db.query(Product).filter(Product.id == product_id).first()
    if product:
        product.quantity += added_quantity
        db.commit()
        message = f"Successfully restocked {added_quantity} units of '{product.subcategory}'"
    else:
        message = "Product not found"

    products = db.query(Product).all()
    return templates.TemplateResponse(request, "restock_products.html", {
        "username": context["username"],
        "role": context["role"],
        "products": products,
        "message": message
    })

# Manage Orders -> Role: Admin
@app.get("/admin-orders", response_class=HTMLResponse)
def view_all_orders(request: Request, user: str, db: Session = Depends(get_db)):
    context = get_user_context(user, db)
    orders = db.query(Order).filter(Order.status != "Delivered").all()
    return templates.TemplateResponse(request, "admin_orders.html", {
        "orders": orders,
        "username": context["username"],
        "role": context["role"]
    })

# Update status route -> Admin
@app.post("/update-order-status/{order_id}", response_class=HTMLResponse)
def update_order_status(
    order_id: int,
    status: str = Form(...),
    user: str = Form(...),  # Accept user from the form
    db: Session = Depends(get_db)
):
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        return {"error": "Order not found"}
    order.status = status
    db.commit()
    return RedirectResponse(f"/admin-orders?user={user}", status_code=303)

# Sales history route -> Role: Admin 
@app.get("/sales-history", response_class=HTMLResponse)
def sales_history(request: Request, user: str, db: Session = Depends(get_db)):
    context = get_user_context(user, db)
    orders = db.query(Order).filter(Order.status == "Delivered").all()
    return templates.TemplateResponse(request, "sales_history.html", {
        "orders": orders,
        "username": context["username"],
        "role": context["role"]
    })
 
# Browse Product Route -> Role: Customer
@app.get("/browse-products", response_class=HTMLResponse)
def browse_products(request: Request, user: str, db: Session = Depends(get_db)):
    context = get_user_context(user, db)
    products = db.query(Product).all()
    return templates.TemplateResponse(request, "browse_products.html", { "products": products, "username": context["username"], "role": context["role"]})

# Add to cart route -> Role: Customer
@app.post("/add-to-cart", response_class=HTMLResponse)
def add_to_cart(user: str = Form(...), product_id: int = Form(...), quantity: int = Form(...), db: Session = Depends(get_db)):
    user_obj = db.query(User).filter(User.username == user).first()
    product = db.query(Product).filter(Product.id == product_id).first()

    if not user_obj or not product:
        return RedirectResponse(f"/browse-products?user={user}", status_code=303)

    existing_item = db.query(CartItem).filter(CartItem.user_id == user_obj.id, CartItem.product_id == product.id).first()

    if existing_item:
        existing_item.quantity += quantity
    else:
        new_cart_item = CartItem(user_id=user_obj.id, product_id=product.id, quantity=quantity)
        db.add(new_cart_item)

    db.commit()
    return RedirectResponse(f"/browse-products?user={user}", status_code=303)

# My cart view route -> Role: Customer
@app.get("/my-cart", response_class=HTMLResponse)
def my_cart(request: Request, user: str = Query(...), db: Session = Depends(get_db)):
    context = get_user_context(user, db)
    user_obj = db.query(User).filter(User.username == user).first()
    cart_items = db.query(CartItem).filter(CartItem.user_id == user_obj.id).all()

    subtotal = sum(item.quantity * item.product.price for item in cart_items)
    gst = round(subtotal * 0.18, 2)
    shipping = 50.0 if cart_items else 0.0
    total_amount = round(subtotal + gst + shipping, 2)

    return templates.TemplateResponse(request, "my_cart.html", {
        "cart_items": cart_items,
        "username": context["username"],
        "role": context["role"],
        "subtotal": subtotal,
        "gst": gst,
        "shipping": shipping,
        "total_amount": total_amount
    })

# Remove from cart route -> Role: Customer
@app.post("/remove-from-cart/{cart_id}")
def remove_from_cart(cart_id: int, user: str = Form(...), db: Session = Depends(get_db)):
    item = db.query(CartItem).filter(CartItem.id == cart_id).first()
    if item:
        db.delete(item)
        db.commit()
    return RedirectResponse(f"/my-cart?user={user}", status_code=303)

# Proceed to buy route -> Role: Customer
@app.post("/checkout", response_class=HTMLResponse)
def checkout(request: Request, user: str = Form(...), db: Session = Depends(get_db)):
    context = get_user_context(user, db)
    return templates.TemplateResponse(request, "message.html", {
        "message": "Proceeding to checkout... (To be implemented)",
        "redirect_url": f"/my-cart?user={user}"
    })

# View Bill Route -> Role: Customer
@app.post("/bill", response_class=HTMLResponse)
def show_bill(request: Request, user: str = Form(...), db: Session = Depends(get_db)):
    context = get_user_context(user, db)
    user_obj = db.query(User).filter(User.username == user).first()
    cart_items = db.query(CartItem).filter(CartItem.user_id == user_obj.id).all()

    subtotal = sum(item.quantity * item.product.price for item in cart_items)
    gst = round(subtotal * 0.18, 2)
    shipping = 50.0 if cart_items else 0.0
    total_amount = round(subtotal + gst + shipping, 2)

    return templates.TemplateResponse(request, "bill.html", {
        "username": context["username"],
        "role": context["role"],
        "cart_items": cart_items,
        "subtotal": subtotal,
        "gst": gst,
        "shipping": shipping,
        "total_amount": total_amount
    })

# confirm buy route -> Role: Customer
@app.post("/confirm-buy", response_class=HTMLResponse)
def confirm_buy(request: Request, user: str = Form(...), db: Session = Depends(get_db)):
    # Get user
    user_obj = db.query(User).filter(User.username == user).first()
    if not user_obj:
        return templates.TemplateResponse(request, "message.html", {
            "message": "User not found.",
            "redirect_url": "/login"
        })

    # Get cart items
    cart_items = db.query(CartItem).filter(CartItem.user_id == user_obj.id).all()
    if not cart_items:
        return templates.TemplateResponse(request, "message.html", {
            "message": "Your cart is empty.",
            "redirect_url": f"/my-cart?user={user}"
        })

    # Create order
    new_order = Order(user_id=user_obj.id)
    db.add(new_order)
    db.commit()
    db.refresh(new_order)

    # Move items from cart to order_items
    for item in cart_items:
        order_item = OrderItem(order_id=new_order.id, product_id=item.product.id, quantity=item.quantity)
        db.add(order_item)
        item.product.quantity -= item.quantity  # reduce stock

    # Clear cart
    for item in cart_items:
        db.delete(item)

    db.commit()

    return RedirectResponse(f"/my-cart?user={user}", status_code=303)

# Order history shown route -> Role: Customer
@app.get("/order-history", response_class=HTMLResponse)
def order_history(request: Request, user: str = Query(...), db: Session = Depends(get_db)):
    context = get_user_context(user, db)
    user_obj = db.query(User).filter(User.username == user).first()

    if not user_obj:
        return templates.TemplateResponse(request, "message.html", {"message": f"User '{user}' not found!", "redirect_url": "/login"})


    orders = db.query(Order).filter(Order.user_id == user_obj.id).all()
    return templates.TemplateResponse(request, "order_history.html", { "orders": orders, "username": context["username"], "role": context["role"]})


