from flask import redirect, url_for
import fitz  # PyMuPDF
from docx import Document
import pandas as pd
import pandas as pd
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer
)
from reportlab.lib.styles import getSampleStyleSheet
from flask import send_file
import os
from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import (
    LoginManager, UserMixin, login_user,
    login_required, logout_user, current_user
)
from matplotlib import text
from werkzeug.security import generate_password_hash, check_password_hash
from transformers import pipeline

classifier = pipeline(
    "sentiment-analysis",
    model="cardiffnlp/twitter-roberta-base-sentiment-latest"
)

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_secret_key'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'

db = SQLAlchemy(app)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"

# Database Models
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True)
    password = db.Column(db.String(200))

class Sentiment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    text = db.Column(db.Text)
    result = db.Column(db.String(50))
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

@app.route("/")
def home():
    return redirect(url_for("login"))

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form["username"]
        password = generate_password_hash(request.form["password"])

        user = User(username=username, password=password)
        db.session.add(user)
        db.session.commit()

        flash("Registration successful!")
        return redirect(url_for("login"))

    return render_template("register.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        user = User.query.filter_by(username=username).first()

        if user and check_password_hash(user.password, password):
            login_user(user)
            return redirect(url_for("dashboard"))

        flash("Invalid credentials")

    return render_template("login.html")

@app.route("/dashboard", methods=["GET", "POST"])
@login_required
def dashboard():

    sentiment = ""

    if request.method == "POST":
        
        text = request.form.get("text", "").strip()

        if text:

            result = classifier(text)[0]

            label = result["label"].lower()

            if "positive" in label:
                sentiment = "Positive"
            elif "negative" in label:
                sentiment = "Negative"
            else:
                sentiment = "Neutral"

            record = Sentiment(
                text=text,
                result=sentiment,
                user_id=current_user.id
            )

            existing = Sentiment.query.filter_by(
                text=str(text),
                user_id=current_user.id
            ).first()

            if not existing:
                db.session.add(record)
                db.session.commit()

        file = request.files.get("csv_file")

        texts = []

        if file and file.filename:
            if file.filename.endswith(".csv"):
                df = pd.read_csv(file)

                if "text" in df.columns:
                    texts = df["text"]
                elif "Post" in df.columns:
                    texts = df["Post"]
                else:
                    return "File must contain either 'text' or 'Post' column."

            elif file.filename.endswith(".xlsx"):
                df = pd.read_excel(file)

                if "text" in df.columns:
                    texts = df["text"]
                elif "Post" in df.columns:
                    texts = df["Post"]
                else:
                    return "File must contain either 'text' or 'Post' column."

            elif file.filename.endswith(".pdf"):
                pdf = fitz.open(stream=file.read(), filetype="pdf")

                for page in pdf:
                    texts.append(page.get_text())

            elif file.filename.endswith(".docx"):
                doc = Document(file)

                for para in doc.paragraphs:
                    texts.append(para.text)

            else:
                return "Supported formats: CSV, Excel, PDF, DOCX"

            for text in texts:
                result = classifier(str(text))[0]

                label = result["label"].lower()

                if "positive" in label:
                    sentiment = "Positive"
                elif "negative" in label:
                    sentiment = "Negative"
                else:
                    sentiment = "Neutral"

                record = Sentiment(
                    text=str(text),
                    result=sentiment,
                    user_id=current_user.id
                )

                existing = Sentiment.query.filter_by(
                    text=str(text),
                    user_id=current_user.id
                ).first()

                if not existing:
                    db.session.add(record)
                    db.session.commit()

    records = Sentiment.query.filter_by(
                user_id=current_user.id
            ).all()

    return render_template(
                "dashboard.html",
                sentiment=sentiment,
                records=records
            )
    

@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("login"))

@app.route("/download_report")
@login_required
def download_report():

    filename = "SocialPulse_Report.pdf"

    doc = SimpleDocTemplate(filename)
    styles = getSampleStyleSheet()

    story = []

    title = Paragraph(
        "<b>SocialPulse AI Report</b>",
        styles["Title"]
    )

    story.append(title)
    story.append(Spacer(1, 20))

    records = Sentiment.query.filter_by(
        user_id=current_user.id
    ).all()

    positive = 0
    negative = 0
    neutral = 0

    for r in records:

        text = f"{r.text} → {r.result}"

        story.append(
            Paragraph(text, styles["BodyText"])
        )

        story.append(Spacer(1, 10))

        if r.result == "Positive":
            positive += 1
        elif r.result == "Negative":
            negative += 1
        else:
            neutral += 1

    story.append(
        Paragraph(
            f"<br/><b>Positive:</b> {positive}",
            styles["BodyText"]
        )
    )

    story.append(
        Paragraph(
            f"<b>Negative:</b> {negative}",
            styles["BodyText"]
        )
    )

    story.append(
        Paragraph(
            f"<b>Neutral:</b> {neutral}",
            styles["BodyText"]
        )
    )

    doc.build(story)

    return send_file(
        filename,
        as_attachment=True
    )

from flask import send_file
import pandas as pd

@app.route("/export_excel")
@login_required
def export_excel():

    records = Sentiment.query.filter_by(
        user_id=current_user.id
    ).all()

    data = []

    for r in records:
        data.append({
            "Post": r.text,
            "Sentiment": r.result
        })

    df = pd.DataFrame(data)

    filename = "sentiment_report.xlsx"

    df.to_excel(
        filename,
        index=False
    )

    return send_file(
        filename,
        as_attachment=True
    )
@app.route("/delete/<int:id>")
@login_required
def delete_record(id):

    record = Sentiment.query.get_or_404(id)

    if record.user_id == current_user.id:
        db.session.delete(record)
        db.session.commit()

    return redirect(url_for("dashboard"))
@app.route("/charts")
@login_required
def charts():
    return render_template("charts.html")
if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    
    app.run(host="0.0.0.0", port=5000)
@app.route("/history")
@login_required
def history():
    records = Sentiment.query.filter_by(
        user_id=current_user.id
    ).all()

    return render_template(
        "history.html",
        records=records
    )
import os
import matplotlib.pyplot as plt
positive = Sentiment.query.filter_by(
    result="Positive",
    user_id=current_user.id
).count()

negative = Sentiment.query.filter_by(
    result="Negative",
    user_id=current_user.id
).count()

neutral = Sentiment.query.filter_by(
    result="Neutral",
    user_id=current_user.id
).count()

plt.figure(figsize=(5,5))
values = [positive, negative, neutral]

if sum(values) == 0:
    values = [1, 1, 1]

plt.pie(
    values,
    labels=["Positive", "Negative", "Neutral"],
    autopct="%1.1f%%"
)

from sqlalchemy import extract

@app.route("/charts")
@login_required
def charts():

    monthly_data = db.session.query(
        extract('month', Sentiment.created_at),
        db.func.count(Sentiment.id)
    ).group_by(
        extract('month', Sentiment.created_at)
    ).all()

    return render_template(
        "charts.html",
        monthly_data=monthly_data
    )
import pandas as pd
file = request.files.get("csv_file")

if file and file.filename != "":
    # CSV Upload code
    df = pd.read_csv(file)
text= request.form.get("text")
for row in df["text"]:
        # Analyze sentiment
        pass
@app.route("/download_report")
@login_required
def download_report():
    # Generate PDF report here
    pass

    pass
is_admin = db.Column(
    db.Boolean,
    default=False
)
@app.route("/admin")
@login_required
def admin():

    if not current_user.is_admin:
        return "Access Denied"

    users = User.query.all()
    posts = Sentiment.query.all()

    return render_template(
        "admin.html",
        users=users,
        posts=posts
    )
total_users = User.query.count()
total_posts = Sentiment.query.count()
positive = Sentiment.query.filter_by(
    result="Positive"
).count()
negative = Sentiment.query.filter_by(
    result="Negative"
).count()
neutral = Sentiment.query.filter_by(
    result="Neutral"
).count()
existing = Sentiment.query.filter_by(
    text=str(text),
    user_id=current_user.id
).first()

if not existing:
    record = Sentiment(text=str(text), user_id=current_user.id)
    db.session.add(record)
    db.session.commit()

from datetime import datetime

created_at = db.Column(
    db.DateTime,
    default=datetime.utcnow
)  