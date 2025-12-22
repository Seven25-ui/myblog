import os
import secrets
import logging
from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import pytz  # pip install pytz

# --- APP SETUP ---
app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", secrets.token_hex(16))

# --- LOGGING (for Render production) ---
if not app.debug:
    stream_handler = logging.StreamHandler()
    stream_handler.setLevel(logging.ERROR)
    formatter = logging.Formatter("[%(asctime)s] %(levelname)s in %(module)s: %(message)s")
    stream_handler.setFormatter(formatter)
    app.logger.addHandler(stream_handler)

# --- DATABASE (Render + local safe) ---
basedir = os.path.abspath(os.path.dirname(__file__))
instance_path = os.path.join(basedir, "instance")
os.makedirs(instance_path, exist_ok=True)
db_path = os.path.join(instance_path, "myblog.db")
app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{db_path}"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)

# --- TIMEZONE ---
local_tz = pytz.timezone("Asia/Manila")

# --- MODELS ---
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), nullable=False, unique=True)
    password = db.Column(db.String(200), nullable=False)
    profile_pic = db.Column(db.String(200), default="https://i.pravatar.cc/150?img=3")
    posts = db.relationship("Post", backref="user", lazy=True)
    comments = db.relationship("Comment", backref="user", lazy=True)
    reactions = db.relationship("Reaction", backref="user", lazy=True)

class Post(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    content = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, default=lambda: datetime.now(local_tz))
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    comments = db.relationship("Comment", backref="post", lazy=True, cascade="all, delete-orphan")
    reactions = db.relationship("Reaction", backref="post", lazy=True, cascade="all, delete-orphan")

class Comment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, default=lambda: datetime.now(local_tz))
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
        user = User.query.filter_by(username=request.form["username"]).first()
        if user and check_password_hash(user.password, request.form["password"]):
            session["user_id"] = user.id
            session["username"] = user.username
            session["profile_pic"] = user.profile_pic
            return redirect(url_for("dashboard"))
        error = "Invalid username or password"
    return render_template("login.html", error=error)

@app.route("/signup", methods=["GET", "POST"])
def signup():
    error = None
    if request.method == "POST":
        if User.query.filter_by(username=request.form["username"]).first():
            error = "Username already exists!"
        else:
            user = User(
                username=request.form["username"],
                password=generate_password_hash(request.form["password"])
            )
            db.session.add(user)
            db.session.commit()
            session["user_id"] = user.id
            session["username"] = user.username
            session["profile_pic"] = user.profile_pic
            return redirect(url_for("dashboard"))
    return render_template("signup.html", error=error)

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

@app.route("/dashboard")
def dashboard():
    if "user_id" not in session:
        return redirect(url_for("login"))
    page = request.args.get("page", 1, type=int)
    per_page = 5
    posts = Post.query.order_by(Post.timestamp.desc()).limit(per_page).offset((page-1)*per_page).all()
    return render_template("dashboard.html", posts=posts, page=page)

@app.route("/add", methods=["GET", "POST"])
def add_post():
    if "user_id" not in session:
        return redirect(url_for("login"))
    if request.method == "POST":
        post = Post(title=request.form["title"], content=request.form["content"], user_id=session["user_id"])
        db.session.add(post)
        db.session.commit()
        flash("Post added successfully!")
        return redirect(url_for("dashboard"))
    return render_template("add_post.html")

@app.route("/edit/<int:post_id>", methods=["GET", "POST"])
def edit_post(post_id):
    if "user_id" not in session:
        return redirect(url_for("login"))
    post = Post.query.get_or_404(post_id)
    if post.user_id != session["user_id"]:
        return redirect(url_for("dashboard"))
    if request.method == "POST":
        post.title = request.form["title"]
        post.content = request.form["content"]
        db.session.commit()
        flash("Post updated!")
        return redirect(url_for("dashboard"))
    return render_template("edit_post.html", post=post)

@app.route("/delete/<int:post_id>", methods=["POST"])
def delete_post(post_id):
    if "user_id" not in session:
        return redirect(url_for("login"))
    post = Post.query.get_or_404(post_id)
    if post.user_id != session["user_id"]:
        return redirect(url_for("dashboard"))
    db.session.delete(post)
    db.session.commit()
    flash("Post deleted!")
    return redirect(url_for("dashboard"))

@app.route("/comment/<int:post_id>", methods=["POST"])
def add_comment(post_id):
    if "user_id" not in session:
        return redirect(url_for("login"))
    comment = Comment(content=request.form["comment"], post_id=post_id, user_id=session["user_id"])
    db.session.add(comment)
    db.session.commit()
    flash("Comment added!")
    return redirect(url_for("dashboard"))

@app.route("/react/<int:post_id>/<emoji>")
def react(post_id, emoji):
    if "user_id" not in session:
        return redirect(url_for("login"))
    db.session.add(Reaction(emoji=emoji, post_id=post_id, user_id=session["user_id"]))
    db.session.commit()
    return redirect(url_for("dashboard"))

# --- RUN APP (Production-ready) ---
if __name__ == "__main__":
    with app.app_context():
        db.create_all()
        # Auto-create admin if no users exist
        if not User.query.filter_by(username="admin").first():
            admin_user = User(username="admin", password=generate_password_hash("admin123"))
            db.session.add(admin_user)
            db.session.commit()
            app.logger.info("Admin created: username=admin, password=admin123")

    port = int(os.environ.get("PORT", 10000))
    # Only run dev server locally
    if os.environ.get("FLASK_ENV") == "development":
        app.run(host="0.0.0.0", port=port, debug=True)
    # In production (Render), Gunicorn will run the app, no print needed
