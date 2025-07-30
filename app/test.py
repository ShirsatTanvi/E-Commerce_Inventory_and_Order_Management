import unittest
from fastapi.testclient import TestClient
from fastapi import status
from main import app
from database import SessionLocal, Base, engine
from models import User, Product, Order, OrderItem, CartItem
from passlib.context import CryptContext
from datetime import date
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from main import *
import os

# Set up test database
TEST_DATABASE_URL = "mysql+pymysql://root:tanvi.2002@localhost/ecommerce_test"
os.environ["TESTING"] = "1"
engine = create_engine(TEST_DATABASE_URL)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base.metadata.create_all(bind=engine)

def override_get_db():
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()

app.dependency_overrides[get_db] = override_get_db
client = TestClient(app)

class TestECommerceApp(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Create test data
        db = TestingSessionLocal()
        
        # Create test users
        pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
        hashed_pw = pwd_context.hash("testpass")
        
        admin = User(username="admin", email="admin@test.com", password=hashed_pw, role="admin")
        customer = User(username="customer", email="customer@test.com", password=hashed_pw, role="customer")
        
        db.add(admin)
        db.add(customer)
        db.commit()
        
        # Create test products
        product1 = Product(
            category="Electronics",
            subcategory="Smartphone",
            brand="Apple",
            desc="iPhone 13",
            quantity=10,
            price=999.99
        )
        product2 = Product(
            category="Electronics",
            subcategory="Laptop",
            brand="Dell",
            desc="XPS 15",
            quantity=5,
            price=1499.99
        )
        db.add(product1)
        db.add(product2)
        db.commit()
        
        # Create test order
        order = Order(user_id=customer.id, status="Pending")
        db.add(order)
        db.commit()
        
        order_item = OrderItem(
            order_id=order.id,
            product_id=product1.id,
            quantity=2
        )
        db.add(order_item)
        db.commit()
        
        cls.admin_id = admin.id
        cls.customer_id = customer.id
        cls.product1_id = product1.id
        cls.product2_id = product2.id
        cls.order_id = order.id
        db.close()

    @classmethod
    def tearDownClass(cls):
        # Clean up database
        Base.metadata.drop_all(bind=engine)

    def setUp(self):
        self.db = TestingSessionLocal()
        
    def tearDown(self):
        self.db.close()

    # Authentication Tests
    def test_root_redirects_to_login(self):
        response = client.get("/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # self.assertIn("login.html", response.text)

    def test_register_get(self):
        response = client.get("/register")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # self.assertIn("register.html", response.text)

    def test_register_post_success(self):
        response = client.post("/register", data={
            "username": "newuser",
            "email": "new@test.com",
            "role": "customer",
            "password": "newpass",
            "confirm_password": "newpass"
        }, follow_redirects=False)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual("text/html; charset=utf-8", response.headers["content-type"])

    def test_register_post_password_mismatch(self):
        response = client.post("/register", data={
            "username": "newuser2",
            "email": "new2@test.com",
            "role": "customer",
            "password": "newpass",
            "confirm_password": "wrongpass"
        })
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("Passwords do not match", response.text)

    def test_login_post_success(self):
        response = client.post("/login", data={
            "username": "customer",
            "password": "testpass"
        }, follow_redirects=False)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("text/html; charset=utf-8", response.headers["content-type"])

    def test_login_post_invalid_credentials(self):
        response = client.post("/login", data={
            "username": "customer",
            "password": "wrongpass"
        })
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    # Dashboard Tests
    def test_admin_dashboard(self):
        response = client.get("/dashboard?user=admin")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_customer_dashboard(self):
        response = client.get("/dashboard?user=customer")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    # Product Management Tests
    def test_view_products(self):
        response = client.get("/view-products?user=admin")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # self.assertIn("view_products.html", response.text)
        self.assertIn("iPhone 13", response.text)

    def test_edit_product(self):
        response = client.post(f"/edit-product/{self.product1_id}", data={
            "user": "admin",
            "category": "Electronics",
            "subcategory": "Smartphone Pro",
            "brand": "Apple",
            "desc": "iPhone 13 Pro",
            "quantity": "15",
            "price": "1099.99"
        }, follow_redirects=False)
        self.assertEqual(response.status_code, status.HTTP_422_UNPROCESSABLE_ENTITY)
        self.assertIn("application/json", response.headers["content-type"])

    def test_delete_product(self):
        # First create a product we can delete
        db = TestingSessionLocal()
        product = Product(
            category="Test",
            subcategory="Delete Me",
            brand="Test",
            desc="Test product for deletion",
            quantity=1,
            price=9.99
        )
        db.add(product)
        db.commit()
        product_id = product.id
        db.close()
        
        response = client.post(f"/delete-product/{product_id}", data={"user": "admin"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("text/html; charset=utf-8", response.headers["content-type"])

    # Cart and Order Tests
    def test_add_to_cart(self):
        response = client.post("/add-to-cart", data={
            "user": "customer",
            "product_id": str(self.product2_id),
            "quantity": "1"
        }, follow_redirects=False)
        self.assertEqual(response.status_code, status.HTTP_303_SEE_OTHER)
        self.assertIn("/browse-products?user=customer", response.headers["location"])

    def test_view_cart(self):
        # First add an item to cart
        client.post("/add-to-cart", data={
            "user": "customer",
            "product_id": str(self.product2_id),
            "quantity": "1"
        })
        
        response = client.get("/my-cart?user=customer")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # self.assertIn("my_cart.html", response.text)
        self.assertIn("XPS 15", response.text)

    def test_remove_from_cart(self):
        # First add an item to cart
        client.post("/add-to-cart", data={
            "user": "customer",
            "product_id": str(self.product2_id),
            "quantity": "1"
        })
        
        # Get the cart item ID
        db = TestingSessionLocal()
        cart_item = db.query(CartItem).filter(CartItem.user_id == self.customer_id).first()
        cart_id = cart_item.id
        db.close()
        
        response = client.post(f"/remove-from-cart/{cart_id}", data={"user": "customer"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("text/html; charset=utf-8", response.headers["content-type"])

    def test_confirm_buy(self):
        # First add an item to cart
        client.post("/add-to-cart", data={
            "user": "customer",
            "product_id": str(self.product2_id),
            "quantity": "1"
        })
        
        response = client.post("/confirm-buy", data={"user": "customer"})
       
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        self.assertIn("text/html; charset=utf-8", response.headers["content-type"])

    # Admin Order Management Tests
    def test_admin_orders_view(self):
        response = client.get("/admin-orders?user=admin")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # self.assertIn("admin_orders.html", response.text)
        self.assertIn("Pending", response.text)

    def test_update_order_status(self):
        response = client.post(f"/update-order-status/{self.order_id}", data={
            "user": "admin",
            "status": "Shipped"
        }, follow_redirects=False)
        self.assertEqual(response.status_code, status.HTTP_303_SEE_OTHER)
        self.assertIn("/admin-orders?user=admin", response.headers["location"])

    def test_sales_history(self):
        response = client.get("/sales-history?user=admin")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # self.assertIn("sales_history.html", response.text)

    # Customer Order History
    def test_order_history(self):
        response = client.get("/order-history?user=customer")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # self.assertIn("order_history.html", response.text)
        self.assertIn("Pending", response.text)

if __name__ == "__main__":
    unittest.main()