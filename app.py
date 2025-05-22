import sqlite3
from flask import Flask, render_template, request, redirect, url_for, session
from flask_cors import CORS
from core import init_db, get_db_connection, P_DB
from api import api_bp

app = Flask(__name__)
app.secret_key = "supersecretkey"
CORS(app)
app.register_blueprint(api_bp)

@app.route("/login", methods=["GET", "POST"])
def login():
    # If user is already logged in, redirect to map
    if "username" in session:
        return redirect(url_for("index"))

    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")

        conn = get_db_connection(P_DB)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM users WHERE username = ? AND password = ?",
            (username, password)
        )
        user = cursor.fetchone()
        conn.close()

        if user:
            session["username"] = username
            return redirect(url_for("index"))
        else:
            return "Invalid credentials!", 401

    return render_template("login.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")

        conn = get_db_connection(P_DB)
        cursor = conn.cursor()
        try:
            cursor.execute(
                "INSERT INTO users (username, password) VALUES (?, ?)",
                (username, password)
            )
            conn.commit()
        except sqlite3.IntegrityError:
            conn.close()
            return "Username already exists!", 400
        conn.close()

        return redirect(url_for("login"))

    return render_template("register.html")

@app.route("/")
def index():
    if "username" not in session:
        return redirect(url_for("login"))
    return render_template("index.html", username=session["username"])

@app.route("/logout")
def logout():
    session.pop("username", None)      # forget logged-in user
    return redirect(url_for("login"))  # show the login page

if __name__ == "__main__":
    init_db()  # Ensure tables exist before running
    app.run(debug=True)