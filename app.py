import eventlet
eventlet.monkey_patch()

from flask import Flask, render_template, request, redirect, session, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_socketio import SocketIO, emit, join_room
from authlib.integrations.flask_client import OAuth
from flask_mail import Mail, Message as MailMessage

from datetime import datetime
import uuid
import os

import random

def generate_otp():
    return str(random.randint(100000,999999))

# ADD THIS
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import inch

app = Flask(__name__)
app.secret_key = "supersecretkey"

# SOCKETIO
socketio = SocketIO(app, cors_allowed_origins="*")

# DATABASE
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///marketplace.db"
db = SQLAlchemy(app)

# MAIL
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = 'mprcom404@gmail.com'
app.config['MAIL_PASSWORD'] = 'lihnaqifsgzxebxm'
app.config['MAIL_DEFAULT_SENDER'] = 'mprcom404@gmail.com'

mail = Mail(app)


# =========================
# MESSAGE MODEL
# =========================

class Message(db.Model):

    id = db.Column(db.Integer, primary_key=True)

    sender_id = db.Column(db.Integer)
    receiver_id = db.Column(db.Integer)

    message = db.Column(db.Text)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)


# =========================
# SOCKET EVENTS (OUTSIDE CLASS)
# =========================

@socketio.on("join")
def handle_join(data):
    join_room(str(data["user_id"]))


@socketio.on("send_message")
def handle_message(data):

    sender = data["sender"]
    receiver = data["receiver"]
    text = data["message"]

    msg = Message(
        sender_id=sender,
        receiver_id=receiver,
        message=text
    )

    db.session.add(msg)
    db.session.commit()

    emit(
        "receive_message",
        {
            "sender": sender,
            "message": text,
            "time": datetime.utcnow().strftime("%H:%M")
        },
        room=str(receiver)
    )

    emit(
        "receive_message",
        {
            "sender": sender,
            "message": text,
            "time": datetime.utcnow().strftime("%H:%M")
        },
        room=str(sender)
    )

# -------------------------
# EMAIL FUNCTION
# -------------------------

def send_email(to, subject, body, attachment=None, filename=None):

    try:
        msg = MailMessage(
            subject=subject,
            recipients=[to],
            body=body
        )

        if attachment:
            msg.attach(
                filename,
                "application/pdf",
                attachment.read()
            )

        mail.send(msg)

    except Exception as e:
        print("Email error:", e)


# -------------------------
# INVOICE PDF GENERATOR
# -------------------------

def generate_invoice_pdf(order, product, buyer, seller, quantity=1):

    from io import BytesIO

    buffer = BytesIO()

    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=40,
        leftMargin=40,
        topMargin=40,
        bottomMargin=40
    )

    styles = getSampleStyleSheet()
    elements = []

    # -----------------------------
    # HEADER
    # -----------------------------

    elements.append(Paragraph("<b>Student Marketplace</b>", styles['Title']))
    elements.append(Paragraph("Official Purchase Invoice", styles['Normal']))
    elements.append(Spacer(1, 20))

    # -----------------------------
    # ORDER DETAILS
    # -----------------------------

    order_data = [
        ["Order Number", order.order_id],
        ["Transaction ID", order.transaction_id],
        ["Date", order.purchase_time.strftime("%Y-%m-%d")],
        ["Status", order.status]
    ]

    order_table = Table(order_data, colWidths=[160,300])
    order_table.setStyle(TableStyle([
        ("BACKGROUND",(0,0),(0,-1),colors.lightgrey),
        ("GRID",(0,0),(-1,-1),0.5,colors.grey)
    ]))

    elements.append(order_table)
    elements.append(Spacer(1,20))




  
    # -----------------------------
    # BUYER DETAILS
    # -----------------------------

    elements.append(Paragraph("<b>Buyer Details</b>", styles['Heading3']))

    buyer_data = [
        ["Name", buyer.name],
        ["Email", buyer.email],
        ["Phone", order.phone],
        ["Address", order.address]
    ]

    buyer_table = Table(buyer_data, colWidths=[160,300])
    buyer_table.setStyle(TableStyle([
        ("GRID",(0,0),(-1,-1),0.5,colors.grey)
    ]))

    elements.append(buyer_table)
    elements.append(Spacer(1,20))

    # -----------------------------
    # SELLER DETAILS
    # -----------------------------

    elements.append(Paragraph("<b>Seller Details</b>", styles['Heading3']))

    seller_data = [
        ["Seller Name", seller.name],
        ["Email", seller.email],
        ["Phone", seller.phone if seller.phone else "N/A"],
        ["Address", seller.address if seller.address else "N/A"]
    ]

    seller_table = Table(seller_data, colWidths=[160,300])
    seller_table.setStyle(TableStyle([
        ("BACKGROUND",(0,0),(0,-1),colors.whitesmoke),
        ("GRID",(0,0),(-1,-1),0.5,colors.grey)
    ]))

    elements.append(seller_table)
    elements.append(Spacer(1,25))
 # -----------------------------
    #SELLER ADISCOUNT   
    # -----------------------------

@app.route("/seller/discount/<int:product_id>", methods=["GET","POST"])
def seller_discount(product_id):

    if "user_id" not in session:
        return redirect("/login")

    product = Product.query.get_or_404(product_id)

    # ensure seller owns the product
    if product.seller != session["user_id"]:
        return "Unauthorized"

    if request.method == "POST":
        discount = int(request.form["discount"])

        if discount < 0 or discount > 90:
            return "Invalid discount"

        product.discount = discount
        db.session.commit()

        return redirect("/seller-dashboard")

    return render_template("seller_discount.html", product=product)

@app.route("/edit-product/<int:product_id>", methods=["GET","POST"])
def edit_product(product_id):

    product = Product.query.get_or_404(product_id)

    if request.method == "POST":

        product.name = request.form["name"]
        product.price = request.form["price"]
        product.description = request.form["description"]

        db.session.commit()

        return redirect("/seller-dashboard")

    return render_template("edit_product.html", product=product)
  # -----------------------------
    #SELLER ANALYTICS
    # -----------------------------

from flask import url_for

@app.route("/seller-dashboard")
def seller_analytics():

    if "user_id" not in session:
        return redirect(url_for("login"))

    seller_id = session["user_id"]

    orders = Order.query.filter_by(seller_id=seller_id).all()

    total_earnings = db.session.query(
        func.sum(Order.price)
    ).filter_by(seller_id=seller_id).scalar() or 0

    pending_payout = db.session.query(
        func.sum(Order.price)
    ).filter_by(
        seller_id=seller_id,
        payout_status="Pending"
    ).scalar() or 0

    paid_payout = db.session.query(
        func.sum(Order.price)
    ).filter_by(
        seller_id=seller_id,
        payout_status="Paid"
    ).scalar() or 0

    return render_template(
        "seller_dashboard.html",
        orders=orders,
        total_earnings=total_earnings,
        pending_payout=pending_payout,
        paid_payout=paid_payout
    )
    # -----------------------------
    # PRODUCT TABLE
    # -----------------------------

    elements.append(Paragraph("<b>Order Summary</b>", styles['Heading3']))

    total_price = product.price * quantity

    product_table_data = [
        ["Product", "Quantity", "Price", "Total"],
        [product.name, str(quantity), f"₹{product.price}", f"₹{total_price}"]
    ]

    product_table = Table(product_table_data, colWidths=[200,100,100,100])
    product_table.setStyle(TableStyle([
        ("BACKGROUND",(0,0),(-1,0),colors.lightgrey),
        ("GRID",(0,0),(-1,-1),0.5,colors.grey),
        ("ALIGN",(1,1),(-1,-1),"CENTER")
    ]))

    elements.append(product_table)
    elements.append(Spacer(1,20))

    # -----------------------------
    # TOTAL SECTION
    # -----------------------------

    total_table = Table([
        ["Total Amount", f"₹{total_price}"]
    ], colWidths=[300,200])

    total_table.setStyle(TableStyle([
        ("BACKGROUND",(0,0),(0,0),colors.lightgrey),
        ("GRID",(0,0),(-1,-1),0.5,colors.grey),
        ("FONTNAME",(0,0),(-1,-1),"Helvetica-Bold")
    ]))

    elements.append(total_table)
    elements.append(Spacer(1,25))

    # -----------------------------
    # FOOTER
    # -----------------------------

    elements.append(Paragraph(
        "Thank you for purchasing from Student Marketplace.",
        styles['Normal']
    ))

    elements.append(Paragraph(
        "This invoice was generated automatically.",
        styles['Normal']
    ))

    doc.build(elements)

    buffer.seek(0)

    return buffer
# -------------------------
# FILE UPLOAD
# -------------------------

UPLOAD_FOLDER = "static/uploads"
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)



# -------------------------
# GOOGLE LOGIN
# -------------------------

oauth = OAuth(app)

google = oauth.register(
    name='google',
    client_id="YOUR_GOOGLE_CLIENT_ID",
    client_secret="YOUR_GOOGLE_SECRET",
    access_token_url='https://oauth2.googleapis.com/token',
    authorize_url='https://accounts.google.com/o/oauth2/auth',
    api_base_url='https://www.googleapis.com/oauth2/v1/',
    client_kwargs={'scope': 'openid email profile'}
)



# -------------------------
# DATABASE MODELS
# -------------------------

class User(db.Model):

    id = db.Column(db.Integer, primary_key=True)

    name = db.Column(db.String(200))
    email = db.Column(db.String(200), unique=True)
    password = db.Column(db.String(200))

    phone = db.Column(db.String(20))
    address = db.Column(db.Text)
    avatar = db.Column(db.String(200), default="default.png")

    role = db.Column(db.String(20))  # user / seller / admin

    wallet = db.Column(db.Integer, default=0)

    otp = db.Column(db.String(10))

    otp_verified = db.Column(db.Boolean, default=False)
    otp_created_at = db.Column(db.DateTime)

    account_name = db.Column(db.String(200))
    account_number = db.Column(db.String(50))
    ifsc = db.Column(db.String(20))

    is_admin = db.Column(db.Boolean, default=False)

    is_banned = db.Column(db.Boolean, default=False)   # ADD THIS

    account_name = db.Column(db.String(200))
    account_number = db.Column(db.String(50))
    ifsc = db.Column(db.String(20))

    is_admin = db.Column(db.Boolean, default=False)

    is_banned = db.Column(db.Boolean, default=False)   # ADD THIS

class WalletTransaction(db.Model):

    id = db.Column(db.Integer, primary_key=True)

    user_id = db.Column(db.Integer)

    amount = db.Column(db.Integer)

    type = db.Column(db.String(20))
    # credit / debit

    description = db.Column(db.String(200))

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Address(db.Model):

    id = db.Column(db.Integer, primary_key=True)

    user_id = db.Column(db.Integer, db.ForeignKey("user.id"))

    address_name = db.Column(db.String(50))   # Home / Hostel / Office
    name = db.Column(db.String(80))
    email = db.Column(db.String(120))

    isd = db.Column(db.String(5))
    phone = db.Column(db.String(10))
    secondary_phone = db.Column(db.String(10))

    house = db.Column(db.String(120))
    street = db.Column(db.String(120))
    state = db.Column(db.String(80))
    country = db.Column(db.String(80))
    pincode = db.Column(db.String(10))

    is_default = db.Column(db.Boolean, default=False)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class PaymentMethod(db.Model):

    id = db.Column(db.Integer, primary_key=True)

    user_id = db.Column(db.Integer, db.ForeignKey("user.id"))

    card_name = db.Column(db.String(80))

    card_last4 = db.Column(db.String(4))

    card_type = db.Column(db.String(20))  # VISA / MasterCard / UPI

    expiry = db.Column(db.String(10))

    is_default = db.Column(db.Boolean, default=False)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
class Category(db.Model):

    id = db.Column(db.Integer, primary_key=True)

    name = db.Column(db.String(100), nullable=False)

    platform_fee = db.Column(db.Integer, default=5)  # percentage

import uuid

class Product(db.Model):

    id = db.Column(db.Integer, primary_key=True)

    # unique SKU automatically generated
    sku = db.Column(db.String(20), unique=True, default=lambda: Product.generate_sku())

    # product name
    name = db.Column(db.String(200))

    # product price
    price = db.Column(db.Integer)

    # discount percentage (for discount badge)
    discount = db.Column(db.Integer, default=0)

    # category reference
    category_id = db.Column(db.Integer, db.ForeignKey("category.id"))

    # category relationship
    category = db.relationship("Category", backref="products")

    # product description
    description = db.Column(db.Text)

    # seller user id
    seller = db.Column(db.Integer)

    # featured product flag
    featured = db.Column(db.Boolean, default=False)

    # product images relationship
    images = db.relationship(
        "ProductImage",
        backref="product",
        lazy=True,
        cascade="all, delete-orphan"
    )

    # SKU generator
    @staticmethod
    def generate_sku():
        return "SKU-" + uuid.uuid4().hex[:8].upper()


class ProductImage(db.Model):

    id = db.Column(db.Integer, primary_key=True)

    product_id = db.Column(db.Integer, db.ForeignKey("product.id"))

    image = db.Column(db.String(200))

class PlatformSettings(db.Model):

    id = db.Column(db.Integer, primary_key=True)

    platform_fee = db.Column(db.Float, default=2.0)   # percent

class Cart(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer)
    product_id = db.Column(db.Integer)
    quantity = db.Column(db.Integer, default=1)

class Wishlist(db.Model):

    id = db.Column(db.Integer, primary_key=True)

    user_id = db.Column(db.Integer)

    product_id = db.Column(db.Integer)


   

class Rating(db.Model):

    id = db.Column(db.Integer, primary_key=True)

    rating = db.Column(db.Integer)

    product_id = db.Column(db.Integer)

    user_id = db.Column(db.Integer)

class Dispute(db.Model):

    id = db.Column(db.Integer, primary_key=True)

    order_id = db.Column(db.String(50))

    user_id = db.Column(db.Integer)   # buyer

    reason = db.Column(db.String(500))

    seller_response = db.Column(db.String(500))

    status = db.Column(db.String(50), default="Open")

    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())

class Refund(db.Model):

    id = db.Column(db.Integer, primary_key=True)

    refund_id = db.Column(db.String(20))

    order_id = db.Column(db.Integer)

    buyer_id = db.Column(db.Integer)

    seller_id = db.Column(db.Integer)

    amount = db.Column(db.Float)

    reason = db.Column(db.Text)   # ← ADD THIS

    status = db.Column(db.String(20))

    refund_transaction_id = db.Column(db.String(50))

class Notification(db.Model):

    id = db.Column(db.Integer, primary_key=True)

    user_id = db.Column(db.Integer)

    message = db.Column(db.String(300))

    link = db.Column(db.String(200))

    is_read = db.Column(db.Boolean, default=False)

    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())
from datetime import datetime

class Order(db.Model):

    id = db.Column(db.Integer, primary_key=True)

    order_id = db.Column(db.String(20), unique=True)
    transaction_id = db.Column(db.String(50), unique=True)

    product_id = db.Column(db.Integer)
    buyer_id = db.Column(db.Integer)
    seller_id = db.Column(db.Integer)

    # buyer details
    name = db.Column(db.String(100))
    email = db.Column(db.String(120))
    phone = db.Column(db.String(20))
    address = db.Column(db.Text)

    price = db.Column(db.Integer)

    status = db.Column(db.String(50), default="Paid")
    payout_status = db.Column(db.String(20), default="Pending")

    fulfillment_status = db.Column(db.String(50), default="Processing")

    purchase_time = db.Column(db.DateTime, default=datetime.utcnow)

    processing_time = db.Column(db.DateTime)
    shipped_time = db.Column(db.DateTime)
    out_for_delivery_time = db.Column(db.DateTime)
    delivered_time = db.Column(db.DateTime)

    estimated_delivery = db.Column(db.DateTime)
    refund_status = db.Column(db.String(50), default="None")
# -------------------------
# ORDER REQUEST (REFUND / RETURN)
# -------------------------

import uuid
from datetime import datetime

class OrderRequest(db.Model):

    id = db.Column(db.Integer, primary_key=True)

    ticket_id = db.Column(db.String(20), unique=True)

    order_id = db.Column(db.Integer)
    buyer_id = db.Column(db.Integer)
    seller_id = db.Column(db.Integer)

    request_type = db.Column(db.String(50))   # refund / return / issue
    reason = db.Column(db.Text)

    status = db.Column(db.String(50), default="Open")
    # Open, Under Review, Resolved, Rejected

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class RequestMessage(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    request_id = db.Column(db.Integer)
    sender_id = db.Column(db.Integer)

    message = db.Column(db.Text)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    
# models

class Review(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer)
    user_id = db.Column(db.Integer)
    rating = db.Column(db.Integer)
    review = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp()) 


class Coupon(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(50), unique=True)
    discount = db.Column(db.Integer)
    min_amount = db.Column(db.Integer, default=0)
    expiry = db.Column(db.DateTime)
    active = db.Column(db.Boolean, default=True)
    one_time = db.Column(db.Boolean, default=True)

class CouponUsage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    coupon_id = db.Column(db.Integer)
    user_id = db.Column(db.Integer)

with app.app_context():
    db.create_all()

    admin = User.query.filter_by(email="mprcom404@gmail.com").first()

    if admin:
        admin.password = "admin123"
        admin.is_admin = True
        admin.role = "admin"
    else:
        admin = User(
            name="Administrator",
            email="mprcom404@gmail.com",
            password="admin123",
            role="admin",
            is_admin=True
        )
        db.session.add(admin)

    db.session.commit()

@app.route("/create-admin")
def create_admin():

    admin = User.query.filter_by(email="mprcom404@gmail.com").first()

    if not admin:
        admin = User(
            name="Administrator",
            email="mprcom404@gmail.com",
            password="admin123",
            role="admin",
            is_admin=True
        )

        db.session.add(admin)

    else:
        admin.is_admin = True

    db.session.commit()

    return "Admin created successfully"

#DASHBOARD
@app.route("/dashboard")
def dashboard():

    if "user_id" not in session:
        return redirect("/login")

    wishlist_items = Wishlist.query.filter_by(
        user_id=session["user_id"]
    ).all()

    products = []

    for w in wishlist_items:
        product = Product.query.get(w.product_id)
        if product:
            products.append(product)

    return render_template(
        "dashboard.html",
        wishlist=products
    )

# -------------------------
# HOME + SEARCH + FILTER
# -------------------------

from sqlalchemy import func

@app.route("/")
def home():

    search = request.args.get("search")
    category = request.args.get("category")
    sort = request.args.get("sort")

    query = Product.query

    # SEARCH
    if search:
        query = query.filter(Product.name.contains(search))

    # CATEGORY FILTER
    if category:
        query = query.filter(Product.category == category)

    # SORTING
    if sort == "low":
        query = query.order_by(Product.price.asc())

    if sort == "high":
        query = query.order_by(Product.price.desc())

    items = query.all()

    # FEATURED PRODUCTS
    featured_products = Product.query.filter_by(featured=True).limit(6).all()

    # ⭐ CALCULATE RATINGS FOR PRODUCTS
    product_ratings = {}

    for p in items:

        avg = db.session.query(
            func.avg(Review.rating)
        ).filter(
            Review.product_id == p.id
        ).scalar()

        product_ratings[p.id] = round(avg,1) if avg else 0

    return render_template(
        "index.html",
        items=items,
        featured_products=featured_products,
        product_ratings=product_ratings
    )
# -------------------------
# REGISTER
# -------------------------

from werkzeug.utils import secure_filename
import os

UPLOAD_FOLDER = "static/uploads/avatars"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

@app.route("/register", methods=["GET", "POST"])
def register():

    if request.method == "POST":

        first_name = request.form.get("first_name")
        last_name = request.form.get("last_name")
        email = request.form.get("email")
        password = request.form.get("password")
        role = request.form.get("role")   # ⭐ capture role

        avatar_file = request.files.get("avatar")
        avatar_filename = "default.png"

        if avatar_file and avatar_file.filename != "":
            filename = secure_filename(avatar_file.filename)
            avatar_path = os.path.join(UPLOAD_FOLDER, filename)
            avatar_file.save(avatar_path)
            avatar_filename = filename

        user = User(
            name=first_name + " " + last_name,
            email=email,
            password=password,
            avatar=avatar_filename,
            role=role   # ⭐ save role
        )

        db.session.add(user)
        db.session.commit()

        otp = generate_otp()
        user.otp = otp
        db.session.commit()

        session["verify_user"] = user.id

        msg = MailMessage(
            subject="EduMarket OTP Verification",
            sender="mprcom404@gmail.com",
            recipients=[email]
        )

        msg.body = f"Your EduMarket verification OTP is: {otp}"

        mail.send(msg)

        return redirect("/verify-otp")

    return render_template("register.html")

##OTP VERIFICATION

@app.route("/verify-otp", methods=["GET","POST"])
def verify_otp():

    if "verify_user" not in session:
        return redirect("/register")

    user = User.query.get(session["verify_user"])

    if request.method == "POST":

        entered_otp = request.form["otp"]

        if entered_otp == user.otp:

            user.otp_verified = True
            db.session.commit()

            session.pop("verify_user")
            session["user_id"] = user.id

            return redirect("/")

        else:
            return "Invalid OTP"

    return render_template("verify_otp.html")
##WALLET
@app.route("/add-wallet/<int:amount>")
def add_wallet(amount):

    if "user_id" not in session:
        return redirect("/login")

    user = User.query.get(session["user_id"])

    user.wallet += amount

    tx = WalletTransaction(
        user_id=user.id,
        amount=amount,
        type="credit",
        description="Wallet Top-up"
    )

    db.session.add(tx)
    db.session.commit()

    return redirect("/wallet")


# -------------------------
# LOGIN
# -------------------------
@app.route("/login", methods=["GET","POST"])
def login():

    error = None

    if request.method == "POST":

        email = request.form["email"]
        password = request.form["password"]

        user = User.query.filter_by(email=email).first()

        if not user:
            error = "Invalid email or password"

        elif user.is_banned:
            return render_template("banned.html")

        elif user.password != password:
            error = "Invalid email or password"

        else:

            otp = generate_otp()

            user.otp = otp
            user.otp_created_at = datetime.utcnow()

            db.session.commit()

            session["login_otp_user"] = user.id

            msg = MailMessage(
                "EduMarket Login OTP",
                sender="mprcom404@gmail.com",
                recipients=[user.email]
            )

            msg.body = f"Your EduMarket login OTP is: {otp}"

            mail.send(msg)

            return redirect("/login-otp")

    return render_template("login.html", error=error)

@app.route("/login-otp", methods=["GET","POST"])
def login_otp():

    if "login_otp_user" not in session:
        return redirect("/login")

    user = User.query.get(session["login_otp_user"])

    if request.method == "POST":

        entered_otp = request.form["otp"]

        if entered_otp == user.otp:

            session.pop("login_otp_user")

            session["user_id"] = user.id
            session["user"] = user.name

            return redirect("/")

        else:
            return "Invalid OTP"

    return render_template("login_otp.html")

@app.route("/login-verify", methods=["GET","POST"])
def login_verify():

    if "login_verify_user" not in session:
        return redirect("/login")

    user = User.query.get(session["login_verify_user"])

    if request.method == "POST":

        otp = request.form["otp"]

        if otp == user.otp:

            session.pop("login_verify_user")

            session["user_id"] = user.id
            session["user"] = user.name

            return redirect("/")

        else:
            return "Invalid OTP"

    return render_template("login_verify.html")



@app.route("/google-auth")
def google_auth():

    token = google.authorize_access_token()

    resp = google.get('userinfo')

    user_info = resp.json()

    email = user_info["email"]

    name = user_info["name"]

    user = User.query.filter_by(email=email).first()

    if not user:

        user = User(name=name,email=email,verified=True)

        db.session.add(user)

        db.session.commit()

    session["user_id"] = user.id

    session["user"] = user.name

    return redirect("/")

# -------------------------
# LOGOUT
# -------------------------

@app.route("/logout")
def logout():

    session.clear()

    return redirect("/")

@app.context_processor
def inject_user():

    if "user_id" in session:
        user = User.query.get(session["user_id"])
        return dict(current_user=user)

    return dict(current_user=None)
# -------------------------
# MESSAGES
# -------------------------

@app.route("/send-message", methods=["POST"])
def send_message():

    if "user_id" not in session:
        return redirect("/")

    receiver_id = request.form["receiver_id"]
    text = request.form["message"]

    msg = Message(
        sender_id=session["user_id"],
        receiver_id=receiver_id,
        message=text
    )

    db.session.add(msg)
    db.session.commit()

    return redirect(request.referrer)

@app.route("/messages/<int:user_id>")
def messages(user_id):

    if "user_id" not in session:
        return redirect("/")

    my_id = session["user_id"]

    msgs = Message.query.filter(

        ((Message.sender_id==my_id) & (Message.receiver_id==user_id)) |
        ((Message.sender_id==user_id) & (Message.receiver_id==my_id))

    ).order_by(Message.created_at.asc()).all()

    other_user = User.query.get(user_id)

    return render_template(
        "messages.html",
        messages=msgs,
        other_user=other_user
    )


@app.route("/inbox")
def inbox():

    if "user_id" not in session:
        return redirect("/")

    user_id = session["user_id"]

    # get all messages related to user
    messages = Message.query.filter(
        (Message.sender_id == user_id) |
        (Message.receiver_id == user_id)
    ).order_by(Message.created_at.desc()).all()

    conversations = {}

    for msg in messages:

        other_user = msg.receiver_id if msg.sender_id == user_id else msg.sender_id

        if other_user not in conversations:
            user = User.query.get(other_user)
            conversations[other_user] = {
                "user": user,
                "last_message": msg.message,
                "time": msg.created_at
            }

    return render_template(
        "inbox.html",
        conversations=conversations.values()
    )

@app.route("/admin/update-category-fee/<int:cat_id>", methods=["POST"])
def update_category_fee(cat_id):

    if "admin" not in session:
        return redirect("/login")

    category = Category.query.get_or_404(cat_id)

    fee = int(request.form["fee"])

    category.platform_fee = fee

    db.session.commit()

    flash("Category platform fee updated")

    return redirect("/admin")

@app.route("/admin/messages")
def admin_messages():

    if not current_user.is_admin:
        return redirect("/")

    messages = Message.query.order_by(Message.created_at.desc()).all()

    return render_template("admin_messages.html", messages=messages)
# -------------------------
# CHAT SYSTEM
# -------------------------

@app.route("/chat/<int:user_id>")
def chat(user_id):

    if "user_id" not in session:
        return redirect("/")

    my_id = session["user_id"]

    other_user = User.query.get_or_404(user_id)

    messages = Message.query.filter(
        ((Message.sender_id == my_id) & (Message.receiver_id == user_id)) |
        ((Message.sender_id == user_id) & (Message.receiver_id == my_id))
    ).order_by(Message.created_at.asc()).all()

    return render_template(
        "chat.html",
        messages=messages,
        other_user=other_user,
        my_id=my_id
    )
# -------------------------
# ADMIN LOGIN
# -------------------------
@app.route("/admin-login", methods=["GET", "POST"])
def admin_login():

    error = None

    if request.method == "POST":

        email = request.form["email"]
        password = request.form["password"]

        # check database
        admin = User.query.filter_by(email=email, is_admin=True).first()

        if not admin:
            error = "Administrator account not found."

        elif admin.password != password:
            error = "Incorrect administrator password."

        else:
            session["user_id"] = admin.id
            return redirect("/admin")   # FIXED

    return render_template("admin_login.html", error=error)

@app.route("/force-admin")
def force_admin():

    admin = User.query.filter_by(email="mprcom404@gmail.com").first()

    if admin:
        admin.is_admin = True
        admin.role = "admin"
        admin.password = "admin123"
    else:
        admin = User(
            name="Administrator",
            email="mprcom404@gmail.com",
            password="admin123",
            role="admin",
            is_admin=True
        )
        db.session.add(admin)

    db.session.commit()

    return "Admin fixed successfully"



@app.route("/admin/feature-product/<int:product_id>")
def feature_product(product_id):

    if not current_user.is_admin:
        return "Unauthorized"

    product = Product.query.get_or_404(product_id)

    product.featured = not product.featured

    db.session.commit()

    return redirect("/admin/products")
# -------------------------
# ADMIN DASHBOARD
# -------------------------
from sqlalchemy import func

@app.route("/admin")
def admin_dashboard():

    if "user_id" not in session:
        return redirect("/admin-login")

    admin = User.query.get(session["user_id"])

    if not admin or not admin.is_admin:
        return "Access Denied"

    # Core data
    users = User.query.all()
    products = Product.query.all()
    orders = Order.query.all()

    # Coupons
    coupons = Coupon.query.order_by(Coupon.id.desc()).all()

    # Refunds
    refunds = Refund.query.order_by(Refund.id.desc()).all()

    # Disputes
    disputes = OrderRequest.query.order_by(
        OrderRequest.created_at.desc()
    ).all()

    open_disputes = OrderRequest.query.filter_by(status="Open").count()

    # Sales analytics
    total_sales = db.session.query(func.sum(Order.price)).scalar() or 0

    pending_payout = db.session.query(func.sum(Order.price))\
        .filter(Order.payout_status == "Pending")\
        .scalar() or 0

    # Platform fee
    settings = PlatformSettings.query.first()
    platform_fee = settings.platform_fee if settings else 10

    return render_template(
        "admin.html",
        users=users,
        products=products,
        orders=orders,
        coupons=coupons,
        refunds=refunds,
        disputes=disputes,
        open_disputes=open_disputes,
        total_sales=total_sales,
        pending_payout=pending_payout,
        platform_fee=platform_fee,
        total_users=len(users),
        total_products=len(products),
        total_orders=len(orders)
    )


@app.route("/admin/update-platform-fee", methods=["POST"])
def update_platform_fee():

    if "user_id" not in session:
        return redirect("/admin-login")

    admin = User.query.get(session["user_id"])

    if not admin or not admin.is_admin:
        return "Access Denied"

    fee = float(request.form["fee"])

    settings = PlatformSettings.query.first()

    if settings:
        settings.platform_fee = fee
    else:
        settings = PlatformSettings(platform_fee=fee)
        db.session.add(settings)

    db.session.commit()

    return redirect("/admin")
# -------------------------
# REFUND DISPUTE
# -------------------------
@app.route("/raise-dispute/<int:order_id>", methods=["POST"])
def raise_dispute(order_id):

    order = Order.query.get(order_id)

    refund = Refund(
        refund_id="REF" + uuid.uuid4().hex[:8].upper(),
        order_id=order.id,
        buyer_id=order.buyer_id,
        seller_id=Product.query.get(order.product_id).seller_id,
        amount=order.price,
        transaction_id=order.transaction_id,
        status="Pending"
    )

    db.session.add(refund)
    db.session.commit()

    return redirect("/orders")
# -------------------------
# PLATFORM FEE SETTINGS
# -------------------------

# -------------------------
# Raise request
# -------------------------
@app.route("/raise-request/<int:order_id>", methods=["GET","POST"])
def raise_request(order_id):

    if "user_id" not in session:
        return redirect("/login")

    order = Order.query.get_or_404(order_id)

    if request.method == "POST":

        # -------------------------
        # PREVENT DUPLICATE DISPUTES
        # -------------------------
        existing = OrderRequest.query.filter_by(order_id=order.id).first()

        if existing:
            flash("Dispute already raised for this order")
            return redirect("/profile")

        # -------------------------
        # SAFE FORM READING
        # -------------------------
        request_type = request.form.get("type", "Dispute")
        reason = request.form.get("reason")

        # -------------------------
        # CREATE TICKET
        # -------------------------
        ticket = "TCK-" + uuid.uuid4().hex[:6].upper()

        req = OrderRequest(
            ticket_id=ticket,
            order_id=order.id,
            buyer_id=session["user_id"],
            seller_id=order.seller_id,
            request_type=request_type,
            reason=reason,
            status="Open"
        )

        db.session.add(req)

        buyer = User.query.get(session["user_id"])
        seller = User.query.get(order.seller_id)

        # -------------------------
        # DATABASE NOTIFICATIONS
        # -------------------------
        note_seller = Notification(
            user_id=seller.id,
            message=f"New dispute raised ({ticket})",
            link="/seller/disputes"
        )

        note_buyer = Notification(
            user_id=buyer.id,
            message=f"Your dispute ticket {ticket} was created",
            link="/profile"
        )

        db.session.add(note_seller)
        db.session.add(note_buyer)

        # -------------------------
        # ADMIN DATABASE NOTIFICATION
        # -------------------------
        admins = User.query.filter_by(is_admin=True).all()

        for admin in admins:
            admin_note = Notification(
                user_id=admin.id,
                message=f"New dispute ticket {ticket} raised",
                link="/admin/disputes"
            )
            db.session.add(admin_note)

        # -------------------------
        # EMAIL NOTIFICATIONS
        # -------------------------
        send_email(
            buyer.email,
            "Dispute Ticket Created",
            f"""
Your dispute request has been submitted.

Ticket ID: {ticket}
Order ID: {order.order_id}

Our team and the seller will review the issue shortly.
"""
        )

        send_email(
            seller.email,
            "New Dispute Raised",
            f"""
A buyer has raised a dispute.

Ticket ID: {ticket}
Order ID: {order.order_id}

Please check your seller dashboard to respond.
"""
        )

        for admin in admins:
            send_email(
                admin.email,
                "Marketplace Dispute Alert",
                f"""
A new dispute has been raised.

Ticket ID: {ticket}
Order ID: {order.order_id}

Admin review may be required.
"""
            )

        # -------------------------
        # SAVE EVERYTHING
        # -------------------------
        db.session.commit()

        flash("Dispute raised successfully")

        return redirect("/profile")

    return render_template("raiserequest.html", order=order)
#RCANCEL ORDER
@app.route("/cancel-order/<int:order_id>", methods=["POST"])
def cancel_order(order_id):

    if "user_id" not in session:
        return redirect("/login")

    order = Order.query.get_or_404(order_id)

    if order.buyer_id != session["user_id"]:
        return "Unauthorized"

    if order.fulfillment_status != "Processing":
        flash("Order cannot be cancelled")
        return redirect("/orders")

    # -------------------------
    # UPDATE ORDER
    # -------------------------

    order.fulfillment_status = "Cancelled"
    order.refund_status = "Processing"
    order.cancelled_by = "buyer"

    # -------------------------
    # CREATE REFUND
    # -------------------------

    refund_code = "RFD-" + uuid.uuid4().hex[:8].upper()

    refund = Refund(
        refund_id=refund_code,
        order_id=order.id,
        buyer_id=order.buyer_id,
        seller_id=order.seller_id,
        amount=order.price,
        reason="Order cancelled by buyer",
        status="Processing"
    )

    db.session.add(refund)

    # LINK REFUND TO ORDER
    order.refund_id = refund_code

    # -------------------------
    # NOTIFICATIONS
    # -------------------------

    buyer_note = Notification(
        user_id=order.buyer_id,
        message=f"Order {order.order_id} cancelled. Refund started.",
        link="/refunds"
    )

    seller_note = Notification(
        user_id=order.seller_id,
        message=f"Order {order.order_id} cancelled by buyer. Refund required.",
        link="/seller"
    )

    db.session.add(buyer_note)
    db.session.add(seller_note)

    db.session.commit()

    flash("Order cancelled successfully. Refund processing started.")

    return redirect("/orders")

@app.route("/seller/cancel-order/<int:order_id>", methods=["POST"])
def seller_cancel_order(order_id):

    if "user_id" not in session:
        return redirect("/login")

    order = Order.query.get_or_404(order_id)

    # prevent cancelling already cancelled orders
    if order.fulfillment_status == "Cancelled":
        flash("Order already cancelled")
        return redirect("/seller")

    # -------------------------
    # UPDATE ORDER STATUS
    # -------------------------

    order.fulfillment_status = "Cancelled"
    order.refund_status = "Processing"
    order.cancelled_by = "seller"

    reason = request.form.get("reason", "Cancelled by seller")
    order.cancel_reason = reason

    # -------------------------
    # CREATE REFUND RECORD
    # -------------------------

    refund = Refund(
        refund_id="RFD-" + uuid.uuid4().hex[:8].upper(),
        order_id=order.id,
        buyer_id=order.buyer_id,
        seller_id=order.seller_id,
        amount=order.price,
        reason=reason,
        status="Processing"
    )

    db.session.add(refund)

    # -------------------------
    # NOTIFY BUYER
    # -------------------------

    buyer_note = Notification(
        user_id=order.buyer_id,
        message=f"Seller cancelled order {order.order_id}. Refund initiated.",
        link="/refunds"
    )

    db.session.add(buyer_note)

    # -------------------------
    # NOTIFY SELLER (record)
    # -------------------------

    seller_note = Notification(
        user_id=order.seller_id,
        message=f"You cancelled order {order.order_id}. Refund pending.",
        link="/seller/refunds"
    )

    db.session.add(seller_note)

    db.session.commit()

    flash("Order cancelled. Refund record created.")

    return redirect("/seller")

@app.route("/refund-pay/<int:order_id>")
def refund_pay(order_id):

    refund = Refund.query.filter_by(order_id=order_id).first()

    return render_template("refund_payment.html", refund=refund)

@app.route("/confirm-refund/<int:refund_id>")
def confirm_refund(refund_id):

    refund = Refund.query.get_or_404(refund_id)

    refund.status = "Credited"
    refund.refund_transaction_id = "TXN-" + uuid.uuid4().hex[:8].upper()

    db.session.commit()

    flash("Refund paid successfully")

    return redirect("/seller")

    return redirect(f"/product/{product_id}")
# -------------------------
# CONVERSATION PAGE
# -------------------------

@app.route("/request/<int:id>", methods=["GET","POST"])
def request_chat(id):

    req = OrderRequest.query.get_or_404(id)

    messages = RequestMessage.query.filter_by(request_id=id).all()

    if request.method == "POST":

        msg = RequestMessage(
            request_id=id,
            sender_id=session["user_id"],
            message=request.form["message"]
        )

        db.session.add(msg)
        db.session.commit()

        return redirect(f"/request/{id}")

    return render_template(
        "requestchat.html",
        request=req,
        messages=messages
    )

@app.route("/admin/requests")
def admin_requests():

    admin = User.query.get(session["user_id"])

    if not admin or not admin.is_admin:
        return "Access Denied"

    requests = OrderRequest.query.all()

    return render_template("admin_requests.html", requests=requests)

@app.route("/admin/refunds")
def admin_refunds():

    if "user_id" not in session:
        return redirect("/admin-login")

    admin = User.query.get(session["user_id"])

    if not admin or not admin.is_admin:
        return "Access Denied"

    refunds = Refund.query.order_by(Refund.id.desc()).all()

    return render_template(
        "admin_refunds.html",
        refunds=refunds
    )

@app.route("/admin/payout-gateway/<int:order_id>")
def admin_payout_gateway(order_id):

    order = Order.query.get_or_404(order_id)

    txn = "PAY-" + uuid.uuid4().hex[:10].upper()

    order.payout_txn_id = txn
    order.payout_status = "Paid"

    db.session.commit()

    flash("Seller payout completed")

    return redirect("/admin#payouts")

# -------------------------
# DELETE PRODUCT
# -------------------------

@app.route("/admin/delete-product/<int:id>")
def delete_product(id):

    if "user_id" not in session:
        return redirect("/admin-login")

    admin = User.query.get(session["user_id"])

    if not admin or not admin.is_admin:
        return "Access Denied"

    product = Product.query.get_or_404(id)

    db.session.delete(product)
    db.session.commit()

    return redirect("/admin")
# -------------------------
# DISPUTES MANAGEMENT
# -------------------------


@app.route("/admin/disputes")
def admin_disputes():

    if "user_id" not in session:
        return redirect("/admin-login")

    admin = User.query.get(session["user_id"])

    if not admin or not admin.is_admin:
        return "Access Denied"

    requests = OrderRequest.query.order_by(
        OrderRequest.created_at.desc()
    ).all()

    return render_template(
        "admindisputes.html",
        requests=requests
    )




    # -------------------------
    # UPDATE STATUS
    # -------------------------

    req.status = status

    db.session.commit()

    # -------------------------
    # SEND EMAIL NOTIFICATIONS
    # -------------------------

    buyer = User.query.get(req.buyer_id)
    seller = User.query.get(req.seller_id)

    send_email(
        buyer.email,
        "Dispute Update",
        f"""
Ticket {req.ticket_id} status updated.

New Status: {status}
"""
    )

    send_email(
        seller.email,
        "Dispute Update",
        f"""
Ticket {req.ticket_id} status updated.

New Status: {status}
"""
    )

    # -------------------------
    # REDIRECT BACK
    # -------------------------

    return redirect("/admin/disputes")


@app.route("/refunds")
def refunds():

    if "user_id" not in session:
        return redirect("/login")

    refunds = Refund.query.filter_by(
        buyer_id=session["user_id"]
    ).all()

    return render_template("buyer_refunds.html", refunds=refunds)


@app.route("/my-disputes")
def buyer_disputes():

    if "user_id" not in session:
        return redirect("/login")

    disputes = OrderRequest.query.filter_by(
        buyer_id=session["user_id"]
    ).order_by(OrderRequest.created_at.desc()).all()

    return render_template(
        "buyer_disputes.html",
        disputes=disputes
    )

@app.route("/seller-disputes")
def seller_disputes():

    if "user_id" not in session:
        return redirect("/login")

    disputes = OrderRequest.query.filter_by(
        seller_id=session["user_id"]
    ).all()

    return render_template("seller_disputes.html", disputes=disputes)
# BAN USER
# -------------------------

@app.route("/admin/ban-user/<int:id>")
def ban_user(id):

    if "user_id" not in session:
        return redirect("/admin-login")

    admin = User.query.get(session["user_id"])

    if not admin or not admin.is_admin:
        return "Access Denied"

    user = User.query.get_or_404(id)

    user.is_banned = True

    db.session.commit()

    return redirect("/admin")


# -------------------------
# UNBAN USER
# -------------------------

@app.route("/admin/unban-user/<int:id>")
def unban_user(id):

    if "user_id" not in session:
        return redirect("/admin-login")

    admin = User.query.get(session["user_id"])

    if not admin or not admin.is_admin:
        return "Access Denied"

    user = User.query.get_or_404(id)

    user.is_banned = False

    db.session.commit()

    return redirect("/admin")


# -------------------------
# DELETE USER
# -------------------------

@app.route("/admin/delete-user/<int:id>")
def delete_user(id):

    if "user_id" not in session:
        return redirect("/admin-login")

    admin = User.query.get(session["user_id"])

    if not admin or not admin.is_admin:
        return "Access Denied"

    target = User.query.get_or_404(id)

    db.session.delete(target)
    db.session.commit()

    return redirect("/admin")


# -------------------------
# ADD COUPON
# -------------------------

@app.route("/admin/add-coupon", methods=["POST"])
def add_coupon():

    if "user_id" not in session:
        return redirect("/admin-login")

    admin = User.query.get(session["user_id"])

    if not admin or not admin.is_admin:
        return "Access Denied"

    code = request.form["code"]
    discount = int(request.form["discount"])

    coupon = Coupon(
        code=code.upper(),
        discount=discount
    )

    db.session.add(coupon)
    db.session.commit()

    return redirect("/admin")


# -------------------------
# DELETE COUPON
# -------------------------

@app.route("/admin/delete-coupon/<int:id>")
def delete_coupon(id):

    if "user_id" not in session:
        return redirect("/admin-login")

    admin = User.query.get(session["user_id"])

    if not admin or not admin.is_admin:
        return "Access Denied"

    coupon = Coupon.query.get_or_404(id)

    db.session.delete(coupon)
    db.session.commit()

    return redirect("/admin")

@app.route("/revoke/<int:product_id>")
def revoke(product_id):

    product = Product.query.get(product_id)

    if product:
        db.session.delete(product)
        db.session.commit()

    return redirect("/seller")
# -------------------------
# ETA UPDATE
# -------------------------
@app.route("/update-delivery/<int:order_id>", methods=["POST"])
def update_delivery(order_id):

    order = Order.query.get_or_404(order_id)

    date = request.form["estimated_delivery"]

    from datetime import datetime
    order.estimated_delivery = datetime.strptime(date, "%Y-%m-%d")

    db.session.commit()

    return redirect("/seller")
# -------------------------
# SELLER PAYOUT PAGE
# -------------------------

@app.route("/admin/payouts")
def admin_payouts():

    if "user_id" not in session:
        return redirect("/admin-login")

    admin = User.query.get(session["user_id"])

    if not admin or not admin.is_admin:
        return "Access Denied"

    orders = Order.query.all()

    payout_data = []

    total_pending = 0

    for order in orders:

        seller = User.query.get(order.seller_id)
        product = Product.query.get(order.product_id)

        if order.payout_status == "Pending":
            total_pending += order.price

        payout_data.append({
            "id": order.id,
            "order_id": order.order_id,
            "seller_name": seller.name if seller else "Unknown",
            "product_name": product.name if product else "Unknown",
            "amount": order.price,
            "status": order.payout_status
        })

    return render_template(
        "adminpayout.html",
        payouts=payout_data,
        total_pending=total_pending
    )
# -------------------------
# PAY SELLER
# -------------------------

@app.route("/admin/pay-seller/<int:order_id>")
def pay_seller(order_id):

    if "user_id" not in session:
        return redirect("/admin-login")

    admin = User.query.get(session["user_id"])

    if not admin or not admin.is_admin:
        return "Access Denied"

    order = Order.query.get_or_404(order_id)

    # -------------------------
    # UPDATE PAYOUT STATUS
    # -------------------------

    order.payout_status = "Paid"

    db.session.commit()

    # -------------------------
    # EMAIL SELLER ABOUT PAYMENT
    # -------------------------

    seller = User.query.get(order.seller_id)

    send_email(
        seller.email,
        "Seller Payment Released",
        f"""
Payment for order {order.order_id} has been released.

Amount: ₹{order.price}

You can check your payout history in the seller dashboard.
"""
    )

    # -------------------------
    # IN-APP NOTIFICATION
    # -------------------------

    note = Notification(
        user_id=seller.id,
        message=f"Payment received for order {order.order_id}",
        link="/seller"
    )

    db.session.add(note)
    db.session.commit()

    return redirect("/admin/payouts")

# -------------------------
#BUYER ORDER STATUS PAGE
# -------------------------

@app.route("/admin/orders")
def admin_orders():

    if "user_id" not in session:
        return redirect("/admin-login")

    admin = User.query.get(session["user_id"])

    if not admin or not admin.is_admin:
        return "Access Denied"

    orders = Order.query.order_by(Order.purchase_time.desc()).all()

    order_list = []

    for o in orders:

        buyer = User.query.get(o.buyer_id)
        product = Product.query.get(o.product_id)

        seller = None
        if product:
            seller = User.query.get(product.seller)

        image = "noimage.png"
        if product and product.images:
            image = product.images[0].image

        order_list.append({
            "id": o.id,
            "order_id": o.order_id,
            "product_id": o.product_id,
            "product_name": product.name if product else "Deleted Product",
            "product_image": image,
            "price": o.price,
            "purchase_time": o.purchase_time,
            "fulfillment_status": o.fulfillment_status,
            "transaction_id": o.transaction_id,
            "estimated_delivery": o.estimated_delivery,
            "address": o.address,
            "refund_status": getattr(o, "refund_status", "None"),
            "buyer_name": buyer.name if buyer else "Unknown",
            "buyer_email": buyer.email if buyer else "Unknown",
            "seller_name": seller.name if seller else "Unknown",
            "seller_email": seller.email if seller else "Unknown"
        })

    return render_template("admin_orders.html", orders=order_list)
# -------------------------
#REFUND STATUS UPDATE
# -------------------------

@app.route("/request-refund/<int:order_id>", methods=["POST"])
def request_refund(order_id):

    order = Order.query.get(order_id)

    product = Product.query.get(order.product_id)

    refund = Refund(
        refund_id="RFD" + uuid.uuid4().hex[:8].upper(),
        order_id=order.id,
        buyer_id=order.buyer_id,
        seller_id=product.seller,   # FIX HERE
        amount=order.price,
        reason=request.form["reason"],
        status="Pending"
    )

    db.session.add(refund)

    order.refund_status = "Requested"

    db.session.commit()

    return redirect("/orders")

@app.route("/admin/approve-refund/<int:refund_id>")
def approve_refund(refund_id):

    refund = Refund.query.get(refund_id)

    refund.status = "Approved"

    db.session.commit()

    return redirect("/admin/refunds")

@app.route("/seller/refunds")
def seller_refunds():

    if "user_id" not in session:
        return redirect("/login")

    seller_id = session["user_id"]

    refunds = Refund.query.filter_by(
        seller_id=seller_id,
        status="Approved"
    ).all()

    return render_template("seller_refunds.html", refunds=refunds)

@app.route("/demo-refund-payment/<int:order_id>")
def demo_refund_payment(order_id):

    if "user_id" not in session:
        return redirect("/login")

    order = Order.query.get_or_404(order_id)

    refund = Refund.query.filter_by(order_id=order.id).first()

    if not refund:
        return "Refund record not found"

    return render_template(
        "demo_refund_payment.html",
        refund=refund,
        order=order
    )
@app.route("/complete-refund/<int:refund_id>", methods=["POST"])
def complete_refund(refund_id):

    refund = Refund.query.get_or_404(refund_id)
    order = Order.query.get(refund.order_id)

    refund.status = "Credited"
    refund.refund_transaction_id = request.form["transaction_id"]

    order.refund_status = "Credited"

    db.session.commit()

    flash("Refund completed successfully")

    return redirect("/seller")
# -------------------------
# ADMIN SEND NOTIFICATION
# -------------------------

@app.route("/admin/send-notification", methods=["POST"])
def send_notification():

    if "user_id" not in session:
        return redirect("/admin-login")

    admin = User.query.get(session["user_id"])

    if not admin or not admin.is_admin:
        return "Access Denied"

    message = request.form["message"]
    target = request.form["target"]

    if target == "all":
        users = User.query.all()

    elif target == "sellers":
        users = User.query.filter_by(role="seller").all()

    else:
        users = User.query.filter_by(role="buyer").all()

    for u in users:

        note = Notification(
            user_id=u.id,
            message=message,
            link="/notifications"
        )

        db.session.add(note)

    db.session.commit()

    return redirect("/admin")
# -------------------------

# -------------------------
# STATUS UPDATE FOR REQUESTS
# ------------------------
@app.route("/admin/update-request/<int:id>/<status>")
def update_request(id, status):

    if "user_id" not in session:
        return redirect("/admin-login")

    admin = User.query.get(session["user_id"])

    if not admin or not admin.is_admin:
        return "Access Denied"

    allowed = ["Under Review", "Resolved", "Rejected"]

    if status not in allowed:
        return "Invalid status"

    req = OrderRequest.query.get_or_404(id)

    # -------------------------
    # UPDATE DISPUTE STATUS
    # -------------------------
    req.status = status

    buyer = User.query.get(req.buyer_id)
    seller = User.query.get(req.seller_id)

    # -------------------------
    # CREATE REFUND IF RESOLVED
    # -------------------------
    if status == "Resolved":

        order = Order.query.get(req.order_id)

        refund = Refund(
            refund_id="RFD" + uuid.uuid4().hex[:8].upper(),
            order_id=order.id,
            buyer_id=order.buyer_id,
            seller_id=order.seller_id,
            amount=order.price,
            reason=req.reason,
            status="Approved"
        )

        db.session.add(refund)

    # -------------------------
    # IN-APP NOTIFICATIONS
    # -------------------------

    buyer_note = Notification(
        user_id=buyer.id,
        message=f"Dispute ticket {req.ticket_id} updated to {status}",
        link="/my-disputes"
    )

    seller_note = Notification(
        user_id=seller.id,
        message=f"Dispute ticket {req.ticket_id} updated to {status}",
        link="/seller-disputes"
    )

    db.session.add(buyer_note)
    db.session.add(seller_note)

    # -------------------------
    # EMAIL BUYER
    # -------------------------

    send_email(
        buyer.email,
        "Dispute Update",
        f"""
Ticket {req.ticket_id} status updated.

New Status: {status}
"""
    )

    # -------------------------
    # EMAIL SELLER
    # -------------------------

    send_email(
        seller.email,
        "Dispute Update",
        f"""
Ticket {req.ticket_id} status updated.

New Status: {status}
"""
    )

    # -------------------------
    # SAVE ALL CHANGES
    # -------------------------
    db.session.commit()

    return redirect("/admin/disputes")
#sellers page
# -------------------------
# SELLER DASHBOARD
# -------------------------
@app.route("/seller")
def seller_dashboard():

    if "user_id" not in session:
        return redirect("/")

    user = User.query.get(session["user_id"])

    if user.role != "seller":
        return render_template("selleraccessdenied.html")

    products = Product.query.filter_by(seller=user.id).all()
    orders = Order.query.filter_by(seller_id=user.id).all()

    total_earnings = sum(o.price for o in orders)
    pending_payout = sum(o.price for o in orders if o.payout_status == "Pending")
    paid_payout = sum(o.price for o in orders if o.payout_status == "Paid")

    return render_template(
        "seller.html",
        products=products,
        orders=orders,
        total_earnings=total_earnings,
        pending_payout=pending_payout,
        paid_payout=paid_payout
    )
from datetime import datetime, timedelta

@app.route("/update-fulfillment/<int:order_id>", methods=["POST"])
def update_fulfillment(order_id):

    if "user_id" not in session:
        return redirect("/login")

    order = Order.query.get_or_404(order_id)

    status = request.form["status"]
    order.fulfillment_status = status

    now = datetime.utcnow()

    # -------------------------
    # STATUS TIMESTAMPS
    # -------------------------

    if status == "Processing":
        order.processing_time = now

    elif status == "Shipped":
        order.shipped_time = now

        # Set estimated delivery (3 days)
        order.estimated_delivery = now + timedelta(days=3)

    elif status == "Out for Delivery":
        order.out_for_delivery_time = now

    elif status == "Delivered":
        order.delivered_time = now

    # -------------------------
    # BUYER NOTIFICATION
    # -------------------------

    buyer = User.query.get(order.buyer_id)

    note = Notification(
        user_id=buyer.id,
        message=f"Order {order.order_id} is now {status}",
        link="/orders"
    )

    db.session.add(note)

    # -------------------------
    # EMAIL BUYER
    # -------------------------

    send_email(
        buyer.email,
        "Order Status Update",
        f"""
Hello {buyer.name},

Your order {order.order_id} has been updated.

New Status: {status}

Thank you for shopping with Student Marketplace.
"""
    )

    db.session.commit()

    return redirect("/seller")
@app.route("/seller-dispute-response/<int:id>", methods=["GET","POST"])
def seller_dispute_response(id):

    dispute = Dispute.query.get(id)

    if request.method == "POST":

        dispute.seller_response = request.form["response"]

        dispute.status = "Seller Responded"

        db.session.commit()

        return redirect("/seller-disputes")

    return render_template("seller_response.html", dispute=dispute)
# -------------------------
# PROFILE TAB
# -------------------------

@app.route("/profile")
def profile():

    if "user_id" not in session:
        return redirect("/login")

    user = User.query.get(session["user_id"])

    # -------------------------
    # USER ORDERS
    # -------------------------

    orders = Order.query.filter_by(
        buyer_id=user.id
    ).order_by(Order.purchase_time.desc()).all()

    order_list = []

    for o in orders:

        product = Product.query.get(o.product_id)

        requests = OrderRequest.query.filter_by(
            order_id=o.id
        ).first()

        image = "noimage.png"

        if product and product.images:
            image = product.images[0].image

        order_list.append({
            "id": o.id,
            "order_id": o.order_id,
            "product_id": o.product_id,
            "product_name": product.name if product else "Deleted Product",
            "product_image": image,
            "price": o.price,
            "status": o.status,
            "fulfillment_status": o.fulfillment_status,
            "purchase_time": o.purchase_time,
            "dispute": requests
        })

    # -------------------------
    # SAVED ADDRESSES
    # -------------------------

    addresses = Address.query.filter_by(
        user_id=user.id
    ).order_by(Address.is_default.desc()).all()

    # -------------------------
    # SAVED PAYMENTS
    # -------------------------

    payments = PaymentMethod.query.filter_by(
        user_id=user.id
    ).order_by(PaymentMethod.is_default.desc()).all()

    return render_template(
        "profile.html",
        user=user,
        orders=order_list,
        addresses=addresses,
        payments=payments
    )
@app.route("/contact")
def contact():
    return render_template("contact.html")

@app.route("/dispute/<int:request_id>", methods=["GET","POST"])
def dispute_chat(request_id):

    if "user_id" not in session:
        return redirect("/login")

    req = OrderRequest.query.get_or_404(request_id)

    if request.method == "POST":

        msg = RequestMessage(
            request_id=request_id,
            sender_id=session["user_id"],
            message=request.form["message"]
        )

        db.session.add(msg)
        db.session.commit()

        return redirect(f"/dispute/{request_id}")

    messages = RequestMessage.query.filter_by(
        request_id=request_id
    ).order_by(RequestMessage.created_at.asc()).all()

    return render_template(
        "disputechat.html",
        request=req,
        messages=messages
    )

# -------------------------
# EDIT PROFILE
# -------------------------

@app.route("/edit-profile", methods=["GET","POST"])
def edit_profile():

    if "user_id" not in session:
        return redirect("/login")

    user = User.query.get(session["user_id"])

    if request.method == "POST":

        user.name = request.form["name"]
        user.email = request.form["email"]
        user.phone = request.form["phone"]

        user.account_name = request.form["account_name"]
        user.account_number = request.form["account_number"]
        user.ifsc = request.form["ifsc"]

        db.session.commit()

        return redirect("/profile")

    return render_template("editprofile.html", user=user)

# -------------------------
# HELP CENTRE
# -------------------------

@app.route("/help")
def help_center():
    return render_template("help.html")

@app.route("/terms")
def terms():
    return render_template("terms.html")

@app.route("/privacy")
def privacy():
    return render_template("privacy.html")

@app.route("/refund")
def refund():
    return render_template("refund.html")

@app.route("/safety-guidelines")
def safety_guidelines():
    return render_template("safety-guidelines.html")

# -------------------------
# PRODUCT PAGE
# -------------------------

from sqlalchemy import func

@app.route("/product/<int:product_id>")
def product_page(product_id):

    product = Product.query.get_or_404(product_id)

    seller = User.query.get(product.seller) if product.seller else None

    reviews = Review.query.filter_by(product_id=product_id).all()

    avg_rating = db.session.query(
    db.func.avg(Review.rating)
).filter_by(product_id=product_id).scalar()

    avg_rating = int(avg_rating) if avg_rating else 0

    review_count = len(reviews)

    latest_products = Product.query.order_by(
        Product.id.desc()
    ).limit(8).all()

    return render_template(
        "product.html",
        product=product,
        seller=seller,
        reviews=reviews,
        avg_rating=avg_rating,
        review_count=review_count,
        latest_products=latest_products
    )
@app.route("/review-product/<int:product_id>", methods=["POST"])
def review_product(product_id):

    if "user_id" not in session:
        return redirect("/login")

    existing = Review.query.filter_by(
        product_id=product_id,
        user_id=session["user_id"]
    ).first()

    if existing:
        return redirect(f"/product/{product_id}")

    rating = request.form.get("rating")
    review = request.form.get("review")

    new_review = Review(
        product_id=product_id,
        user_id=session["user_id"],
        rating=int(rating),
        review=review
    )

    db.session.add(new_review)
    db.session.commit()

    return redirect(f"/product/{product_id}")

# -------------------------
# ADD TO CART
# -------------------------

@app.route("/add-cart/<int:product_id>")
def add_cart(product_id):

    if "user_id" not in session:
        return redirect("/login")

    qty = int(request.args.get("qty", 1))

    item = Cart.query.filter_by(
        user_id=session["user_id"],
        product_id=product_id
    ).first()

    if item:
        item.quantity += qty
    else:
        item = Cart(
            user_id=session["user_id"],
            product_id=product_id,
            quantity=qty
        )
        db.session.add(item)

    db.session.commit()

    return redirect("/cart")


@app.route("/buy/<int:product_id>")
def buy(product_id):

    if "user_id" not in session:
        return redirect("/login")

    session["buy_now"] = product_id

    return redirect("/checkout")
# -------------------------
# CART
# -------------------------

@app.route("/cart")
def cart():

    if "user_id" not in session:
        return redirect("/login")

    cart_items = Cart.query.filter_by(user_id=session["user_id"]).all()

    items = []
    subtotal = 0

    for c in cart_items:
        product = Product.query.get(c.product_id)

        if product:
            total_price = product.price * c.quantity
            subtotal += total_price

            items.append({
                "product": product,
                "quantity": c.quantity,
                "total": total_price
            })

    settings = PlatformSettings.query.first()
    fee_percent = settings.platform_fee if settings else 2

    platform_fee = round(subtotal * fee_percent / 100)
    total = subtotal + platform_fee

    return render_template(
        "cart.html",
        items=items,
        subtotal=subtotal,
        platform_fee=platform_fee,
        total=total
    )
#remove cart item
@app.route("/remove-cart/<int:product_id>")
def remove_cart(product_id):

    if "user_id" not in session:
        return redirect("/login")

    item = Cart.query.filter_by(
        user_id=session["user_id"],
        product_id=product_id
    ).first()

    if item:
        db.session.delete(item)
        db.session.commit()

    return redirect("/cart")
#cart model
@app.context_processor
def inject_cart_count():
    if "user_id" in session:
        count = Cart.query.filter_by(user_id=session["user_id"]).count()
    else:
        count = 0
    return dict(cart_count=count)

# -------------------------
# CHECKOUT
# 
from datetime import datetime
from sqlalchemy import func

@app.route("/checkout", methods=["GET","POST"])
def checkout():

    if "user_id" not in session:
        return redirect("/login")

    user_id = session["user_id"]

    # -------------------------
    # CART ITEMS
    # -------------------------

    cart_items = Cart.query.filter_by(user_id=user_id).all()

    items = []
    subtotal = 0

    for c in cart_items:

        product = Product.query.get(c.product_id)

        if product:

            item_total = product.price * c.quantity
            subtotal += item_total

            items.append({
                "product": product,
                "quantity": c.quantity,
                "total": item_total
            })

    # -------------------------
    # PLATFORM FEE
    # -------------------------

    settings = PlatformSettings.query.first()
    platform_fee_percent = settings.platform_fee if settings else 5

    platform_fee = round(subtotal * platform_fee_percent / 100, 2)

    discount = 0
    applied_coupon = None

    coupons = Coupon.query.filter_by(active=True).all()

    # -------------------------
    # SAVED DATA
    # -------------------------

    saved_addresses = Address.query.filter_by(user_id=user_id).all()
    saved_payments = PaymentMethod.query.filter_by(user_id=user_id).all()

    total = subtotal + platform_fee

    # -------------------------
    # FORM SUBMIT
    # -------------------------

    if request.method == "POST":

        coupon_code = request.form.get("coupon")

        # -------------------------
        # COUPON APPLY
        # -------------------------

        if coupon_code:

            coupon = Coupon.query.filter_by(
                code=coupon_code.upper(),
                active=True
            ).first()

            if coupon and subtotal >= coupon.min_amount:

                discount = round(subtotal * coupon.discount / 100)
                applied_coupon = coupon.code

            total = subtotal + platform_fee - discount

            return render_template(
                "checkout.html",
                items=items,
                subtotal=subtotal,
                platform_fee=platform_fee,
                platform_fee_percent=platform_fee_percent,
                discount=discount,
                total=total,
                coupons=coupons,
                applied_coupon=applied_coupon,
                saved_addresses=saved_addresses,
                saved_payments=saved_payments
            )

        # -------------------------
        # ADDRESS HANDLING
        # -------------------------

        selected_address = request.form.get("saved_address")

        if selected_address:

            address = Address.query.get(selected_address)

            name = address.name
            email = address.email
            phone = address.phone
            house = address.house
            street = address.street
            state = address.state
            country = address.country
            pincode = address.pincode

        else:

            name = request.form.get("name")
            email = request.form.get("email")
            phone = request.form.get("phone")
            house = request.form.get("house")
            street = request.form.get("street")
            state = request.form.get("state")
            country = request.form.get("country")
            pincode = request.form.get("pincode")

            # -------------------------
            # SAVE ADDRESS
            # -------------------------

            if request.form.get("save_address"):

                new_address = Address(
                    user_id=user_id,
                    address_name=request.form.get("address_name"),
                    name=name,
                    email=email,
                    isd=request.form.get("isd"),
                    phone=phone,
                    secondary_phone=request.form.get("secondary_phone"),
                    house=house,
                    street=street,
                    state=state,
                    country=country,
                    pincode=pincode,
                    is_default=True if request.form.get("default_address") else False
                )

                db.session.add(new_address)
                db.session.commit()

        # -------------------------
        # PAYMENT METHOD
        # -------------------------

        payment_method = request.form.get("saved_payment")

        # -------------------------
        # TOTAL
        # -------------------------

        total = subtotal + platform_fee - discount

        # -------------------------
        # SAVE SESSION
        # -------------------------

        session["checkout"] = {
            "subtotal": subtotal,
            "platform_fee": platform_fee,
            "discount": discount,
            "total": total,
            "coupon_code": applied_coupon,
            "name": name,
            "email": email,
            "phone": phone,
            "house": house,
            "street": street,
            "state": state,
            "country": country,
            "pincode": pincode,
            "payment_method": payment_method
        }

        # -------------------------
        # REDIRECT TO PAYMENT
        # -------------------------

        return redirect("/pay")

    # -------------------------
    # PAGE LOAD
    # -------------------------

    return render_template(
        "checkout.html",
        items=items,
        subtotal=subtotal,
        platform_fee=platform_fee,
        platform_fee_percent=platform_fee_percent,
        discount=discount,
        total=total,
        coupons=coupons,
        applied_coupon=applied_coupon,
        saved_addresses=saved_addresses,
        saved_payments=saved_payments
    )
@app.route("/pay")
def pay():

    if "checkout" not in session:
        return redirect("/checkout")

    checkout = session.get("checkout")

    return render_template(
        "payment.html",
        total=checkout["total"]
    )



# -------------------------
# PAYMENT SUCCESS
# -------------------------
import uuid

@app.route("/payment-success", methods=["POST"])
def payment_success():

    if "user_id" not in session:
        return redirect("/login")

    cart_items = Cart.query.filter_by(user_id=session["user_id"]).all()
    shipping = session.get("checkout")

    if not cart_items or not shipping:
        return redirect("/cart")

    buyer = User.query.get(session["user_id"])

    created_orders = []

    for item in cart_items:

        product = Product.query.get(item.product_id)
        if not product:
            continue

        seller = User.query.get(product.seller)

        order_number = "EDU" + uuid.uuid4().hex[:8].upper()
        transaction_id = "TXN" + uuid.uuid4().hex[:10].upper()

        total_price = product.price * item.quantity

        # -------------------------
        # BUILD FULL ADDRESS
        # -------------------------

        full_address = (
            f"{shipping.get('house','')}, "
            f"{shipping.get('street','')}, "
            f"{shipping.get('state','')}, "
            f"{shipping.get('country','')} - "
            f"{shipping.get('pincode','')}"
        )

        order = Order(
            order_id=order_number,
            transaction_id=transaction_id,
            product_id=product.id,
            buyer_id=buyer.id,
            seller_id=seller.id,
            price=total_price,
            name=shipping.get("name"),
            email=shipping.get("email"),
            phone=shipping.get("phone"),
            address=full_address,
            status="Paid",
            fulfillment_status="Processing"
        )

        db.session.add(order)

        # -------------------------
        # SELLER NOTIFICATION
        # -------------------------

        seller_notification = Notification(
            user_id=seller.id,
            message=f"New order received: {order_number}",
            link="/seller"
        )

        db.session.add(seller_notification)

        created_orders.append((order, product, seller, item.quantity, total_price))

    # -------------------------
    # COMMIT ALL ORDERS
    # -------------------------

    db.session.commit()

    # -------------------------
    # SEND EMAILS + INVOICES
    # -------------------------

    for order, product, seller, qty, total_price in created_orders:

        invoice_pdf = generate_invoice_pdf(order, product, buyer, seller)

        # BUYER EMAIL
        send_email(
            buyer.email,
            "Order Confirmation - Student Marketplace",
            f"""
Hello {buyer.name},

Your order has been placed successfully.

Order ID: {order.order_id}
Product: {product.name}
Quantity: {qty}
Total Price: ₹{total_price}

Your invoice is attached.

Thank you for shopping with Student Marketplace.
""",
            attachment=invoice_pdf,
            filename=f"Invoice_{order.order_id}.pdf"
        )

        # SELLER EMAIL
        send_email(
            seller.email,
            "New Order Received",
            f"""
Hello {seller.name},

You received a new order.

Order ID: {order.order_id}
Product: {product.name}
Quantity: {qty}
Buyer: {buyer.name}

Please fulfill the order from your seller dashboard.
"""
        )

    # -------------------------
    # CLEAR CART
    # -------------------------

    Cart.query.filter_by(user_id=session["user_id"]).delete()
    db.session.commit()

    return redirect("/order-confirmation")

# -------------------------
# ORDER CONFIRMATION PAGE
# -------------------------



@app.route("/order/<int:order_id>")
def order_details(order_id):

    if "user_id" not in session:
        return redirect("/login")

    order = Order.query.get(order_id)

    product = Product.query.get(order.product_id)

    buyer = User.query.get(order.buyer_id)

    return render_template(
        "order_details.html",
        order=order,
        product=product,
        buyer=buyer
    )
#ORDER PAGE

@app.route("/orders")
def orders():

    if "user_id" not in session:
        return redirect("/login")

    user_id = session["user_id"]

    orders = Order.query.filter_by(buyer_id=user_id).all()

    order_list = []

    for o in orders:

        product = Product.query.get(o.product_id)

        # Default image
        image = "noimage.png"

        # Get first product image if exists
        if product and product.images:
            image = product.images[0].image

        order_list.append({
            "id": o.id,
            "order_id": o.order_id,
            "product_id": o.product_id,
            "product_name": product.name if product else "Deleted Product",
            "product_image": image,
            "price": o.price,
            "purchase_time": o.purchase_time,
            "fulfillment_status": o.fulfillment_status,
            "transaction_id": o.transaction_id
        })

    return render_template("orders.html", orders=order_list)

@app.route("/order-confirmation")
def order_confirmation():

    order = Order.query.order_by(Order.id.desc()).first()

    return render_template(
        "orderconfirmation.html",
        order=order
    )



# -------------------------
# BUY NOW
# -------------------------

@app.route("/buy-now/<int:product_id>")
def buy_now(product_id):

    if "user_id" not in session:
        return redirect("/login")

    Cart.query.filter_by(user_id=session["user_id"]).delete()

    item = Cart(
        user_id=session["user_id"],
        product_id=product_id,
        quantity=1
    )

    db.session.add(item)
    db.session.commit()

    return redirect("/checkout")
# -------------------------
# SELL PRODUCT
# -------------------------
from werkzeug.utils import secure_filename
import os

@app.route("/sell", methods=["GET","POST"])
def sell():

    if "user_id" not in session:
        return redirect("/")

    user = User.query.get(session["user_id"])

    if user.role != "seller":
        return "Only sellers can upload products"

    if request.method == "POST":

        name = request.form["name"]
        price = request.form["price"]
        description = request.form["description"]

        category_id = request.form.get("category")
        new_category = request.form.get("new_category")

        # CREATE NEW CATEGORY IF TYPED
        if new_category:

            category = Category.query.filter_by(name=new_category).first()

            if not category:
                category = Category(name=new_category)
                db.session.add(category)
                db.session.commit()

            category_id = category.id


        # CREATE PRODUCT
        product = Product(
            sku=Product.generate_sku(),
            name=name,
            price=price,
            category_id=category_id,
            description=description,
            seller=user.id
        )

        db.session.add(product)
        db.session.commit()


        # HANDLE MULTIPLE IMAGE UPLOAD
        images = request.files.getlist("images")

        for img in images:

            if img.filename != "":

                filename = secure_filename(img.filename)

                upload_path = os.path.join("static/uploads", filename)
                img.save(upload_path)

                product_image = ProductImage(
                    product_id=product.id,
                    image=filename
                )

                db.session.add(product_image)

        db.session.commit()

        return redirect("/dashboard")


    categories = Category.query.all()

    return render_template(
        "sell.html",
        categories=categories
    )
#whislist page
@app.route("/wishlist/<int:product_id>")
def add_wishlist(product_id):

    if "user_id" not in session:
        return redirect("/login")

    # check if already in wishlist
    existing = Wishlist.query.filter_by(
        user_id=session["user_id"],
        product_id=product_id
    ).first()

    if not existing:
        item = Wishlist(
            user_id=session["user_id"],
            product_id=product_id
        )
        db.session.add(item)
        db.session.commit()

    return redirect("/dashboard")
#Notifications page
@app.route("/notifications")
def notifications():

    if "user_id" not in session:
        return redirect("/login")

    notes = Notification.query.filter_by(
        user_id=session["user_id"]
    ).order_by(Notification.created_at.desc()).all()

    return render_template("notification.html", notes=notes)

@app.context_processor
def inject_notifications():

    if "user_id" in session:

        count = Notification.query.filter_by(
            user_id=session["user_id"],
            is_read=False
        ).count()

        return dict(notification_count=count)

    return dict(notification_count=0)
@app.route("/seller/update-order/<int:id>/<status>")
def update_order_status(id, status):

    if "user_id" not in session:
        return redirect("/login")

    order = Order.query.get_or_404(id)

    # -------------------------
    # UPDATE ORDER STATUS
    # -------------------------
    order.fulfillment_status = status

    db.session.commit()

    # -------------------------
    # EMAIL BUYER ABOUT STATUS UPDATE
    # -------------------------

    buyer = User.query.get(order.buyer_id)

    send_email(
        buyer.email,
        "Order Status Update",
        f"""
Order {order.order_id} update

New Status: {status}
"""
    )

    # -------------------------
    # OPTIONAL: NOTIFY BUYER IN APP
    # -------------------------

    note = Notification(
        user_id=buyer.id,
        message=f"Order {order.order_id} status updated to {status}",
        link="/profile"
    )

    db.session.add(note)
    db.session.commit()

    return redirect("/seller")
# -----------------------
if __name__ == "__main__":

    for rule in app.url_map.iter_rules():
        print(rule)

    port = int(os.environ.get("PORT", 10000))

    socketio.run(app, host="0.0.0.0", port=port)


