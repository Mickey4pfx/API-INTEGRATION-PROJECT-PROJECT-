import sqlite3
from flask import Flask, g, jsonify, request

app = Flask(__name__)
DB = "students.db"
FIELDS = ("name", "email", "course", "age")


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DB)
        g.db.row_factory = sqlite3.Row
    return g.db


@app.teardown_appcontext
def close_db(_):
    db = g.pop("db", None)
    if db:
        db.close()


def init_db():
    with sqlite3.connect(DB) as db:
        db.execute(
            """CREATE TABLE IF NOT EXISTS students (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT NOT NULL UNIQUE,
                course TEXT NOT NULL,
                age INTEGER
            )"""
        )


def row_to_dict(row):
    return dict(row)


def error(message, code):
    return jsonify({"success": False, "error": message}), code


def validate(data, partial=False):
    if not isinstance(data, dict):
        return "Request body must be JSON"
    if not partial:
        for f in ("name", "email", "course"):
            if not str(data.get(f, "")).strip():
                return f"'{f}' is required"
    if "email" in data and "@" not in str(data["email"]):
        return "Invalid email"
    if "age" in data and data["age"] is not None:
        if not isinstance(data["age"], int) or not 5 <= data["age"] <= 100:
            return "'age' must be an integer between 5 and 100"
    return None


# CREATE
@app.route("/students", methods=["POST"])
def create_student():
    data = request.get_json(silent=True)
    err = validate(data)
    if err:
        return error(err, 400)
    db = get_db()
    try:
        cur = db.execute(
            "INSERT INTO students (name, email, course, age) VALUES (?, ?, ?, ?)",
            (data["name"].strip(), data["email"].strip(), data["course"].strip(), data.get("age")),
        )
        db.commit()
    except sqlite3.IntegrityError:
        return error("Email already registered", 409)
    row = db.execute("SELECT * FROM students WHERE id = ?", (cur.lastrowid,)).fetchone()
    return jsonify({"success": True, "data": row_to_dict(row)}), 201


# READ ALL + SEARCH  (?q=john&course=CS)
@app.route("/students", methods=["GET"])
def list_students():
    q = request.args.get("q", "").strip()
    course = request.args.get("course", "").strip()
    sql, params = "SELECT * FROM students WHERE 1=1", []
    if q:
        sql += " AND (name LIKE ? OR email LIKE ?)"
        params += [f"%{q}%", f"%{q}%"]
    if course:
        sql += " AND course LIKE ?"
        params.append(f"%{course}%")
    rows = get_db().execute(sql + " ORDER BY id", params).fetchall()
    return jsonify({"success": True, "count": len(rows), "data": [row_to_dict(r) for r in rows]})


# READ ONE
@app.route("/students/<int:student_id>", methods=["GET"])
def get_student(student_id):
    row = get_db().execute("SELECT * FROM students WHERE id = ?", (student_id,)).fetchone()
    if not row:
        return error("Student not found", 404)
    return jsonify({"success": True, "data": row_to_dict(row)})


# UPDATE
@app.route("/students/<int:student_id>", methods=["PUT"])
def update_student(student_id):
    data = request.get_json(silent=True)
    err = validate(data, partial=True)
    if err:
        return error(err, 400)
    updates = {k: data[k] for k in FIELDS if k in data}
    if not updates:
        return error("No valid fields to update", 400)
    db = get_db()
    if not db.execute("SELECT 1 FROM students WHERE id = ?", (student_id,)).fetchone():
        return error("Student not found", 404)
    set_clause = ", ".join(f"{k} = ?" for k in updates)
    try:
        db.execute(f"UPDATE students SET {set_clause} WHERE id = ?", [*updates.values(), student_id])
        db.commit()
    except sqlite3.IntegrityError:
        return error("Email already registered", 409)
    row = db.execute("SELECT * FROM students WHERE id = ?", (student_id,)).fetchone()
    return jsonify({"success": True, "data": row_to_dict(row)})


# DELETE
@app.route("/students/<int:student_id>", methods=["DELETE"])
def delete_student(student_id):
    db = get_db()
    cur = db.execute("DELETE FROM students WHERE id = ?", (student_id,))
    db.commit()
    if cur.rowcount == 0:
        return error("Student not found", 404)
    return jsonify({"success": True, "message": "Student deleted"})


@app.errorhandler(404)
def not_found(_):
    return error("Route not found", 404)


@app.errorhandler(405)
def bad_method(_):
    return error("Method not allowed", 405)


init_db()  # also runs under `flask run`

if __name__ == "__main__":
    app.run(debug=True)
