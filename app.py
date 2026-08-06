import os
import sqlite3
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from werkzeug.security import generate_password_hash, check_password_hash

# ============ APP SETUP ============
app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-change-me")

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "app.db")

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    cur = conn.cursor()
    cur.executescript("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        role TEXT NOT NULL DEFAULT 'user',
        created_at TEXT DEFAULT (datetime('now'))
    );
    CREATE TABLE IF NOT EXISTS lessons (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        content TEXT NOT NULL,
        example_code TEXT,
        two_styles_enabled INTEGER DEFAULT 0,
        style1 TEXT,
        style2 TEXT,
        order_index INTEGER DEFAULT 0
    );
    CREATE TABLE IF NOT EXISTS progress (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        lesson_id INTEGER NOT NULL,
        completed_at TEXT DEFAULT (datetime('now')),
        UNIQUE(user_id, lesson_id)
    );
    """)
    # Seed default admin
    cur.execute("SELECT id FROM users WHERE username=?", ("admin",))
    if cur.fetchone() is None:
        cur.execute("INSERT INTO users (username, password, role) VALUES (?,?,?)",
                    ("admin", generate_password_hash("admin123"), "admin"))
    # Seed default lessons
    cur.execute("SELECT COUNT(*) as c FROM lessons")
    if cur.fetchone()["c"] == 0:
        lessons = [
            ("Hello World - Your First Program",
             "Every programming journey starts here. A Python program runs line by line from top to bottom. The print() function sends text to the screen.\n\n**Concepts:** print(), strings, running a program.",
             'print("Hello, World!")', 1,
             'print("Hello, World!")',
             'message = "Hello, World!"\nprint(message)',
             1),
            ("Variables and Data Types",
             "Variables store data. Python automatically knows the type: integers (whole numbers), floats (decimals), strings (text). Use the type() function to check.",
             'age = 25\nheight = 1.75\nname = "Mukesh"\nprint(age, height, name)\nprint(type(age))', 1,
             'age = 25\nname = "Mukesh"\nprint(name, "is", age)',
             'name = "Mukesh"\nprint(f"{name} is {25}")',
             2),
            ("If-Else - Making Decisions",
             "Conditional statements let your program make decisions. The if statement runs code only when a condition is True. indentation (4 spaces) tells Python what belongs together.",
             'score = 85\nif score >= 90:\n    print("A grade")\nelif score >= 80:\n    print("B grade")\nelse:\n    print("Keep trying!")',
             1,
             'score = 85\nif score >= 80:\n    print("Pass")\nelse:\n    print("Fail")',
             'score = 85\nresult = "Pass" if score >= 80 else "Fail"\nprint(result)',
             3),
            ("Loops - Repeating Tasks",
             "Loops repeat code. A for loop repeats over a sequence (like a list or a range of numbers). A while loop repeats while a condition is True.",
             'for i in range(1, 6):\n    print(i)\n\n# While loop\ncount = 1\nwhile count <= 5:\n    print(count)\n    count += 1',
             1,
             'numbers = [1, 2, 3]\nresult = []\nfor n in numbers:\n    result.append(n * 2)\nprint(result)',
             'numbers = [1, 2, 3]\nresult = [n * 2 for n in numbers]\nprint(result)',
             4),
            ("Functions - Reusable Code",
             "Functions bundle code so you can reuse it. Define with 'def', then call by name. Return sends a value back to the caller.",
             'def greet(name):\n    """Says hello to a person"""\n    return f"Hello, {name}!"\n\nprint(greet("Mukesh"))',
             1,
             'def add(a, b):\n    return a + b\n\nprint(add(3, 5))',
             'add = lambda a, b: a + b\nprint(add(3, 5))',
             5),
        ]
        cur.executemany("INSERT INTO lessons (title, content, example_code, two_styles_enabled, style1, style2, order_index) VALUES (?,?,?,?,?,?,?)", lessons)
    conn.commit()
    conn.close()

init_db()

# ============ AI ENGINE (Free / Groq) ============
# Free AI via Groq (Llama 3.1/3.3) - no API key required in this environment.
# Uses an OpenAI-compatible endpoint. Falls back to a rule-based explainer if AI unavailable.

GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
GROQ_MODEL = os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile")
GROQ_ENDPOINT = "https://api.groq.com/openai/v1/chat/completions"

def ai_explain_code(code, lang="python"):
    """Return step-by-step explanation of pasted code using free AI, with rule-based fallback."""
    if GROQ_API_KEY:
        try:
            import urllib.request, json
            prompt = (
                f"You are a friendly coding tutor. Explain the following {lang} code "
                "line by line in simple, step-by-step language for a beginner. "
                "For each meaningful line, explain WHAT it does and WHY. "
                "Then give a short summary of the whole program. Use clear formatting.\n\n"
                f"CODE:\n{code}"
            )
            body = json.dumps({
                "model": GROQ_MODEL,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.4,
                "max_tokens": 900
            }).encode()
            req = urllib.request.Request(GROQ_ENDPOINT, data=body,
                headers={"Content-Type": "application/json", "Authorization": f"Bearer {GROQ_API_KEY}"})
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read().decode())
                return data["choices"][0]["message"]["content"]
        except Exception as e:
            # fall through to rule-based
            pass
    return rule_based_explain(code)

def rule_based_explain(code):
    """Fallback: simple, grammar-based explanation without any external call."""
    lines = code.split("\n")
    out = ["### 📖 Line-by-line explanation", ""]
    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        if not stripped:
            out.append(f"`{i}.` *(empty line)*")
            continue
        explanation = []
        if stripped.startswith("def "):
            explanation.append("Defines a new **function**. Python will not run this yet — it only remembers the name for later.")
        elif stripped.startswith("for "):
            explanation.append("Starts a **for loop** that repeats over a sequence.")
        elif stripped.startswith("while "):
            explanation.append("Starts a **while loop** that repeats **while** the condition stays True.")
        elif stripped.startswith("if "):
            explanation.append("Starts an **if statement** — runs the indented block only if the condition is True.")
        elif stripped.startswith("elif "):
            explanation.append("**else-if** — tries another condition if earlier ones were False.")
        elif stripped.startswith("else"):
            explanation.append("**else** block — runs when no earlier condition was True.")
        elif stripped.startswith("print"):
            explanation.append("**print()** displays text/value on the screen.")
        elif stripped.startswith("return "):
            explanation.append("**return** sends a value back to whoever called the function.")
        elif stripped.startswith("import "):
            explanation.append("**import** brings in extra code/modules you can use.")
        elif "=" in stripped and "==" not in stripped:
            explanation.append("**Assignment** — stores a value into a variable.")
        elif stripped.startswith("#"):
            explanation.append("**Comment** — text Python ignores; used to explain code to humans.")
        else:
            explanation.append("Executes this statement.")
        out.append(f"`{i}.` {explanation[0]}")
    out.append("")
    out.append("### 💡 Summary")
    out.append("This program reads from top to bottom. Look at the keywords (def, for, if, while, print, return) to understand its overall purpose. The **indented** lines belong to the blocks started by those keywords.")
    return "\n".join(out)

def ai_two_styles(prompt):
    """Generate two styles via AI, with fallback to showing stored lesson styles."""
    if GROQ_API_KEY:
        try:
            import urllib.request, json
            body = json.dumps({
                "model": GROQ_MODEL,
                "messages": [{"role": "user", "content": (
                    "Show two different programming styles (Style A and Style B) to solve the same problem: "
                    + prompt + ". Keep each short with a one-line caption.")}],
                "temperature": 0.5, "max_tokens": 400
            }).encode()
            req = urllib.request.Request(GROQ_ENDPOINT, data=body,
                headers={"Content-Type": "application/json", "Authorization": f"Bearer {GROQ_API_KEY}"})
            with urllib.request.urlopen(req, timeout=30) as resp:
                return json.loads(resp.read().decode())["choices"][0]["message"]["content"]
        except Exception:
            pass
    return "Free AI engine not configured. See lesson examples for two-style demonstrations."

# ============ AUTH HELPERS ============
def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if "user_id" not in session:
            flash("Please log in first.", "warning")
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return wrapper

def admin_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if "user_id" not in session:
            flash("Please log in first.", "warning")
            return redirect(url_for("login"))
        conn = get_db()
        u = conn.execute("SELECT role FROM users WHERE id=?", (session["user_id"],)).fetchone()
        conn.close()
        if not u or u["role"] != "admin":
            flash("Admins only.", "danger")
            return redirect(url_for("dashboard"))
        return f(*args, **kwargs)
    return wrapper

@app.context_processor
def inject_user():
    return {"current_user": None}

# ============ ROUTES ============
@app.route("/")
def index():
    return render_template("index.html")

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form["username"].strip()
        password = request.form["password"]
        if not username or not password:
            flash("Username and password required.", "danger")
            return redirect(url_for("register"))
        conn = get_db()
        try:
            conn.execute("INSERT INTO users (username, password, role) VALUES (?,?,?)",
                         (username, generate_password_hash(password), "user"))
            conn.commit()
            flash("Account created! Please log in.", "success")
            return redirect(url_for("login"))
        except sqlite3.IntegrityError:
            flash("Username already taken.", "danger")
        finally:
            conn.close()
    return render_template("register.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"].strip()
        password = request.form["password"]
        conn = get_db()
        u = conn.execute("SELECT * FROM users WHERE username=?", (username,)).fetchone()
        conn.close()
        if u and check_password_hash(u["password"], password):
            session["user_id"] = u["id"]
            session["username"] = u["username"]
            session["role"] = u["role"]
            flash(f"Welcome back, {u['username']}!", "success")
            return redirect(url_for("dashboard"))
        flash("Invalid username or password.", "danger")
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    flash("Logged out.", "info")
    return redirect(url_for("index"))

@app.route("/dashboard")
@login_required
def dashboard():
    conn = get_db()
    user = conn.execute("SELECT * FROM users WHERE id=?", (session["user_id"],)).fetchone()
    lessons = conn.execute("SELECT l.*, (SELECT 1 FROM progress p WHERE p.lesson_id=l.id AND p.user_id=?) as done FROM lessons l ORDER BY l.order_index", (session["user_id"],)).fetchall()
    completed = conn.execute("SELECT COUNT(*) as c FROM progress WHERE user_id=?", (session["user_id"],)).fetchone()["c"]
    total = conn.execute("SELECT COUNT(*) as c FROM lessons").fetchone()["c"]
    conn.close()
    return render_template("dashboard.html", user=user, lessons=lessons, completed=completed, total=total)

@app.route("/lesson/<int:lid>")
@login_required
def lesson(lid):
    conn = get_db()
    lesson = conn.execute("SELECT * FROM lessons WHERE id=?", (lid,)).fetchone()
    done = conn.execute("SELECT 1 FROM progress WHERE lesson_id=? AND user_id=?", (lid, session["user_id"])).fetchone()
    conn.close()
    if not lesson:
        flash("Lesson not found.", "danger")
        return redirect(url_for("dashboard"))
    return render_template("lesson.html", lesson=lesson, done=done)

@app.route("/lesson/<int:lid>/complete", methods=["POST"])
@login_required
def complete_lesson(lid):
    conn = get_db()
    conn.execute("INSERT OR IGNORE INTO progress (user_id, lesson_id) VALUES (?,?)", (session["user_id"], lid))
    conn.commit()
    conn.close()
    flash("Lesson marked complete 🎉", "success")
    return redirect(url_for("lesson", lid=lid))

@app.route("/explain", methods=["GET", "POST"])
@login_required
def explain():
    explanation = None
    code = None
    if request.method == "POST":
        code = request.form.get("code", "")
        lang = request.form.get("lang", "python")
        if code.strip():
            explanation = ai_explain_code(code, lang)
    return render_template("explain.html", explanation=explanation, code=code)

@app.route("/twostyles", methods=["GET", "POST"])
@login_required
def twostyles():
    result = None
    prompt = None
    if request.method == "POST":
        prompt = request.form.get("prompt", "").strip()
        if prompt:
            result = ai_two_styles(prompt)
    return render_template("twostyles.html", result=result, prompt=prompt)

# ============ ADMIN ROUTES ============
@app.route("/admin")
@admin_required
def admin_dashboard():
    conn = get_db()
    total_users = conn.execute("SELECT COUNT(*) as c FROM users").fetchone()["c"]
    total_lessons = conn.execute("SELECT COUNT(*) as c FROM lessons").fetchone()["c"]
    total_completions = conn.execute("SELECT COUNT(*) as c FROM progress").fetchone()["c"]
    users = conn.execute("SELECT id, username, role, created_at FROM users ORDER BY id").fetchall()
    conn.close()
    return render_template("admin_dashboard.html", total_users=total_users, total_lessons=total_lessons,
                           total_completions=total_completions, users=users)

@app.route("/admin/users")
@admin_required
def admin_users():
    conn = get_db()
    users = conn.execute("SELECT id, username, role, created_at FROM users ORDER BY id").fetchall()
    conn.close()
    return render_template("admin_users.html", users=users)

@app.route("/admin/user/<int:uid>/role", methods=["POST"])
@admin_required
def admin_change_role(uid):
    role = request.form["role"]
    if role not in ("admin", "user"):
        flash("Invalid role.", "danger")
        return redirect(url_for("admin_users"))
    conn = get_db()
    conn.execute("UPDATE users SET role=? WHERE id=?", (role, uid))
    conn.commit()
    conn.close()
    flash("Role updated.", "success")
    return redirect(url_for("admin_users"))

@app.route("/admin/user/<int:uid>/delete", methods=["POST"])
@admin_required
def admin_delete_user(uid):
    conn = get_db()
    conn.execute("DELETE FROM users WHERE id=?", (uid,))
    conn.execute("DELETE FROM progress WHERE user_id=?", (uid,))
    conn.commit()
    conn.close()
    flash("User deleted.", "success")
    return redirect(url_for("admin_users"))

@app.route("/admin/lessons")
@admin_required
def admin_lessons():
    conn = get_db()
    lessons = conn.execute("SELECT * FROM lessons ORDER BY order_index").fetchall()
    conn.close()
    return render_template("admin_lessons.html", lessons=lessons)

@app.route("/admin/lessons/new", methods=["GET", "POST"])
@admin_required
def admin_lesson_new():
    if request.method == "POST":
        title = request.form["title"].strip()
        content = request.form["content"].strip()
        example = request.form.get("example_code", "")
        style1 = request.form.get("style1", "")
        style2 = request.form.get("style2", "")
        two = 1 if request.form.get("two_styles") else 0
        order = int(request.form.get("order_index", 0) or 0)
        if not title or not content:
            flash("Title and content required.", "danger")
            return redirect(url_for("admin_lesson_new"))
        conn = get_db()
        conn.execute("INSERT INTO lessons (title, content, example_code, two_styles_enabled, style1, style2, order_index) VALUES (?,?,?,?,?,?,?)",
                     (title, content, example, two, style1, style2, order))
        conn.commit()
        conn.close()
        flash("Lesson added.", "success")
        return redirect(url_for("admin_lessons"))
    return render_template("admin_lesson_form.html", lesson=None)

@app.route("/admin/lessons/<int:lid>/edit", methods=["GET", "POST"])
@admin_required
def admin_lesson_edit(lid):
    conn = get_db()
    lesson = conn.execute("SELECT * FROM lessons WHERE id=?", (lid,)).fetchone()
    if request.method == "POST":
        title = request.form["title"].strip()
        content = request.form["content"].strip()
        example = request.form.get("example_code", "")
        style1 = request.form.get("style1", "")
        style2 = request.form.get("style2", "")
        two = 1 if request.form.get("two_styles") else 0
        order = int(request.form.get("order_index", 0) or 0)
        conn.execute("UPDATE lessons SET title=?, content=?, example_code=?, two_styles_enabled=?, style1=?, style2=?, order_index=? WHERE id=?",
                     (title, content, example, two, style1, style2, order, lid))
        conn.commit()
        conn.close()
        flash("Lesson updated.", "success")
        return redirect(url_for("admin_lessons"))
    conn.close()
    return render_template("admin_lesson_form.html", lesson=lesson)

@app.route("/admin/lessons/<int:lid>/delete", methods=["POST"])
@admin_required
def admin_lesson_delete(lid):
    conn = get_db()
    conn.execute("DELETE FROM lessons WHERE id=?", (lid,))
    conn.execute("DELETE FROM progress WHERE lesson_id=?", (lid,))
    conn.commit()
    conn.close()
    flash("Lesson deleted.", "success")
    return redirect(url_for("admin_lessons"))

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
