import os
import secrets
import logging
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import pytz

# --- APP SETUP ---
app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", secrets.token_hex(16))

# --- LOGGING ---
if not app.debug:
    handler = logging.StreamHandler()
    handler.setLevel(logging.INFO)
    app.logger.addHandler(handler)

# --- DATABASE ---
basedir = os.path.abspath(os.path.dirname(__file__))
instance_path = os.path.join(basedir, "instance")
os.makedirs(instance_path, exist_ok=True)

db_path = os.path.join(instance_path, "myblog.db")
app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{db_path}"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db = SQLAlchemy(app)

# --- TIMEZONE ---
local_tz = pytz.timezone("Asia/Manila")

# ---------- MODELS ----------
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
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

# ---------- ROUTES ----------
@app.route("/")
def home():
    return redirect(url_for("dashboard") if "user_id" in session else url_for("login"))

# --- AUTH ---
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
        error = "Invalid credentials"
    return render_template("login.html", error=error)

@app.route("/signup", methods=["GET", "POST"])
def signup():
    error = None
    if request.method == "POST":
        if User.query.filter_by(username=request.form["username"]).first():
            error = "Username exists"
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

# --- DASHBOARD / FEED ---
@app.route("/dashboard")
def dashboard():
    if "user_id" not in session:
        return redirect(url_for("login"))
    posts = Post.query.order_by(Post.timestamp.desc()).all()
    return render_template("dashboard.html", posts=posts, profile_pic=session.get("profile_pic"))

# --- ADD POST ---
@app.route("/add", methods=["GET", "POST"])
def add_post():
    if "user_id" not in session:
        return redirect(url_for("login"))
    if request.method == "POST":
        post = Post(
            title=request.form["title"],
            content=request.form["content"],
            user_id=session["user_id"]
        )
        db.session.add(post)
        db.session.commit()
        flash("Post added!")
        return redirect(url_for("dashboard"))
    return render_template("add_post.html")

# --- EDIT POST ---
@app.route("/edit/<int:post_id>", methods=["GET", "POST"])
def edit_post(post_id):
    if "user_id" not in session:
        return redirect(url_for("login"))
    post = Post.query.get_or_404(post_id)
    if post.user_id != session["user_id"]:
        flash("Not allowed")
        return redirect(url_for("dashboard"))
    if request.method == "POST":
        post.title = request.form["title"]
        post.content = request.form["content"]
        db.session.commit()
        flash("Post updated!")
        return redirect(url_for("dashboard"))
    return render_template("edit_post.html", post=post)

# --- DELETE POST ---
@app.route("/delete/<int:post_id>", methods=["POST"])
def delete_post(post_id):
    if "user_id" not in session:
        return redirect(url_for("login"))
    post = Post.query.get_or_404(post_id)
    if post.user_id != session["user_id"]:
        flash("Not allowed")
        return redirect(url_for("dashboard"))
    db.session.delete(post)
    db.session.commit()
    flash("Post deleted!")
    return redirect(url_for("dashboard"))

# --- ADD COMMENT ---
@app.route("/add_comment/<int:post_id>", methods=["POST"])
def add_comment(post_id):
    if "user_id" not in session:
        return redirect(url_for("login"))
    comment = Comment(
        content=request.form["comment"],
        post_id=post_id,
        user_id=session["user_id"]
    )
    db.session.add(comment)
    db.session.commit()
    flash("Comment added!")
    return redirect(url_for("dashboard"))

# --- REACTIONS ---
@app.route("/react/<int:post_id>", methods=["POST"])
def react(post_id):
    emoji = request.form.get("emoji")
    if emoji and "user_id" in session:
        existing = Reaction.query.filter_by(post_id=post_id, user_id=session["user_id"], emoji=emoji).first()
        if not existing:
            db.session.add(Reaction(
                emoji=emoji,
                post_id=post_id,
                user_id=session["user_id"]
            ))
            db.session.commit()
    return redirect(url_for("dashboard"))

# --- PROFILE PIC UPDATE ---
@app.route("/update_profile_pic", methods=["POST"])
def update_profile_pic():
    if "user_id" not in session:
        return redirect(url_for("login"))
    file = request.files.get("profile_pic")
    if file and file.filename:
        filename = secrets.token_hex(8) + "_" + file.filename
        path = os.path.join("static/uploads", filename)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        file.save(path)
        user = User.query.get(session["user_id"])
        user.profile_pic = url_for("static", filename=f"uploads/{filename}")
        db.session.commit()
        session["profile_pic"] = user.profile_pic
    return redirect(url_for("dashboard"))

# --- PROFILE PAGE (ONLY ONE ROUTE NOW) ---
@app.route("/profile")
def my_profile():
    if "user_id" not in session:
        return redirect(url_for("login"))
    user = User.query.get(session["user_id"])
    posts = Post.query.filter_by(user_id=user.id).order_by(Post.timestamp.desc()).all()
    return render_template("profile.html", user=user, posts=posts)

# --- OTHER PAGES (Under Construction) ---
@app.route("/settings")
def settings_page():
    if "user_id" not in session:
        return redirect(url_for("login"))
    return "<h2>Settings Page (Under Construction)</h2>"

@app.route("/search")
def search_page():
    if "user_id" not in session:
        return redirect(url_for("login"))
    return "<h2>Search Page (Under Construction)</h2>"

@app.route("/messages")
def messages_page():
    if "user_id" not in session:
        return redirect(url_for("login"))
    return "<h2>Messages Page (Under Construction)</h2>"

@app.route("/notifications")
def notifications_page():
    if "user_id" not in session:
        return redirect(url_for("login"))
    return "<h2>Notifications Page (Under Construction)</h2>"

# --- JSON FEED FOR TABS ---
@app.route("/feed/<tab>")
def feed_tab(tab):
    if "user_id" not in session:
        return jsonify([])

    if tab == "discover":
        posts = Post.query.order_by(Post.timestamp.desc()).all()
    elif tab == "following":
        following_ids = [2,3]  # example
        posts = Post.query.filter(Post.user_id.in_(following_ids)).order_by(Post.timestamp.desc()).all()
    elif tab == "videos":
        posts = Post.query.filter(Post.content.ilike("%video%")).order_by(Post.timestamp.desc()).all()
    else:
        posts = []

    data = []
    for post in posts:
        data.append({
            "id": post.id,
            "title": post.title,
            "content": post.content,
            "username": post.user.username,
            "profile_pic": post.user.profile_pic,
            "timestamp": post.timestamp.strftime("%Y-%m-%d %H:%M"),
            "reactions": [{"emoji": r.emoji} for r in post.reactions],
            "comments": [{"username": c.user.username, "content": c.content} for c in post.comments]
        })
    return jsonify(data)

# ---------- RUN ----------
if __name__ == "__main__":
    with app.app_context():
        db.create_all()
        if not User.query.filter_by(username="admin").first():
            db.session.add(User(
                username="admin",
                password=generate_password_hash("admin123")
            ))
            db.session.commit()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=True)
