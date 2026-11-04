from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3
import re
from difflib import SequenceMatcher

app = Flask(__name__)
app.secret_key = "replace-this-secret-key-before-deployment"
DB = "medicare.db"

def connect():
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    return con

def init_db():
    with connect() as con:
        con.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL,
                age INTEGER NOT NULL CHECK(age BETWEEN 1 AND 120)
            )
        """)
        con.execute("""
            CREATE TABLE IF NOT EXISTS medicines (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                medicine_name TEXT NOT NULL,
                brand_names TEXT DEFAULT '',
                composition TEXT DEFAULT '',
                manufacturer TEXT DEFAULT '',
                price TEXT DEFAULT '',
                dosage_form TEXT DEFAULT '',
                uses TEXT DEFAULT '',
                side_effects TEXT DEFAULT '',
                age_precautions TEXT DEFAULT '',
                dosage_info TEXT DEFAULT '',
                warnings TEXT DEFAULT '',
                source TEXT DEFAULT '',
                verified_status TEXT DEFAULT ''
            )
        """)
        con.execute("CREATE INDEX IF NOT EXISTS idx_medicine_name ON medicines(medicine_name)")
        con.execute("CREATE INDEX IF NOT EXISTS idx_composition ON medicines(composition)")

def normalize(value):
    return re.sub(r"[^a-z0-9 ]", " ", (value or "").lower()).strip()

def search_medicines(query, limit=20):
    q = normalize(query)
    if not q:
        return []
    like = "%" + q + "%"
    with connect() as con:
        rows = con.execute("""
            SELECT * FROM medicines
            WHERE lower(medicine_name) LIKE ?
               OR lower(brand_names) LIKE ?
               OR lower(composition) LIKE ?
               OR lower(manufacturer) LIKE ?
            ORDER BY medicine_name
            LIMIT ?
        """, (like, like, like, like, limit)).fetchall()

        if rows:
            return rows

        # Fuzzy fallback for small spelling mistakes in medicine/product names.
        all_rows = con.execute("SELECT * FROM medicines LIMIT 5000").fetchall()
        scored = []
        for row in all_rows:
            candidate = normalize(row["medicine_name"])
            score = SequenceMatcher(None, q, candidate).ratio()
            if score >= 0.68:
                scored.append((score, row))
        scored.sort(key=lambda item: item[0], reverse=True)
        return [item[1] for item in scored[:limit]]

@app.route("/")
def home():
    if "user_id" not in session:
        return redirect(url_for("login"))
    with connect() as con:
        count = con.execute("SELECT COUNT(*) FROM medicines").fetchone()[0]
    return render_template("home.html", user=session, medicine_count=count)

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        try:
            age = int(request.form.get("age", ""))
            if not 1 <= age <= 120:
                raise ValueError
        except ValueError:
            flash("Enter a valid age between 1 and 120.")
            return render_template("register.html")

        if not name or not email or len(password) < 6:
            flash("Fill all fields. Password must contain at least 6 characters.")
            return render_template("register.html")

        try:
            with connect() as con:
                cur = con.execute(
                    "INSERT INTO users(name,email,password,age) VALUES(?,?,?,?)",
                    (name, email, generate_password_hash(password), age)
                )
                user_id = cur.lastrowid
            session.update(user_id=user_id, name=name, age=age, email=email)
            return redirect(url_for("home"))
        except sqlite3.IntegrityError:
            flash("This email is already registered. Please log in.")
    return render_template("register.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        with connect() as con:
            user = con.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
        if user and check_password_hash(user["password"], password):
            session.update(user_id=user["id"], name=user["name"], age=user["age"], email=user["email"])
            return redirect(url_for("home"))
        flash("Incorrect email or password.")
    return render_template("login.html")

@app.route("/search", methods=["GET", "POST"])
def search():
    if "user_id" not in session:
        return redirect(url_for("login"))
    query = request.values.get("medicine", "").strip()
    results = search_medicines(query) if query else []
    return render_template("result.html", results=results, query=query, age=session.get("age"))

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

if __name__ == "__main__":
    init_db()
    app.run(debug=True)
