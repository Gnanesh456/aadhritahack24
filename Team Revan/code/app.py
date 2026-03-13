from flask import Flask, render_template, request, redirect, send_file, session
from pymongo import MongoClient
from werkzeug.utils import secure_filename
import os
from datetime import datetime
import pdfplumber
from google import genai
from pymongo import MongoClient

app = Flask(__name__)

ai_client = genai.Client(api_key="YOUR_NEW_KEY")

@app.route("/ai-chat", methods=["POST"])
def ai_chat():
    try:
        data = request.get_json()
        msg = data.get("message")

        response = ai_client.models.generate_content(
            model="gemini-2.0-flash",
            contents=msg
        )

        return {"reply": response.text}

    except Exception as e:
        print("Gemini Error:", e)
        return {"reply": "AI unavailable"}

app.secret_key = "pettava_secret"

UPLOAD_FOLDER = "uploads"
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)


# MongoDB Connection
mongo_client = MongoClient("mongodb://localhost:27017/")
db = mongo_client["pettava"]

users = db["users"]
resources = db["resources"]


# ---------------- HOME ----------------

@app.route("/")
def home():
    return render_template("home.html")


# ---------------- STUDENT LOGIN ----------------
@app.route("/student/login", methods=["GET","POST"])
def student_login():

    if request.method == "POST":

        email = request.form["email"].strip()
        password = request.form["password"].strip()

        user = users.find_one({
            "email": email,
            "password": password,
            "role": "student"
        })

        if user:
            session["user"] = user["name"]
            session["role"] = "student"
            return redirect("/student")
        else:
            return "Invalid email or password"

    return render_template("login.html", role="Student")

# ---------------- STUDENT SIGNUP ----------------

@app.route("/student/signup", methods=["GET","POST"])
def student_signup():

    if request.method == "POST":

        user = {
            "name":request.form["name"],
            "email":request.form["email"],
            "password":request.form["password"],
            "role":"student"
        }

        users.insert_one(user)

        return redirect("/student/login")

    return render_template("signup.html", role="Student")


# ---------------- TEACHER LOGIN ----------------

@app.route("/teacher/login", methods=["GET","POST"])
def teacher_login():

    if request.method == "POST":

        email = request.form["email"]
        password = request.form["password"]

        user = users.find_one({
            "email":email,
            "password":password,
            "role":"teacher"
        })

        if user:
            session["user"] = user["name"]
            session["role"] = "teacher"
            return redirect("/teacher")

    return render_template("login.html", role="Teacher")


# ---------------- TEACHER SIGNUP ----------------

@app.route("/teacher/signup", methods=["GET","POST"])
def teacher_signup():

    if request.method == "POST":

        user = {
            "name":request.form["name"],
            "email":request.form["email"],
            "password":request.form["password"],
            "role":"teacher"
        }

        users.insert_one(user)

        return redirect("/teacher/login")

    return render_template("signup.html", role="Teacher")


# ---------------- LOGOUT ----------------

@app.route("/logout")
def logout():

    session.clear()

    return redirect("/")


# ---------------- STUDENT PORTAL ----------------

@app.route("/student")
def student():

    if "role" not in session:
        return redirect("/student/login")

    query = request.args.get("search")

    if query:
        data = list(resources.find({
            "$or":[
                {"subject":{"$regex":query,"$options":"i"}},
                {"subject_id":{"$regex":query,"$options":"i"}},
                {"teacher_name":{"$regex":query,"$options":"i"}}
            ]
        }))
    else:
        data = []

    return render_template("student.html", resources=data)


# ---------------- TEACHER PORTAL ----------------

@app.route("/teacher")
def teacher():

    if "role" not in session or session["role"] != "teacher":
        return redirect("/teacher/login")

    data = list(resources.find())

    return render_template("teacher.html", resources=data)

# ---------------- UPLOAD RESOURCE ----------------


@app.route("/student/upload", methods=["GET","POST"])
def student_upload():

        if "role" not in session:
            return redirect("/student/login")

        if request.method == "POST":

            subject = request.form["subject"]
            subject_id = request.form["subject_id"]
            student_name = request.form["student_name"]
            unit = request.form["unit"]
            category = request.form["category"]

            file = request.files["file"]

            filename = secure_filename(file.filename)

            filepath = os.path.join(app.config["UPLOAD_FOLDER"], filename)

            file.save(filepath)

            resource = {

                "subject": subject,
                "subject_id": subject_id,
                "student_name": student_name,
                "unit": unit,
                "category": category,
                "file": filename,
                "verified": False,
                "date": datetime.now().strftime("%d %b %Y  %I:%M %p")

            }

            resources.insert_one(resource)

            return redirect("/student")
        return render_template("student_upload.html")

@app.route("/upload", methods=["GET","POST"])
def upload():

    if "role" not in session or session["role"] != "teacher":
        return redirect("/teacher/login")

    if request.method == "POST":

        subject = request.form["subject"]
        subject_id = request.form["subject_id"]
        teacher_name = request.form["teacher_name"]
        unit = request.form["unit"]
        category = request.form["category"]
        youtube = request.form["youtube"]

        # 🔴 DUPLICATE CHECK
        existing = resources.find_one({
            "subject": subject,
            "subject_id": subject_id,
            "unit": unit,
            "category": category
        })

        if existing:
            return "Duplicate resource already uploaded."

        file = request.files["file"]

        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config["UPLOAD_FOLDER"], filename)

        file.save(filepath)

        resource = {
            "subject": subject,
            "subject_id": subject_id,
            "teacher_name": teacher_name,
            "unit": unit,
            "category": category,
            "file": filename,
            "youtube": youtube,
            "verified": True,
            "date": datetime.now().strftime("%d %b %Y  %I:%M %p")
        }

        resources.insert_one(resource)

        return redirect("/teacher")

    return render_template("upload.html")


# ---------------- FILE PREVIEW ----------------

@app.route("/preview/<filename>")
def preview(filename):

        filepath = os.path.join("uploads", filename)

        summary = quick_summary(filepath)

        return render_template("preview.html", file=filename, summary=summary)


# ---------------- DOWNLOAD ----------------

@app.route("/download/<filename>")
def download(filename):

    return send_file("uploads/" + filename, as_attachment=True)


# ---------------- SERVE FILE ----------------

@app.route("/uploads/<filename>")
def serve_file(filename):

    return send_file("uploads/" + filename)

def quick_summary(filepath):

    text = ""

    try:
        with pdfplumber.open(filepath) as pdf:
            for page in pdf.pages[:2]:
                text += page.extract_text()
    except:
        text = "Preview not available."

    return text[:500]

# ---------------- RUN APP ----------------

if __name__ == "__main__":

    app.run(debug=True)