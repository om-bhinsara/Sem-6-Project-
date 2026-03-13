import matplotlib
matplotlib.use("Agg")  
import matplotlib.pyplot as plt
from werkzeug.utils import secure_filename
from flask import send_file
from flask_wtf.csrf import CSRFProtect
from datetime import datetime, timedelta 
import os
import uuid
from flask import session, request, jsonify, url_for, current_app
from matplotlib.figure import Figure
from matplotlib.backends.backend_agg import FigureCanvasAgg as FigureCanvas
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import cm
from reportlab.platypus import Table, TableStyle, Paragraph
from reportlab.lib.styles import getSampleStyleSheet
import secrets
from flask import Flask, request, jsonify, current_app
from flask_login import login_required, current_user
from dotenv import load_dotenv
from flask_login import login_required, current_user, LoginManager, UserMixin, login_user, logout_user
from flask_login import UserMixin
from flask_login import login_user
from flask_login import login_required, current_user
import os
from werkzeug.utils import secure_filename
from flask import request, jsonify
from email_validator import validate_email, EmailNotValidError

load_dotenv()  
from reportlab.platypus import Paragraph
from reportlab.lib.styles import getSampleStyleSheet

from functools import wraps

# =========================
# FLASK CORE
# =========================
from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    flash,
    session,
    jsonify
)

# =========================
# DATABASE
# =========================
from flask_sqlalchemy import SQLAlchemy

# =========================
# SECURITY
# =========================
from werkzeug.security import generate_password_hash, check_password_hash


# =========================
# PDF (ReportLab)
# =========================
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.platypus import Table, TableStyle

# =========================
# UTILITIES
# =========================
import uuid
import requests
from datetime import datetime
import pytz


# =========================
# FILE UPLOAD HELPERS
# =========================
ALLOWED_EXTENSIONS = {"pdf", "png", "jpg", "jpeg"}

def allowed_file(filename):
    return (
        "." in filename and
        filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS
    )


from flask import request, redirect, url_for, flash, session

from flask_mail import Mail, Message
from itsdangerous import URLSafeTimedSerializer
from email_validator import validate_email, EmailNotValidError

RESERVED_USERNAMES = {
    "admin",
    "support",
    "root",
    "system",
    "cardiosense",
    "moderator",
    "help",
    "contact"
}

app = Flask(__name__)

app.config["SECRET_KEY"] = os.getenv("SECRET_KEY")

# (temporary safety fallback for local dev)
if not app.config["SECRET_KEY"]:
    raise RuntimeError("SECRET_KEY is missing. Set it in .env")

csrf = CSRFProtect(app)

app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = 'hridyacare.webapp@gmail.com'  
app.config['MAIL_PASSWORD'] = os.getenv("MAIL_PASSWORD")
app.config['MAIL_DEFAULT_SENDER'] = 'hridyacare.webapp@gmail.com'

mail = Mail(app)
s = URLSafeTimedSerializer(app.secret_key)

# =========================
# EMAIL VERIFICATION HELPER
# =========================
def send_verification_email(user_email):
    token = s.dumps(user_email, salt="email-confirm")

    verify_url = url_for(
        "confirm_email",
        token=token,
        _external=True
    )

    msg = Message(
        subject="Verify your HridyaCare account",
        recipients=[user_email]
    )

    msg.body = f"""
Hi,

Welcome to HridyaCare 💙

Please verify your email by clicking the link below:

{verify_url}

This link expires in 1 hour.

If you did not create this account, ignore this email.

— Team HridyaCare
"""

    try:
        mail.send(msg)
        print("EMAIL SENT TO:", user_email)
        return True
    except Exception as e:
        print("EMAIL ERROR:", e)
        return False


# =========================
# CSRF ERROR HANDLER
# =========================
from flask_wtf.csrf import CSRFError

@app.errorhandler(CSRFError)
def handle_csrf_error(e):
    flash("Session expired. Please try again.", "warning")
    return redirect(url_for("login"))


UPLOAD_FOLDER = "uploads/certificates"
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# ---------------- CONFIG ----------------

app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv("DATABASE_URL")

db = SQLAlchemy(app)
login_manager = LoginManager()
login_manager.init_app(app)        # <--- THIS IS THE MISSING LINE CAUSING THE ERROR
login_manager.login_view = 'login'

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))

class HeartRateRecord(db.Model):
    __tablename__ = 'heart_rate_records'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    
    member_id = db.Column(db.Integer, db.ForeignKey('family_members.member_id')) 
    
    bpm = db.Column(db.Integer, nullable=False)
    aqi = db.Column(db.Integer)
    pm25 = db.Column(db.Float, nullable=True)
    pm10 = db.Column(db.Float, nullable=True)
    stress_level = db.Column(db.String(50))
    impact_category = db.Column(db.String(50))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


AQICN_API_TOKEN = os.getenv("AQICN_API_TOKEN")

@csrf.exempt
@app.route("/api/stress/save", methods=["POST"])
def save_stress():
    if "user_id" not in session:
        return jsonify({"error": "Unauthorized"}), 401

    data = request.json
    print("STRESS DATA:", data)

    user_id = session["user_id"]
    member_id = data.get("member_id")
    if member_id:
        member_id = int(member_id)

    user = User.query.get(user_id)

    if not member_id:
        return jsonify({"error": "member_id required"}), 400

    
    stress = StressAssessment.query.filter_by(
        user_id=user_id,
        member_id=member_id
    ).first()
    

    # If not exist → create
    if not stress:
        stress = StressAssessment(
            user_id=user_id,
            member_id=member_id
        )

    # Update values
    stress.total_score = data.get("total")
    stress.stress_level = data.get("level")
    stress.emotional = data.get("emotional")
    stress.control = data.get("control")
    stress.resilience = data.get("resilience")
    stress.cognitive = data.get("cognitive")
    stress.anger = data.get("anger")
    stress.insight_present = data.get("insight_present")
    stress.insight_past = data.get("insight_past")
    stress.updated_at = datetime.utcnow()

    db.session.add(stress)
    db.session.commit()

    return jsonify({"status": "updated"})

app.config['UPLOAD_FOLDER'] = os.path.join(app.root_path, 'static/uploads')
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/upload-avatar', methods=['POST'])
@login_required
def upload_avatar():
    # 1. Check if file is present
    if 'avatar' not in request.files:
        return jsonify({'success': False, 'message': 'No file sent'})
    
    file = request.files['avatar']
    
    if file.filename == '':
        return jsonify({'success': False, 'message': 'No file selected'})

    if file and allowed_file(file.filename):
        try:
            # 2. Create a random secure name (prevents files overwriting each other)
            # e.g., 'a1b2c3d4.jpg'
            random_hex = secrets.token_hex(8)
            _, f_ext = os.path.splitext(file.filename)
            new_filename = random_hex + f_ext
            
            # 3. Save the actual image file to your folder
            # Result path: /your-project/static/uploads/a1b2c3d4.jpg
            save_path = os.path.join(app.config['UPLOAD_FOLDER'], new_filename)
            file.save(save_path)
            
            # 4. Update the DATABASE with the new filename
            # This is the crucial step that makes it load every time
            current_user.profile_pic = new_filename
            db.session.commit()
            
            return jsonify({'success': True, 'filename': new_filename})
            
        except Exception as e:
            print(f"Upload Error: {e}")
            return jsonify({'success': False, 'message': 'Could not save file'})
            
    return jsonify({'success': False, 'message': 'Invalid file type'})

QUIZ_QUESTIONS = [
    {
        "id": 1,
        "question": "Nut consumption helps improve blood lipid levels.",
        "correct": True,
        "category": "Diet"
    },
    {
        "id": 2,
        "question": "A resting heart rate above 100 BPM is always normal.",
        "correct": False,
        "category": "Heart"
    },
    {
        "id": 3,
        "question": "Chronic stress can increase heart disease risk.",
        "correct": True,
        "category": "Stress"
    },
    {
        "id": 4,
        "question": "Poor sleep has no effect on heart rate variability.",
        "correct": False,
        "category": "Sleep"
    }
]

# Make sure UserMixin is imported at the top: 
# from flask_login import UserMixin

class User(UserMixin, db.Model): 
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), unique=True, nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)

    gender = db.Column(db.String(10))
    age = db.Column(db.Integer)
    blood_type = db.Column(db.String(5))
    height = db.Column(db.Float)
    weight = db.Column(db.Float)
    city = db.Column(db.String(100))
    
    role = db.Column(db.String(10), default="user")
    verification_status = db.Column(db.String(10), default="approved")
    certificate_path = db.Column(db.Text)
    is_verified = db.Column(db.Boolean, default=False)
    selected_member_id = db.Column(db.Integer, db.ForeignKey("family_members.member_id"))
    profile_pic = db.Column(db.String(150), nullable=False, default='default.jpg')
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
   
class TelehealthChat(db.Model):
    __tablename__ = "telehealth_chat"

    id = db.Column(db.Integer, primary_key=True)
    member_id = db.Column(db.Integer, db.ForeignKey("family_members.member_id"))
    coach_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    sender = db.Column(db.String(10))
    message = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)    
    
@app.route("/admin/migrate-user-medical")
def migrate_user_medical():
    users = User.query.all()

    for u in users:
        self_mem = FamilyMember.query.filter_by(user_id=u.id, relationship="self").first()
        if self_mem:
            self_mem.gender = getattr(u, "gender", None)
            self_mem.age = getattr(u, "age", None)
            self_mem.blood_type = getattr(u, "blood_type", None)
            self_mem.height = getattr(u, "height", None)
            self_mem.weight = getattr(u, "weight", None)
            self_mem.city = getattr(u, "city", None)

    db.session.commit()
    return "Migration Done"


from sqlalchemy import text
class FamilyMember(db.Model):
    __tablename__ = "family_members"
    __table_args__ = (
        db.Index(
            "ix_one_self_per_user",
            "user_id",
            unique=True,
            postgresql_where=text("relationship = 'self'")
        ),
    )


    # Existing fields
    member_id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    member_name = db.Column(db.String(100), nullable=False)
    relationship = db.Column(db.String(50), nullable=False)
    age = db.Column(db.Integer)
    gender = db.Column(db.String(10))
    city = db.Column(db.String(100))

    # --- ADD THESE NEW COLUMNS ---
    blood_type = db.Column(db.String(5))
    height = db.Column(db.Float)
    weight = db.Column(db.Float)
    # -----------------------------
    
class StressAssessment(db.Model):
    __tablename__ = "stress_assessment"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    member_id = db.Column(db.Integer, db.ForeignKey("family_members.member_id"), nullable=False)

    total_score = db.Column(db.Integer)
    stress_level = db.Column(db.String(50))
    emotional = db.Column(db.Integer)
    control = db.Column(db.Integer)
    resilience = db.Column(db.Integer)
    cognitive = db.Column(db.Integer)
    anger = db.Column(db.Integer)
    insight_present = db.Column(db.Text)
    insight_past = db.Column(db.Text)

    updated_at = db.Column(db.DateTime, default=datetime.utcnow)


class CoachNote(db.Model):
    __tablename__ = "coach_notes"

    id = db.Column(db.Integer, primary_key=True)
    coach_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    note = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    seen = db.Column(db.Boolean, default=False)
    
class ConsultationRequest(db.Model):
    __tablename__ = "consultation_requests"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer)
    coach_id = db.Column(db.Integer)
    reason = db.Column(db.Text)
    details = db.Column(db.Text)
    status = db.Column(db.String(20))
    created_at = db.Column(db.DateTime)

class Feedback(db.Model):
    __tablename__ = "feedback"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    name = db.Column(db.String(100))
    email = db.Column(db.String(150))
    feedback_type = db.Column(db.String(50))
    rating = db.Column(db.Integer)
    message = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    
with app.app_context():
    db.create_all()

@csrf.exempt
@app.route("/api/telehealth/send-message", methods=["POST"])
def send_message():
    if "user_id" not in session:
        return jsonify({"error": "Unauthorized"}), 401

    data = request.json
    member_id = data.get("member_id")
    coach_id = data.get("coach_id")
    message = data.get("message")

    if not member_id or not coach_id or not message:
        return jsonify({"error": "Invalid data"}), 400

    chat = TelehealthChat(
        member_id=member_id,
        coach_id=coach_id,
        sender="user",
        message=message
    )

    db.session.add(chat)
    db.session.commit()

    return jsonify({"success": True})

@app.route("/api/telehealth/chat-history")
def chat_history():

    if "user_id" not in session:
        return jsonify([]), 401

    member_id = request.args.get("member_id", type=int)
    coach_id = request.args.get("coach_id", type=int)

    chats = (
        TelehealthChat.query
        .filter_by(member_id=member_id, coach_id=coach_id)
        .order_by(TelehealthChat.created_at.asc())
        .all()
    )

    result = []

    for c in chats:
        result.append({
            "sender": c.sender,
            "message": c.message,
            "timestamp": c.created_at.isoformat()
        })

    return jsonify(result)

@csrf.exempt
@app.route("/api/coach/send-message", methods=["POST"])
def coach_send_message():

    if "user_id" not in session:
        return jsonify({"error": "Unauthorized"}), 401

    coach = User.query.get(session["user_id"])
    if coach.role != "coach":
        return jsonify({"error": "Forbidden"}), 403

    data = request.json

    chat = TelehealthChat(
        member_id=data["member_id"],
        coach_id=coach.id,
        sender="coach",
        message=data["message"]
    )

    db.session.add(chat)
    db.session.commit()

    return jsonify({"success": True})

# --- GET Details for Selected Member (API) ---
@app.route('/api/member/<int:id_val>')
@login_required
def get_member_details(id_val):
    
    # Get member from family_members table
    member = FamilyMember.query.filter_by(
        member_id=id_val,
        user_id=current_user.id
    ).first()

    if not member:
        return jsonify({"error": "Member not found"}), 404

    return jsonify({
        "id": member.member_id,
        "name": member.member_name,
        "gender": member.gender,
        "age": member.age,
        "blood_type": member.blood_type,
        "height": member.height,
        "weight": member.weight,
        "city": member.city,
        "relationship": member.relationship
    })
    
    
@app.route('/update-medical-id', methods=['POST'])
@login_required  # Keep this! It provides the 'current_user' data.
def update_medical_id():
    # 1. Get the member ID
    target_id = request.form.get('member_id', type=int)
    
    # 2. Determine who to update
    target = None
    if not target_id:
        target = FamilyMember.query.filter_by(user_id=current_user.id, relationship='self').first()
        # Fallback if self profile doesn't exist yet
        if not target:
            target = FamilyMember(user_id=current_user.id, member_name=current_user.username, relationship='self')
            db.session.add(target)
    else:
        target = db.session.get(FamilyMember, target_id)
        # Security check: does this belong to you?
        if not target or target.user_id != current_user.id:
            flash("Invalid access.", "danger")
            return redirect(url_for('profile'))

    # 3. Update Data
    target.gender = request.form.get('gender')
    target.blood_type = request.form.get('blood_type')
    target.city = request.form.get('city')

    # Handle numbers safely
    try:
        def clean(val, is_float=False):
            if not val or not val.strip(): return None
            return float(val) if is_float else int(val)

        target.age = clean(request.form.get('age'))
        target.height = clean(request.form.get('height'), True)
        target.weight = clean(request.form.get('weight'), True)

        db.session.commit()
        flash(f"Updated profile for {target.member_name}", "success")
        
    except Exception as e:
        db.session.rollback()
        print("DB Error:", e)
        flash("Error saving data.", "danger")

    return redirect(url_for('profile'))


@app.route('/feedback', methods=['GET', 'POST'])
def feedback():

    if 'user_id' not in session:
        flash("Please login to submit feedback.", "warning")
        return redirect(url_for('login'))

    # ✅ Get user using SQLAlchemy
    user = User.query.get(session["user_id"])

    if not user:
        flash("User not found.", "danger")
        return redirect(url_for('login'))

    # ✅ Save feedback
    if request.method == 'POST':
        fb = Feedback(
            user_id=session['user_id'],
            name=user.username,
            email=user.email,
            feedback_type=request.form.get("type"),
            rating=request.form.get("rating"),
            message=request.form.get("message")
        )
        db.session.add(fb)
        db.session.commit()

        flash("Thank you! Feedback submitted successfully.", "success")
        return redirect(url_for("feedback"))

    return render_template(
        'pages/feedback.html',
        user_name=user.username,
        user_email=user.email
    )
    
    
@app.route("/api/last-health-summary")
def last_health_summary():

    user_id = request.args.get("user_id", type=int)

    if not user_id:
        return jsonify({"error": "user_id required"}), 400

    record = (
        HeartRateRecord.query
        .filter_by(user_id=user_id)
        .order_by(HeartRateRecord.created_at.desc())
        .first()
    )

    if not record:
        return jsonify({"exists": False})

    return jsonify({
        "exists": True,
        "bpm": record.bpm,
        "aqi": record.aqi,
        "impactCategory": record.impact_category
    })

    
@app.route("/api/last-health-summary-member")
def last_health_summary_member():

    member_id = request.args.get("member_id", type=int)

    if not member_id:
        return jsonify({"exists": False})

    record = (
        HeartRateRecord.query
        .filter_by(member_id=member_id)
        .order_by(HeartRateRecord.created_at.desc())
        .first()
    )

    if not record:
        return jsonify({"exists": False})

    member = FamilyMember.query.get(member_id)

    return jsonify({
        "exists": True,
        "bpm": record.bpm,
        "aqi": record.aqi,
        "impactCategory": record.impact_category,
        "member_name": member.member_name if member else "Unknown",
        "relationship": member.relationship if member else "Unknown",
        "timestamp": record.created_at.isoformat()
    })
    
    

@app.route("/api/coaches")
def get_coaches():
    if "user_id" not in session:
        return jsonify([]), 401

    coaches = User.query.filter_by(role="coach", verification_status="approved").all()

    return jsonify([
        {"id": c.id, "username": c.username}
        for c in coaches
    ])



@csrf.exempt
@app.route("/api/telehealth/request", methods=["POST"])
def submit_consultation():
    if "user_id" not in session:
        return jsonify({"error": "Unauthorized"}), 401

    data = request.json

    if not data or not data.get("coach_id") or not data.get("reason"):
        return jsonify({"error": "Invalid data"}), 400

    req = ConsultationRequest(
        user_id=session["user_id"],
        coach_id=data["coach_id"],
        reason=data["reason"],
        details=data.get("details", "")
    )

    db.session.add(req)
    db.session.commit()

    return jsonify({"success": True})

from sqlalchemy import text

@app.route("/api/coach/requests")
def coach_requests():

    coach_id = session["user_id"]

    rows = db.session.execute(text("""
        SELECT 
            id,
            user_id,
            reason,
            details
        FROM consultation_requests
        WHERE coach_id = :coach_id
        ORDER BY created_at DESC
    """), {"coach_id": coach_id}).fetchall()

    result = []

    for r in rows:
        result.append({
            "user_id": r.user_id,
            "member_id": r.user_id,
            "reason": r.reason
        })

    return jsonify(result)

@app.route("/api/telehealth/user-snapshot/<int:user_id>")
def telehealth_user_snapshot(user_id):
    if "user_id" not in session:
        return jsonify({"error": "Unauthorized"}), 401

    coach = User.query.get(session["user_id"])
    if not coach or coach.role != "coach":
        return jsonify({"error": "Forbidden"}), 403

    user = User.query.get(user_id)


    hr_rows = HeartRateRecord.query.filter_by(user_id=user_id).limit(50).all()


    user = User.query.get(user_id)
    
    stress = StressAssessment.query.filter_by(
        user_id=user_id,
        member_id=request.args.get("member_id", type=int)
    ).first()
    
    bpm_values = [r.bpm for r in hr_rows]

    return jsonify({
        "username": user.username if user else "Unknown",
        "heart_rate": {
            "avg": round(sum(bpm_values)/len(bpm_values)) if bpm_values else None,
            "max": max(bpm_values) if bpm_values else None,
            "min": min(bpm_values) if bpm_values else None,
            "history": [
                {
                    "bpm": r.bpm,
                    "time": r.created_at.strftime("%d %b %Y %I:%M %p")
                } for r in hr_rows[::-1]
            ]
        },
        "stress": {
            "total_score": stress.total_score if stress else None,
            "stress_level": stress.stress_level if stress else None
        }
    })

@app.route('/all-topics')
def all_topics():
    return render_template('articles/all-topics.html') 

@app.route('/all-articles')
def all_articles():
    return render_template('articles/all-articles.html')   

@app.route('/how_to_use_heart_rate.html')
def help_page():
    return render_template('articles/how_to_use_heart_rate.html')

@app.route('/diet-low-salt.html')
def diet_low_salt():
    return render_template('articles/diet-low-salt.html')

@app.route('/diet-high-protein.html')
def diet_high_protein():
    return render_template('articles/diet-high-protein.html')

@app.route('/diet-omega-3.html')
def diet_omega_3():
    return render_template('articles/diet-omega-3.html')

@app.route('/article/resting-heart-rate')
def article_resting_hr():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    return render_template('articles/article_resting_hr.html')

@app.route('/article/heart-healthy-diet')
def article_diet():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    return render_template('articles/article_diet.html')

@app.route('/article/heart-disease')
def article_heart_disease():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    return render_template('articles/article_heart_disease.html')

@app.route('/article/stress-connection')
def stress_article_page():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    return render_template('articles/article_stress.html')

@app.route('/heart-health')
def heart_health_hub():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    return render_template('articles/heart.html')

@app.route("/api/telehealth/coach-response")
def telehealth_coach_response():
    if "user_id" not in session:
        return jsonify({"note": None}), 401

    note = (
        CoachNote.query
        .filter_by(user_id=session["user_id"])
        .order_by(CoachNote.created_at.desc())
        .first()
    )

    if not note:
        return jsonify({"note": None})

    coach = User.query.get(note.coach_id)

    return jsonify({
        "note": note.note,
        "coach_name": coach.username if coach else "",
        "coach_email": coach.email if coach else "",
        "timestamp": note.created_at.isoformat()
    })



@app.route('/report')
def report():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    print("REPORT USER:", session.get("username"))  

    return render_template(
        'features/report.html',
        username=session.get("username")
    )
    
@app.route('/report_download_later')
def report_download_later():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    print("REPORT USER:", session.get("username"))  

    return render_template(
        'features/report_download_later.html',
        username=session.get("username")
    )
    
import os
import secrets
from PIL import Image # Optional: pip install Pillow (for resizing)
from flask import current_app

# 1. Helper function to save the picture
def save_picture(form_picture):
    # Generate a random hex to prevent filename collisions
    random_hex = secrets.token_hex(8)
    _, f_ext = os.path.splitext(form_picture.filename)
    picture_fn = random_hex + f_ext
    
    # Create the full path: static/uploads/picture_fn
    picture_path = os.path.join(current_app.root_path, 'static/uploads', picture_fn)

    # (Optional) Resize image to save space - 125x125 pixels
    output_size = (125, 125)
    i = Image.open(form_picture)
    i.thumbnail(output_size)
    i.save(picture_path)

    return picture_fn


@app.route("/api/telehealth/coach-timeline")
def telehealth_coach_timeline():
    if "user_id" not in session:
        return jsonify([]), 401

    notes = (
        CoachNote.query
        .filter_by(user_id=session["user_id"])
        .order_by(CoachNote.created_at.desc())
        .all()
    )

    timeline = []
    for n in notes:
        coach = User.query.get(n.coach_id)
        timeline.append({
            "id": n.id,
            "note": n.note,
            "coach_name": coach.username if coach else "",
            "coach_email": coach.email if coach else "",
            "timestamp": n.created_at.isoformat(),
            "seen": n.seen
        })

    return jsonify(timeline)


@csrf.exempt
@app.route("/api/telehealth/mark-seen", methods=["POST"])
def mark_coach_note_seen():
    if "user_id" not in session:
        return jsonify({"error": "Unauthorized"}), 401

    note_id = request.json.get("note_id")
    if not note_id:
        return jsonify({"error": "Invalid data"}), 400

    note = CoachNote.query.filter_by(id=note_id, user_id=session["user_id"]).first()
    if note:
        note.seen = True
        db.session.commit()

    return jsonify({"status": "seen"})

@app.route('/heart-rate')
def heart_rate():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    return render_template('features/heart_rate.html')


@app.route('/physical-health')
def physical_health():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    return render_template('features/physical_health.html')

# PHYSICAL HEALTH METRICS
def calculate_bmi(weight, height_cm):
    height_m = height_cm / 100
    return round(weight / (height_m ** 2), 2)


def calculate_wasi(age, weight, height_cm):
    bmi = calculate_bmi(weight, height_cm)

    if bmi < 18.5:
        bmi_score = 50
    elif bmi <= 24.9:
        bmi_score = 100
    elif bmi <= 29.9:
        bmi_score = 70
    else:
        bmi_score = 40

    age_factor = max(0.7, 1 - (age - 20) * 0.005)
    wasi = round(bmi_score * age_factor, 1)

    return wasi


def calculate_mls(age, weight, height_cm):
    height_m = height_cm / 100
    ideal_weight = 22 * (height_m ** 2)

    load_ratio = weight / ideal_weight

    if age < 30:
        age_multiplier = 1.0
    elif age < 45:
        age_multiplier = 1.1
    else:
        age_multiplier = 1.2

    mls = round(load_ratio * age_multiplier * 100, 1)
    return mls

@app.route("/api/stress/latest")
def get_latest_stress():
    if "user_id" not in session:
        return jsonify({}), 401

    member_id = request.args.get("member_id", type=int)

    # ✅ STRICT MODE: member_id MUST be provided
    if not member_id:
        return jsonify({"error": "member_id required"}), 400

    query = StressAssessment.query.filter_by(
        user_id=session["user_id"],
        member_id=member_id
    )

    stress = query.order_by(StressAssessment.updated_at.desc()).first()

    if not stress:
        return jsonify({})

    return jsonify({
        "total_score": stress.total_score,
        "stress_level": stress.stress_level,
        "emotional": stress.emotional,
        "control": stress.control,
        "resilience": stress.resilience,
        "cognitive": stress.cognitive,
        "anger": stress.anger,
        "insight_past": stress.insight_past,
        "measured_at": stress.updated_at.isoformat()
    })



@app.route("/stress-check")
def stress_check():
    if "user_id" not in session:
        return redirect(url_for("login"))
    return render_template("features/stress_check.html")

@app.route("/add-plan")
def add_plan():
    return render_template("add_plan.html")

@csrf.exempt
@app.route("/api/quiz", methods=["POST"])
def quiz():
    data = request.json
    correct = data["answer"] is True
    return jsonify({"correct": correct})

@app.route('/lifestyle')
def lifestyle():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    return render_template('features/lifestyle.html')



@app.route('/telehealth')
def telehealth():
    if "user_id" not in session:
        return redirect(url_for("login"))
    return render_template('features/telehealth.html')


@app.route("/coach/dashboard")
def coach_dashboard():
    if "user_id" not in session:
        return redirect(url_for("login"))

    # ✅ Fetch coach using SQLAlchemy
    coach = User.query.get(session["user_id"])

    if not coach or coach.role != "coach":
        return redirect(url_for("index"))

    if coach.verification_status != "approved":
        return redirect(url_for("coach_pending"))

    # ✅ Fetch all patients
    patients = User.query.filter_by(role="user").order_by(User.id.desc()).all()

    selected_patient = patients[0] if patients else None

    metrics = None
    notes = []

    # ✅ Fetch metrics (if HealthMetrics model exists)
    if selected_patient:
        # Uncomment if HealthMetrics model exists
        # metrics = HealthMetrics.query.filter_by(user_id=selected_patient.id).order_by(HealthMetrics.created_at.desc()).first()

        # ✅ Fetch coach notes
        notes = CoachNote.query.filter_by(user_id=selected_patient.id).order_by(CoachNote.created_at.desc()).all()

    return render_template(
        "dashboard/coach_dashboard.html",
        coach=coach,
        patients=patients,
        selected_patient=selected_patient,
        metrics=metrics,
        notes=notes
    )


@app.route("/api/coach/patient/<int:user_id>/last-7")
def coach_last_7_hr(user_id):
    if "user_id" not in session:
        return jsonify([]), 401

    coach = User.query.get(session["user_id"])
    if not coach or coach.role != "coach":
        return jsonify([]), 403

    records = (
        HeartRateRecord.query
        .filter_by(user_id=user_id)
        .order_by(HeartRateRecord.created_at.desc())
        .limit(7)
        .all()
    )

    return jsonify([
        {"bpm": r.bpm, "time": r.created_at.isoformat()}
        for r in records
    ])



@app.route("/coach/pending")
def coach_pending():
    if "user_id" not in session:
        return redirect(url_for("login"))
    return render_template("dashboard/coach_pending.html")


@app.route('/eye_health')
def eye_health():
    if "user_id" not in session:
        return redirect(url_for("login"))
    return render_template('features/eye_health.html')


@app.route('/privacy-policy')
def privacy_policy():
    return render_template('pages/privacy_policy.html')

@app.route('/terms')
def terms():
    return render_template('pages/terms.html')




@app.route('/health')
def health():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    return render_template('pages/health.html')


@app.route('/profile')
def profile():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    user = db.session.get(User, session['user_id'])
    db.session.refresh(user)  

    # --- NEW: Fetch Family Members ---
    # This gets all members where the user_id matches the logged-in user
    from sqlalchemy import case

    family_members = (
        FamilyMember.query
        .filter_by(user_id=user.id)
        .order_by(
            case(
                (FamilyMember.relationship == "self", 0),
                else_=1
            ),
            FamilyMember.member_name.asc()
        )
        .all()
    )


    # --- Pass 'family_members' to the template ---
    return render_template('dashboard/profile.html', user=user, family_members=family_members)


@app.route('/tracker')
def tracker():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    return render_template('features/tracker.html')

@csrf.exempt
@app.route('/save-heart-rate', methods=['POST'])
def save_heart_rate():
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401

    data = request.get_json(force=True) or {}

    def safe_int(x, default=0):
        try: return int(float(x))
        except: return default

    def safe_float(x, default=0.0):
        try: return float(x)
        except: return default

    # ===== MEMBER ID STRICT =====
    raw_member_id = data.get("member_id")
    if not raw_member_id:
        return jsonify({"error": "member_id required"}), 400

    try:
        member_id = int(raw_member_id)
    except:
        return jsonify({"error": "Invalid member_id"}), 400

    member = FamilyMember.query.filter_by(
        member_id=member_id,
        user_id=session["user_id"]
    ).first()
    if not member:
        return jsonify({"error": "Invalid member"}), 400

    incoming_bpm = safe_int(data.get("bpm"))

    # ===== DELETE OLDEST IF > 7 =====
    count = HeartRateRecord.query.filter_by(
        user_id=session["user_id"],
        member_id=member_id
    ).count()

    if count >= 7:
        oldest = HeartRateRecord.query.filter_by(
            user_id=session["user_id"],
            member_id=member_id
        ).order_by(HeartRateRecord.created_at.asc(), HeartRateRecord.id.asc()).first()
        db.session.delete(oldest)
        db.session.commit()

    # ===== SAVE NEW RECORD ONLY =====
    record = HeartRateRecord(
        user_id=session["user_id"],
        member_id=member_id,
        bpm=incoming_bpm,
        aqi=safe_int(data.get("aqi")),
        pm25=safe_float(data.get("pm25")),
        pm10=safe_float(data.get("pm10")),
        stress_level=data.get("stress"),
        impact_category=data.get("impact")
    )

    db.session.add(record)
    db.session.commit()

    print("SAVED:", 
          "user_id:", session["user_id"], 
          "member_id:", member_id, 
          "bpm:", incoming_bpm)

    return jsonify({"success": True})


def calculate_us_aqi(pm25):
    """Calculates US EPA AQI from PM2.5 concentration"""
    if pm25 is None: return None
    try:
        c = float(pm25)
        if c < 0: return 0
        if c <= 12.0: return round(((50 - 0) / (12.0 - 0)) * (c - 0) + 0)
        if c <= 35.4: return round(((100 - 51) / (35.4 - 12.1)) * (c - 12.1) + 51)
        if c <= 55.4: return round(((150 - 101) / (55.4 - 35.5)) * (c - 35.5) + 101)
        if c <= 150.4: return round(((200 - 151) / (150.4 - 55.5)) * (c - 55.5) + 151)
        if c <= 250.4: return round(((300 - 201) / (250.4 - 150.5)) * (c - 150.5) + 201)
        if c <= 350.4: return round(((400 - 301) / (350.4 - 250.5)) * (c - 250.5) + 301)
        if c <= 500.4: return round(((500 - 401) / (500.4 - 350.5)) * (c - 350.5) + 401)
        return 500
    except (ValueError, TypeError):
        return None

# ---------------- AQI BACKEND API (SECURE & FIXED) ----------------
@csrf.exempt
@app.route("/api/aqi")
def get_aqi():
    city = request.args.get("city")
    if not city:
        return jsonify({"error": "City required"}), 400

    if not AQICN_API_TOKEN:
        return jsonify({"error": "AQICN token missing"}), 500

    # 1️⃣ GEOCODE CITY
    try:
        geo_resp = requests.get(
            "https://nominatim.openstreetmap.org/search",
            params={"q": city, "format": "json", "limit": 1},
            headers={"User-Agent": "HridyaCare/1.0"},
            timeout=10
        ).json()
    except Exception:
        return jsonify({"error": "Geocoding failed"}), 502

    if not geo_resp:
        return jsonify({"error": "City not found"}), 404

    lat = geo_resp[0]["lat"]
    lon = geo_resp[0]["lon"]

    # 2️⃣ AQICN GEO FEED
    url = f"https://api.waqi.info/feed/geo:{lat};{lon}/"
    params = {"token": AQICN_API_TOKEN}

    try:
        resp = requests.get(url, params=params, timeout=10).json()
    except Exception:
        return jsonify({"error": "AQI API unreachable"}), 502

    if resp.get("status") != "ok":
        return jsonify({"error": "AQICN error", "details": resp}), 502

    data = resp["data"]

    # ----------------------------------------------
    # 🚨 THE FIX: FORCE CALCULATION
    # ----------------------------------------------
    raw_aqi = data["aqi"]
    pm25_val = data.get("iaqi", {}).get("pm25", {}).get("v")
    pm10_val = data.get("iaqi", {}).get("pm10", {}).get("v")

    # If we have PM2.5, calculate the REAL score manually.
    # This fixes the issue where API sends "7" (concentration) instead of "29" (Score)
    calculated_aqi = calculate_us_aqi(pm25_val)

    # Use the calculated value if available, otherwise fallback to API value
    final_aqi = calculated_aqi if calculated_aqi is not None else raw_aqi

    # Debug print to your console
    print(f"City: {city} | API Says: {raw_aqi} | PM2.5: {pm25_val} | Calculated: {final_aqi}")
    pm25_val = data.get("iaqi", {}).get("pm25", {}).get("v")
    pm10_val = data.get("iaqi", {}).get("pm10", {}).get("v")

    return jsonify({
        "city": city,
        "aqi": final_aqi,  # ✅ Now returns correct score (e.g., 29 instead of 7)
        "pm25": pm25_val,
        "pm10": pm10_val,
        "dominant": data.get("dominentpol"),
        "source": "AQICN / CPCB",
        "scale": "US EPA AQI"
    })



@app.route('/generate-pdf', methods=['POST'])
@csrf.exempt  # <--- THIS IS IMPORTANT FOR JAVASCRIPT FETCH REQUESTS
def generate_pdf():
    # 1. Auth Check
    if 'user_id' not in session:
        return jsonify({"error": "Unauthorized"}), 401

    data = request.json
    history = data.get("history", [])

    # Ensure directory exists
    save_dir = os.path.join("static", "reports")
    os.makedirs(save_dir, exist_ok=True)

    # Unique filenames
    unique_id = uuid.uuid4().hex
    pdf_name = f"HridyaCare_Report_{unique_id}.pdf"
    img_name = f"hr_graph_{unique_id}.png"
    
    pdf_path = os.path.join(save_dir, pdf_name)
    img_path = os.path.join(save_dir, img_name)

    try:
        # ==================================================
        # 📊 GENERATE GRAPH IMAGE (THREAD-SAFE METHOD)
        # ==================================================
        if history:
            bpm_values = [h.get("bpm", 0) for h in history]
            x_values = list(range(1, len(bpm_values) + 1))

            # Use Figure() instead of plt.figure() for thread safety
            fig = Figure(figsize=(6, 3))
            ax = fig.add_subplot(111)
            
            ax.plot(x_values, bpm_values, marker="o", linewidth=2, color="#f43f5e")
            ax.fill_between(x_values, bpm_values, color="#f43f5e", alpha=0.15)
            
            ax.set_title("Heart Rate Trend (Last 7 Readings)")
            ax.set_xlabel("Reading")
            ax.set_ylabel("BPM")
            ax.grid(True, alpha=0.3)
            
            # Save using FigureCanvas
            FigureCanvas(fig).print_png(img_path)

        # ==================================================
        # 📄 CREATE PDF
        # ==================================================
        c = canvas.Canvas(pdf_path, pagesize=A4)
        width, height = A4
        
        # Margins & Dimensions
        BOTTOM_MARGIN = 2 * cm
        LEFT_MARGIN = 2 * cm
        RIGHT_MARGIN = 2 * cm
        CONTENT_WIDTH = width - LEFT_MARGIN - RIGHT_MARGIN

        # --- Helper to check page space ---
        def check_page_break(current_y, needed_height):
            if current_y - needed_height < BOTTOM_MARGIN:
                c.showPage()
                return height - 50 # Reset Y to top
            return current_y

        # ---------- HEADER ----------
        c.setFillColorRGB(0.96, 0.26, 0.39) # HridyaCare Pink
        c.rect(0, height - 70, width, 70, fill=1)
        c.setFillColor(colors.white)
        c.setFont("Helvetica-Bold", 22)
        c.drawCentredString(width / 2, height - 45, "HridyaCare Health Report")

        y = height - 100
        c.setFillColor(colors.black)

        # ---------- USER INFO ----------
        c.setFont("Helvetica", 12)
        c.drawString(LEFT_MARGIN, y, f"Username: {data.get('name', 'User')}")
        c.drawRightString(width - RIGHT_MARGIN, y, f"Date: {data.get('timestamp')}")
        y -= 18

        c.drawString(LEFT_MARGIN, y, f"Age: {data.get('age')}")
        c.drawRightString(width - RIGHT_MARGIN, y, f"City: {data.get('city')}")
        y -= 30

        # ---------- HEART RATE CARD ----------
        c.setFillColorRGB(0.95, 0.96, 0.98)
        c.roundRect(LEFT_MARGIN, y - 80, CONTENT_WIDTH, 80, 12, fill=1)
        c.setFillColor(colors.black)

        c.setFont("Helvetica-Bold", 20)
        c.drawCentredString(width / 2, y - 35, f"{data.get('bpm')} BPM")

        c.setFont("Helvetica", 12)
        c.drawCentredString(width / 2, y - 60, f"Impact: {data.get('impactCategory')}")
        y -= 100 # Adjusted spacing

        # ---------- AQI DETAILS ----------
        c.setFillColorRGB(0.97, 0.97, 0.97)
        c.roundRect(LEFT_MARGIN, y - 70, CONTENT_WIDTH, 70, 10, fill=1)
        c.setFillColor(colors.black)

        c.setFont("Helvetica-Bold", 12)
        c.drawString(LEFT_MARGIN + 10, y - 28, f"AQI: {data.get('aqi', '--')} (US EPA)")

        c.setFont("Helvetica", 11)
        c.drawString(LEFT_MARGIN + 10, y - 48, f"PM2.5: {data.get('pm25', '--')} µg/m³")
        c.drawRightString(width - RIGHT_MARGIN - 10, y - 48, f"PM10: {data.get('pm10', '--')} µg/m³")

        y -= 90

        # ---------- GRAPH IMAGE ----------
        if history and os.path.exists(img_path):
            # Check space for graph (needs approx 180 height)
            y = check_page_break(y, 180)
            
            c.drawImage(
                img_path,
                LEFT_MARGIN,
                y - 180,
                width=CONTENT_WIDTH,
                height=160,
                preserveAspectRatio=True
            )
            y -= 240

        # ---------- HEART RATE TABLE ----------
        if history:
            # Check space for Title + minimal table
            y = check_page_break(y, 100)
            
            c.setFont("Helvetica-Bold", 14)
            c.drawString(LEFT_MARGIN, y, "Last 7 Heart Rate Readings")
            y -= 20

            hr_table_data = [["#", "BPM", "Time"]]
            # Limit history to prevent huge tables if needed, or paginate inside
            # For now, we take the last 7 strictly
            for i, h in enumerate(history[:7][::-1], 1):
                hr_table_data.append([str(i), str(h.get("bpm", "--")), h.get("time", "--")])

            hr_table = Table(hr_table_data, colWidths=[2 * cm, 3 * cm, CONTENT_WIDTH - 5 * cm])
            hr_table.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("FONT", (0, 0), (-1, 0), "Helvetica-Bold"),
            ]))

            _, table_height = hr_table.wrap(CONTENT_WIDTH, height)
            
            # Check if table fits, if not new page
            y = check_page_break(y, table_height)
            
            hr_table.drawOn(c, LEFT_MARGIN, y - table_height)
            y -= (table_height + 30)

        # ---------- AQI REFERENCE TABLE ----------
        # Check space for Title + AQI Table (approx 150-200 units)
        y = check_page_break(y, 200)

        c.setFont("Helvetica-Bold", 14)
        c.drawString(LEFT_MARGIN, y, "AQI Reference (US EPA Scale)")
        y -= 20

        styles = getSampleStyleSheet()
        cell_style = styles["BodyText"]
        cell_style.fontSize = 9
        cell_style.leading = 11

        aqi_table_data = [
            [Paragraph("<b>AQI Range</b>", cell_style),
             Paragraph("<b>Category</b>", cell_style),
             Paragraph("<b>Health Meaning</b>", cell_style)],
            ["0–50", "Good", "Air quality is satisfactory"],
            ["51–100", "Moderate", "Some pollutants may affect sensitive people"],
            ["101–150", "Sensitive Groups", "Lung/heart disease risks"],
            ["151–200", "Unhealthy", "Everyone may experience effects"],
            ["201–300", "Very Unhealthy", "Health alert: increased risk"],
            ["301+", "Hazardous", "Emergency conditions"],
        ]

        aqi_table = Table(aqi_table_data, colWidths=[2.5 * cm, 4 * cm, CONTENT_WIDTH - 6.5 * cm])
        aqi_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#fee2e2")),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
            ("ALIGN", (0, 0), (-1, -1), "LEFT"),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("PADDING", (0,0), (-1,-1), 6),
        ]))

        _, aqi_height = aqi_table.wrap(CONTENT_WIDTH, height)
        
        # We already checked for space above, but good double check
        y = check_page_break(y, aqi_height)
        
        aqi_table.drawOn(c, LEFT_MARGIN, y - aqi_height)
        y -= (aqi_height + 20)

        # ---------- FOOTER / DISCLAIMER ----------
        y = check_page_break(y, 30)
        c.setFont("Helvetica-Oblique", 10)
        c.setFillColor(colors.grey)
        c.drawString(LEFT_MARGIN, y, "This report provides wellness insights and is not a medical diagnosis.")

        c.showPage()
        c.save()

        return jsonify({
            "pdf_url": url_for("static", filename=f"reports/{pdf_name}")
        })

    except Exception as e:
        # Log the error properly in production
        print(f"Error generating PDF: {e}")
        return jsonify({"error": "Failed to generate PDF"}), 500

    finally:
        # 🧹 ALWAYS CLEAN UP THE IMAGE
        if os.path.exists(img_path):
            os.remove(img_path)

# FIND THIS FUNCTION AND REPLACE IT
def coach_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("login"))

        # ✅ FIXED: Use SQLAlchemy instead of get_db_connection
        user = User.query.get(session["user_id"])

        if not user or user.role != "coach":
            return redirect(url_for("index"))

        return f(*args, **kwargs)
    return wrapper

    
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":

        # ---------- BASIC FIELDS ----------
        username = request.form["username"].strip().lower()
        email = request.form["email"].strip().lower()
        password = (request.form.get("password") or "").strip()
        confirm_password = (request.form.get("confirm_password") or "").strip()
        role = request.form.get("role", "user")

        # ---------- 1. EMAIL VALIDATION (NEW) ----------
        try:
            # check_deliverability=True pings the domain to see if it accepts email
            valid = validate_email(email, check_deliverability=True)
            email = valid.normalized  # Updates email to the canonical form
        except EmailNotValidError as e:
            flash(f"Invalid email: {str(e)}")
            return redirect(url_for("register"))

        # ---------- 2. FORM VALIDATIONS ----------
        if username in RESERVED_USERNAMES:
            flash("This username is reserved.")
            return redirect(url_for("register"))

        if not password or password != confirm_password:
            flash("Password and Confirm Password must be identical.")
            return redirect(url_for("register"))

        # ---------- 3. DATABASE CHECKS ----------
        # conn = get_db_connection()
        # cur = conn.cursor()

        # Check if email exists
        if User.query.filter_by(email=email).first():
            flash("Email already registered.")
            return redirect(url_for("register"))


        # Check if username exists
        if User.query.filter_by(username=username).first():
            flash("Username already taken.")
            return redirect(url_for("register"))

        password_hash = generate_password_hash(password)

        # ---------- ROLE LOGIC ----------
        verification_status = "pending" if role == "coach" else "approved"
        certificate_path = None

        # ---------- COACH CERTIFICATE ----------
        if role == "coach":
            file = request.files.get("certificate")

            if not file or file.filename == "":
                flash("Certificate is required for Health Coach.")
                return redirect(url_for("register"))

            if not allowed_file(file.filename): 
                flash("Invalid certificate format.")
                return redirect(url_for("register"))

            filename = secure_filename(file.filename)
            certificate_path = f"{uuid.uuid4().hex}_{filename}"
            save_path = os.path.join(app.config["UPLOAD_FOLDER"], certificate_path)
            file.save(save_path)

        try:
            new_user = User(
                username=username,
                email=email,
                password_hash=password_hash,
                role=role,
                verification_status=verification_status,
                certificate_path=certificate_path,
                is_verified=False
            )

            db.session.add(new_user)
            db.session.commit()
            
            self_member = FamilyMember.query.filter_by(
                user_id=new_user.id,
                relationship="self"
            ).first()
            
            if not self_member:
                self_member = FamilyMember(
                    user_id=new_user.id,
                    member_name=username,
                    relationship="self"
                )
                db.session.add(self_member)
                db.session.commit()
            

            send_verification_email(email)

            flash("Account created! Please verify your email before logging in.", "info")
            return redirect(url_for("login"))

        except Exception as e:
            db.session.rollback()
            print("DB Error:", e)
            flash("An error occurred during registration.")
            return redirect(url_for("register"))
        
    return render_template("auth/register.html")

# FIND THIS ROUTE AND REPLACE IT
@app.route("/coach/entry")
def coach_entry():
    if "user_id" not in session:
        return redirect(url_for("login"))

    # ✅ FIXED: Use SQLAlchemy
    user = User.query.get(session["user_id"])

    if not user or user.role != "coach":
        return redirect(url_for("index"))

    if user.verification_status == "approved":
        return redirect(url_for("coach_dashboard"))

    return redirect(url_for("coach_pending"))
 
@app.route("/")
def index():
    if "user_id" not in session:
        return redirect(url_for("login"))

    user_id = session["user_id"]
    missing_med_info = False

    try:
        # 1. Fetch all profiles attached to this user (including their "self" profile)
        family_members = FamilyMember.query.filter_by(user_id=user_id).all()
        
        # 2. Check if ANY of them are missing vital medical details
        for member in family_members:
            if not member.age or not member.height or not member.weight or not member.blood_type:
                missing_med_info = True
                break  # Stop checking once we find at least one incomplete profile

    except Exception as e:
        print(f"Error checking medical info: {e}")

    # 3. Pass the flag to the dashboard template
    return render_template("pages/index.html", missing_med_info=missing_med_info)

@app.route("/admin/coaches")
def admin_coaches():
    if "user_id" not in session:
        return redirect(url_for("login"))

    admin = User.query.get(session["user_id"])
    if not admin or admin.role != "admin":
        return redirect(url_for("index"))

    coaches = User.query.filter_by(role="coach", verification_status="pending").all()

    return render_template("dashboard/admin_coaches.html", coaches=coaches)



@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"].strip().lower()
        password = request.form["password"]

        user = User.query.filter_by(email=email).first()

        if not user or not check_password_hash(user.password_hash, password):
            session.clear()
            flash("Invalid email or password")
            return redirect(url_for("login"))
        login_user(user)   # ✅ ADD THIS

        # 🚨 BLOCK LOGIN IF EMAIL NOT VERIFIED
        if not user.is_verified:
            flash("Please verify your email before logging in.", "warning")
            return redirect(url_for("login"))

        session["user_id"] = user.id
        session["username"] = user.username
        # Auto select SELF if no selected member
        if not user.selected_member_id:
            self_mem = FamilyMember.query.filter_by(user_id=user.id, relationship="self").first()
            if self_mem:
                user.selected_member_id = self_mem.member_id
                db.session.commit()

        print("LOGIN USER:", session["username"])  # DEBUG

        if user.role == "admin":
                return redirect(url_for("admin_coaches"))
        elif user.role == "coach":
            return redirect(url_for("coach_dashboard"))
        else:
            return redirect(url_for("index"))
    return render_template("auth/login.html")

@app.route("/admin/coach/approve/<int:coach_id>")
def approve_coach(coach_id):
    coach = User.query.get(coach_id)
    if coach:
        coach.verification_status = "approved"
        db.session.commit()
    flash("Coach approved successfully.", "success")
    return redirect(url_for("admin_coaches"))

@app.route("/admin/coach/reject/<int:coach_id>")
def reject_coach(coach_id):
    coach = User.query.get(coach_id)
    if coach:
        coach.verification_status = "rejected"
        db.session.commit()
    flash("Coach rejected.", "info")
    return redirect(url_for("admin_coaches"))

@app.route("/uploads/certificates/<path:filename>")
def view_certificate(filename):
    if "user_id" not in session:
        return redirect(url_for("login"))

    # ✅ FIXED: Use SQLAlchemy
    user = User.query.get(session["user_id"])

    if not user or user.role != "admin":
        return redirect(url_for("index"))

    filename = os.path.basename(filename)
    file_path = os.path.join(app.config["UPLOAD_FOLDER"], filename)

    if not os.path.exists(file_path):
        return "Certificate file not found", 404

    return send_file(file_path)

from sqlalchemy import text

@app.route("/api/coach/patient/<int:user_id>")
def coach_patient_chat(user_id):

    rows = db.session.execute(text("""
        SELECT sender, message, created_at
        FROM telehealth_chat
        WHERE member_id IN (
            SELECT member_id
            FROM family_members
            WHERE user_id = :user_id
        )
        ORDER BY created_at ASC
    """), {"user_id": user_id}).fetchall()

    notes = []

    for r in rows:
        notes.append({
            "sender": r.sender,
            "note": r.message,
            "timestamp": r.created_at
        })

    return jsonify({"notes": notes})

@csrf.exempt
@app.route("/api/coach/add-note", methods=["POST"])
def coach_add_note():

    data = request.json
    member_id = data["patient_id"]
    message = data["note"]
    coach_id = session["user_id"]

    db.session.execute(text("""
    INSERT INTO telehealth_chat
    (member_id, coach_id, sender, message)
    VALUES (:m,:c,'coach',:msg)
    """), {"m":member_id,"c":coach_id,"msg":message})
    
    db.session.commit()

    return jsonify({"status":"ok"})


@app.route("/api/coach/profile")
def coach_profile():
    if "user_id" not in session:
        return jsonify({"error": "Unauthorized"}), 401

    coach = User.query.get(session["user_id"])

    if not coach or coach.role != "coach":
        return jsonify({"error": "Not a coach"}), 403

    return jsonify({
        "id": coach.id,
        "name": coach.username,
        "email": coach.email,
        "status": coach.verification_status
    })

@app.route("/api/telehealth/data")
def telehealth_data():
    if "user_id" not in session:
        return jsonify({"error": "Unauthorized"}), 401
    
    # 1. Get latest Coach Note
    note = CoachNote.query.filter_by(user_id=session["user_id"]).order_by(CoachNote.created_at.desc()).first()

    # 2. Get latest Heart Rate (as a proxy for health metrics if you don't have a specific table)
    user = User.query.get(session["user_id"])

    hr = HeartRateRecord.query.filter_by(
        user_id=session["user_id"],
        member_id=request.args.get("member_id", type=int)

    ).order_by(HeartRateRecord.created_at.desc()).first()

    return jsonify({
        "avg_bpm": hr.bpm if hr else "--",
        "stress": hr.stress_level if hr else "--",
        "coach_note": note.note if note else None
    })
    
@csrf.exempt
@app.route('/logout', methods=["GET", "POST"])  
def logout():
    session.clear()
    flash('Logged out successfully.', 'info')
    return redirect(url_for('login'))

def diet_recommendation(bpm):
    if bpm < 60:
        return "Energy-support diet (complex carbs, hydration)"
    elif 60 <= bpm <= 90:
        return "Balanced heart-healthy diet"
    else:
        return "Stress-reduction & low-salt diet"
    
@app.route("/api/diet")
def api_diet():
    bpm = int(request.args.get("bpm", 72))  
    return {
        "bpm": bpm,
        "recommendation": diet_recommendation(bpm)
    }

@app.route("/article/<slug>")
def article_page(slug):
    article = ARTICLES.get(slug)
    if not article:
        return "Article not found", 404

    return render_template("article.html", article=article)


ARTICLES = {
    "resting-heart-rate": {
        "title": "Resting Heart Rate Explained",
        "category": "Heart Health",
        "read_time": "4 min",
        "content": """
Your resting heart rate (RHR) is the number of times your heart beats per minute while at complete rest.

A lower resting heart rate usually indicates better cardiovascular fitness and heart efficiency.

• Average adult RHR: 60–100 BPM  
• Athletes: 40–60 BPM  
• High RHR may indicate stress, dehydration, or illness

Improving sleep, reducing stress, and regular exercise can help lower resting heart rate.
"""
    },
    "heart-healthy-diet": {
        "title": "Best Foods for Heart Health",
        "category": "Diet",
        "read_time": "5 min",
        "content": """
A heart-healthy diet focuses on whole foods, healthy fats, and low sodium intake.

Recommended foods:
• Nuts and seeds
• Fruits & vegetables
• Whole grains
• Omega-3 rich foods (fish, flaxseed)

Avoid excessive sugar, fried foods, and processed meats.
"""
    }
}

ARTICLES["resting-heart-rate"]["recommended_by"] = "Dr. Cardiology"
ARTICLES["heart-healthy-diet"]["recommended_by"] = "Health Coach"

def ai_pick_article(bpm):
    if bpm > 90:
        return "resting-heart-rate"
    return "heart-healthy-diet"

@app.route("/api/ai-read")
def ai_read():
    bpm = 88  # later from DB
    slug = ai_pick_article(bpm)
    return {"slug": slug, "article": ARTICLES[slug]}

@csrf.exempt
@app.route("/api/physical-health", methods=["POST"])
def api_physical_health():
    if "user_id" not in session:
        return jsonify({"error": "Unauthorized"}), 401

    data = request.get_json()

    try:
        age = int(data.get("age"))
        weight = float(data.get("weight"))
        height = float(data.get("height"))

        if (
            age < 5 or age > 100 or
            weight < 20 or weight > 200 or
            height < 100 or height > 220
        ):
            return jsonify({"error": "Invalid input values"}), 400

        wasi = calculate_wasi(age, weight, height)
        mls = calculate_mls(age, weight, height)

        return jsonify({
            "wasi": wasi,
            "mls": mls
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/confirm_email/<token>")
def confirm_email(token):
    try:
        email = s.loads(token, salt="email-confirm", max_age=3600)
    except Exception:
        flash("Verification link invalid or expired.", "danger")
        return redirect(url_for("login"))

    user = User.query.filter_by(email=email).first()
    if user:
        user.is_verified = True
        db.session.commit()

    flash("Email verified successfully!", "success")
    return redirect(url_for("login"))


@app.route("/api/family-members")
def get_family_members():
    if "user_id" not in session:
        return jsonify([]), 401

    members = FamilyMember.query.filter_by(user_id=session["user_id"]).all()

    return jsonify([
        {
            "id": m.member_id,
            "name": m.member_name,
            "relationship": m.relationship
        } for m in members
    ])


@csrf.exempt
@app.route("/api/family-members/add", methods=["POST"])
def add_family_member():
    if "user_id" not in session: 
        return jsonify({"error": "Unauthorized"}), 401
    
    data = request.json
    name = data.get("name")
    relation = data.get("relationship")
    
    if not name or not relation:
        return jsonify({"error": "Missing fields"}), 400
        
    try:
        new_member = FamilyMember(
            user_id=session["user_id"],
            member_name=name,
            relationship=relation.lower()
        )

        db.session.add(new_member)
        db.session.commit()
        
        return jsonify({"success": True, "id": new_member.member_id})
    except Exception as e:
        print("Error adding member:", e)
        return jsonify({"success": False, "error": str(e)}), 500
    
    
@csrf.exempt
@app.route("/api/family-members/delete/<int:member_id>", methods=["DELETE"])
def delete_family_member(member_id):
    if "user_id" not in session:
        return jsonify({"error": "Unauthorized"}), 401

    member = FamilyMember.query.filter_by(
        member_id=member_id,
        user_id=session["user_id"]
    ).first()

    if not member:
        return jsonify({"error": "Member not found"}), 404

    if member.user_id != session["user_id"]:
        return jsonify({"error": "Unauthorized action"}), 403

    if member.relationship.lower() == "self":
        return jsonify({"error": "Cannot delete your main profile"}), 400

    try:
        # ✅ DELETE HEART RATE DATA
        HeartRateRecord.query.filter_by(
            member_id=member_id,
            user_id=session["user_id"]
        ).delete()

        StressAssessment.query.filter_by(
            member_id=member_id,
            user_id=session["user_id"]
        ).delete()


        # ✅ DELETE MEMBER
        db.session.delete(member)
        db.session.commit()

        return jsonify({"success": True})

    except Exception as e:
        db.session.rollback()
        print("Error deleting member:", e)
        return jsonify({"error": "Database error"}), 500

    
# Make sure this import exists at the top of app.py
from sqlalchemy import func 

@app.route('/api/heart-rate/last-7')
def get_last_7_heart_rates():
    if 'user_id' not in session:
        return jsonify([]), 401

    target_member_id = request.args.get("member_id", type=int)

    query = HeartRateRecord.query.filter_by(
        user_id=session["user_id"],
        member_id=target_member_id
    )

    if not target_member_id:
        return jsonify({"error": "member_id required"}), 400


    records = query.order_by(HeartRateRecord.created_at.desc()).limit(7).all()
    if not records:
        return jsonify([])

    result = []
    ist = pytz.timezone("Asia/Kolkata")

    for r in records:
        member = FamilyMember.query.get(r.member_id)
        member_name = member.member_name if member else session["username"]

        local_time = r.created_at.replace(tzinfo=pytz.utc).astimezone(ist)

        result.append({
            "bpm": r.bpm,
            "member_name": member_name,
            "time": local_time.strftime("%d %b %Y %I:%M %p"),
            
            # 🔥 ADD THESE LINES so the frontend receives the data
            "aqi": r.aqi,
            "pm25": r.pm25,
            "pm10": r.pm10
        })

    return jsonify(result)


@csrf.exempt
@app.route("/api/set-selected-member", methods=["POST"])
def set_selected_member():
    if "user_id" not in session:
        return jsonify({"error": "Unauthorized"}), 401

    data = request.json
    member_id = data.get("member_id")

    member = FamilyMember.query.filter_by(
        member_id=member_id,
        user_id=session["user_id"]
    ).first()

    if not member:
        return jsonify({"error": "Invalid member"}), 403

    user = User.query.get(session["user_id"])
    user.selected_member_id = member_id
    db.session.commit()

    return jsonify({"success": True})


@app.route("/api/get-selected-member")
def get_selected_member():
    if "user_id" not in session:
        return jsonify({"member_id": None})

    user = User.query.get(session["user_id"])
    return jsonify({"member_id": user.selected_member_id})

@csrf.exempt
@app.route("/api/member/update-medical", methods=["POST"])
def api_update_member_medical():
    if "user_id" not in session:
        return jsonify({"error": "Unauthorized"}), 401

    data = request.json
    member_id = data.get("member_id")
    
    # .get() returns None if the key is missing (Safe for heart_rate.html)
    age = data.get("age")
    city = data.get("city")
    weight = data.get("weight")
    height = data.get("height")

    if not member_id:
        return jsonify({"error": "Missing member_id"}), 400

    member = FamilyMember.query.filter_by(
        member_id=member_id,
        user_id=session["user_id"]
    ).first()

    if not member:
        return jsonify({"error": "Member not found"}), 404

    # Update fields ONLY if they exist in the request
    if age: member.age = int(age)
    if city: member.city = city
    if weight: member.weight = float(weight)
    if height: member.height = float(height)

    db.session.commit()

    return jsonify({"success": True})

@app.route("/blood-donation")
def blood_donation():
    if "user_id" not in session:
        return redirect(url_for("login"))

    family_members = FamilyMember.query.filter_by(user_id=session["user_id"]).all()
    return render_template("features/blood_donation.html", family_members=family_members)

@app.route("/api/blood-donation-eligibility")
def blood_donation_eligibility():
    if "user_id" not in session:
        return jsonify({"eligible": False, "reason": "Login required"})

    member_id = request.args.get("member_id", type=int)

    # Fetch member
    member = FamilyMember.query.filter_by(
        member_id=member_id,
        user_id=session["user_id"]
    ).first()

    if not member:
        return jsonify({"eligible": False, "reason": "Member not found"})

    # 1️⃣ AGE CHECK
    if not member.age or member.age < 18 or member.age > 65:
        return jsonify({"eligible": False, "reason": "Age must be 18–65 years"})

    # 2️⃣ BMI CHECK
    if not member.height or not member.weight:
        return jsonify({"eligible": False, "reason": "Height/Weight missing"})

    height_m = member.height / 100
    bmi = member.weight / (height_m ** 2)

    if bmi < 18.5 or bmi > 30:
        return jsonify({"eligible": False, "reason": f"BMI unsafe ({round(bmi,1)})"})

    # 3️⃣ HEART RATE CHECK (last 7)
    hr_records = HeartRateRecord.query.filter_by(
        user_id=session["user_id"],
        member_id=member_id
    ).order_by(HeartRateRecord.created_at.desc()).limit(7).all()

    if len(hr_records) < 3:
        return jsonify({"eligible": False, "reason": "Not enough heart rate data"})

    avg_hr = sum([r.bpm for r in hr_records]) / len(hr_records)

    if avg_hr < 50 or avg_hr > 100:
        return jsonify({"eligible": False, "reason": f"Unstable heart rate ({int(avg_hr)} BPM)"})

    # 4️⃣ STRESS CHECK
    stress = StressAssessment.query.filter_by(
        user_id=session["user_id"],
        member_id=member_id
    ).order_by(StressAssessment.updated_at.desc()).first()

    if stress and stress.total_score and stress.total_score > 25:
        return jsonify({"eligible": False, "reason": "High stress detected"})

    # ✅ FINAL ELIGIBLE
    return jsonify({
        "eligible": True,
        "bmi": round(bmi, 1),
        "avg_hr": int(avg_hr),
        "stress_score": stress.total_score if stress else "NA",
        "note": "Check hemoglobin before donation"
    })

@app.route("/api/blood-donation/check-missing")
def check_missing_data():
    if "user_id" not in session:
        return jsonify({"error": "Unauthorized"}), 401

    member_id = request.args.get("member_id", type=int)

    member = FamilyMember.query.filter_by(
        member_id=member_id,
        user_id=session["user_id"]
    ).first()

    if not member:
        return jsonify({"error": "Member not found"}), 404

    missing = []

    if not member.age:
        missing.append("age")
    if not member.height:
        missing.append("height")
    if not member.weight:
        missing.append("weight")

    # Heart rate count
    hr_count = HeartRateRecord.query.filter_by(
        user_id=session["user_id"],
        member_id=member_id
    ).count()

    if hr_count < 3:
        missing.append("heart_rate")

    stress = StressAssessment.query.filter_by(
        user_id=session["user_id"],
        member_id=member_id
    ).first()

    if not stress:
        missing.append("stress")

    return jsonify({"missing": missing})

@csrf.exempt
@app.route("/api/blood-donation/save-missing", methods=["POST"])
def save_missing_data():
    if "user_id" not in session:
        return jsonify({"error": "Unauthorized"}), 401

    data = request.json
    member_id = data.get("member_id")

    member = FamilyMember.query.filter_by(
        member_id=member_id,
        user_id=session["user_id"]
    ).first()

    if not member:
        return jsonify({"error": "Member not found"}), 404

    if data.get("age"): member.age = int(data["age"])
    if data.get("height"): member.height = float(data["height"])
    if data.get("weight"): member.weight = float(data["weight"])

    db.session.commit()
    return jsonify({"success": True})

from flask import Flask, render_template, jsonify, request, session, redirect, url_for
from flask_login import login_required, current_user
from datetime import datetime

if __name__ == '__main__':
    app.run(debug=True)
