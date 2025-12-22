import os
import secrets
from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", secrets.token_hex(16))

# --- SQLite setup ---
basedir = os.path.abspath(os.path.dirname(__file__))
instance_path = os.path.join(basedir, "instance")
os.makedirs(instance_path, exist_ok=True)

db_path = os.path.join(instance_path, "myblog.db")
app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{db_path}"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)

# --- MODELS ---
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), nullable=False, unique=True)
    password = db.Column(db.String(200), nullable=False)
    profile_pic = db.Column(
        db.String(200),
        default="https://i.pravatar.cc/150?img=3"
    )
    posts = db.relationship("Post", backref="user", lazy=True)
    comments = db.relationship("Comment", backref="user", lazy=True)
    reactions = db.relationship("Reaction", backref="user", lazy=True)

class Post(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    content = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    comments = db.relationship(
        "Comment",
        backref="post",
        lazy=True,
        cascade="all, delete-orphan"
    )
    reactions = db.relationship(
        "Reaction",
        backref="post",
        lazy=True,
        cascade="all, delete-orphan"
    )

class Comment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    post_id = db.Column(db.Integer, db.ForeignKey("post.id"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)

class Reaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    emoji = db.Column(db.String(10), nullable=False)
    post_id = db.Column(db.Integer, db.ForeignKey("post.id"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)

# --- ROUTES ---
@app.route("/")
def home():
    return redirect(url_for("dashboard") if "user_id" in session else url_for("login"))

@app.route("/login", methods=["GET", "POST"])
def login():
    error = None
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()

        if not username or not password:
            error = "All fields are required"
        else:
            user = User.query.filter_by(username=username).first()
            if user and check_password_hash(user.password, password):
                session["user_id"] = user.id
                session["username"] = user.username
                session["profile_pic"] = user.profile_pic
                flash("Login successful!")
                return redirect(url_for("dashboard"))
            else:
                error = "Invalid username or password"

    return render_template("login.html", error=error)

@app.route("/signup", methods=["GET", "POST"])
def signup():
    error = None
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()

        if not username or not password:
            error = "All fields are required"
        elif User.query.filter_by(username=username).first():
            error = "Username already exists!"
        else:
            user = User(
                username=username,
                password=generate_password_hash(password)
            )
            db.session.add(user)
            db.session.commit()
            session["user_id"] = user.id
            session["username"] = user.username
            session["profile_pic"] = user.profile_pic
            flash("Account created successfully!")
            return redirect(url_for("dashboard"))

    return render_template("signup.html", error=error)

@app.route("/logout")
def logout():
    session.clear()
    flash("Logged out successfully")
    return redirect(url_for("login"))

@app.route("/dashboard")
def dashboard():
    if "user_id" not in session:
        return redirect(url_for("login"))
    posts = Post.query.order_by(Post.timestamp.desc()).all()
    return render_template("dashboard.html", posts=posts)

@app.route("/add", methods=["GET", "POST"])
def add_post():
    if "user_id" not in session:
        return redirect(url_for("login"))

    if request.method == "POST":
        title = request.form.get("title", "").strip()
        content = request.form.get("content", "").strip()
        if title and content:
            post = Post(title=title, content=content, user_id=session["user_id"])
            db.session.add(post)
            db.session.commit()
            flash("Post added successfully!")
            return redirect(url_for("dashboard"))
        else:
            flash("Title and content cannot be empty")

    return render_template("add_post.html")

# --- Edit, Delete, Comment, React routes same as previous version ---
# (They are already safe and functional)

# --- RUN ---
if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port, debug=True)
