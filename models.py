"""
PoseAI — Database Models

Stores authenticated users, workout sessions, and user statistics
via Flask-SQLAlchemy. Passwords are always stored as Werkzeug-generated
hashes. Workout sessions track completed exercises per user.
"""

from datetime import datetime, timezone

from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash

# Shared instance — initialized by app.py via db.init_app(app)
db = SQLAlchemy()


class User(db.Model):
    """
    A registered PoseAI user.

    password_hash is never exposed to the API layer.
    The plaintext password is never stored.
    """

    __tablename__ = "users"

    id           = db.Column(db.Integer, primary_key=True, autoincrement=True)
    full_name    = db.Column(db.String(120), nullable=False)
    username     = db.Column(db.String(80), unique=True, nullable=False, index=True)
    email        = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(256), nullable=False)
    is_active    = db.Column(db.Boolean, default=True, nullable=False)
    created_at   = db.Column(
        db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False
    )
    updated_at   = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # ── Relationships ──────────────────────────────────────────────
    workout_sessions = db.relationship(
        "WorkoutSession", backref="user", lazy=True, cascade="all, delete-orphan"
    )
    user_stats = db.relationship(
        "UserStats", backref="user", uselist=False, lazy=True, cascade="all, delete-orphan"
    )
    user_achievements = db.relationship(
        "UserAchievement", backref="user", lazy=True, cascade="all, delete-orphan"
    )

    # ── Password helpers ──────────────────────────────────────────────

    def set_password(self, raw_password: str) -> None:
        self.password_hash = generate_password_hash(raw_password)

    def check_password(self, raw_password: str) -> bool:
        return check_password_hash(self.password_hash, raw_password)

    # ── Serialisation (never leaks password_hash) ────────────────────

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "full_name": self.full_name,
            "username": self.username,
            "email": self.email,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    def __repr__(self) -> str:
        return f"<User {self.username}>"


class WorkoutSession(db.Model):
    """A single completed workout session linked to a user."""

    __tablename__ = "workout_sessions"

    id         = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id    = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    exercise   = db.Column(db.String(80), nullable=False)
    reps       = db.Column(db.Integer, default=0, nullable=False)
    sets       = db.Column(db.Integer, default=0, nullable=False)
    duration   = db.Column(db.Integer, default=0, nullable=False)  # seconds
    calories   = db.Column(db.Float, default=0.0, nullable=False)
    accuracy   = db.Column(db.Float, default=0.0, nullable=False)  # 0-100 form score
    feedback   = db.Column(db.Text, default="", nullable=False)
    date       = db.Column(db.Date, nullable=False, index=True)
    created_at = db.Column(
        db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "user_id": self.user_id,
            "exercise": self.exercise,
            "reps": self.reps,
            "sets": self.sets,
            "duration": self.duration,
            "calories": self.calories,
            "accuracy": self.accuracy,
            "feedback": self.feedback,
            "date": self.date.isoformat() if self.date else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    def __repr__(self) -> str:
        return f"<WorkoutSession {self.exercise} {self.date}>"


class UserStats(db.Model):
    """Aggregated lifetime statistics for a user. One row per user."""

    __tablename__ = "user_stats"

    id              = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id         = db.Column(db.Integer, db.ForeignKey("users.id"), unique=True, nullable=False, index=True)
    total_workouts  = db.Column(db.Integer, default=0, nullable=False)
    total_reps      = db.Column(db.Integer, default=0, nullable=False)
    total_sets      = db.Column(db.Integer, default=0, nullable=False)
    total_calories  = db.Column(db.Float, default=0.0, nullable=False)
    total_duration  = db.Column(db.Integer, default=0, nullable=False)  # seconds
    current_streak  = db.Column(db.Integer, default=0, nullable=False)
    longest_streak  = db.Column(db.Integer, default=0, nullable=False)
    last_workout_date = db.Column(db.Date, nullable=True)
    best_reps       = db.Column(db.Integer, default=0, nullable=False)
    best_calories   = db.Column(db.Float, default=0.0, nullable=False)
    best_duration   = db.Column(db.Integer, default=0, nullable=False)
    best_form_score = db.Column(db.Float, default=0.0, nullable=False)
    updated_at      = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    def to_dict(self) -> dict:
        return {
            "total_workouts": self.total_workouts,
            "total_reps": self.total_reps,
            "total_sets": self.total_sets,
            "total_calories": round(self.total_calories, 1),
            "total_duration": self.total_duration,
            "current_streak": self.current_streak,
            "longest_streak": self.longest_streak,
            "last_workout_date": self.last_workout_date.isoformat() if self.last_workout_date else None,
            "best_reps": self.best_reps,
            "best_calories": round(self.best_calories, 1),
            "best_duration": self.best_duration,
            "best_form_score": round(self.best_form_score, 1),
        }


# ── Achievement Definitions ──────────────────────────────────────────
# These are the canonical achievement types. They are NOT a database
# table — they are a fixed catalog. User progress is tracked in
# UserAchievement.

ACHIEVEMENT_DEFINITIONS: list[dict] = [
    {"key": "first_rep",       "name": "First Rep",       "description": "Complete your first tracked rep.",        "category": "milestone", "xp": 10,  "target": 1},
    {"key": "first_workout",   "name": "First Workout",   "description": "Complete your first workout.",             "category": "milestone", "xp": 50,  "target": 1},
    {"key": "workouts_5",      "name": "5 Workouts",      "description": "Complete 5 workouts.",                     "category": "milestone", "xp": 75,  "target": 5},
    {"key": "workouts_10",     "name": "10 Workouts",     "description": "Complete 10 workouts.",                    "category": "milestone", "xp": 100, "target": 10},
    {"key": "workouts_50",     "name": "50 Workouts",     "description": "Complete 50 workouts.",                    "category": "milestone", "xp": 250, "target": 50},
    {"key": "reps_50",         "name": "50 Reps",         "description": "Complete 50 total reps.",                  "category": "reps",      "xp": 50,  "target": 50},
    {"key": "reps_100",        "name": "100 Reps",        "description": "Complete 100 total reps.",                 "category": "reps",      "xp": 100, "target": 100},
    {"key": "reps_500",        "name": "500 Reps",        "description": "Complete 500 total reps.",                 "category": "reps",      "xp": 200, "target": 500},
    {"key": "reps_1000",       "name": "1000 Reps",       "description": "Complete 1000 total reps.",                "category": "reps",      "xp": 500, "target": 1000},
    {"key": "streak_3",        "name": "3 Day Streak",    "description": "Work out 3 days in a row.",               "category": "streak",    "xp": 30,  "target": 3},
    {"key": "streak_7",        "name": "7 Day Streak",    "description": "Work out 7 days in a row.",               "category": "streak",    "xp": 100, "target": 7},
    {"key": "streak_30",       "name": "30 Day Streak",   "description": "Work out 30 days in a row.",              "category": "streak",    "xp": 500, "target": 30},
    {"key": "calorie_burn_100", "name": "Calorie Burn",   "description": "Burn 100 total calories.",                 "category": "calories",  "xp": 50,  "target": 100},
    {"key": "calorie_burn_500", "name": "Calorie Crusher","description": "Burn 500 total calories.",                 "category": "calories",  "xp": 200, "target": 500},
    {"key": "form_master",     "name": "Form Master",     "description": "Achieve 90%+ form score in a workout.",   "category": "form",      "xp": 75,  "target": 90},
    {"key": "consistency_king", "name": "Consistency King","description": "Complete 7 workouts in one week.",        "category": "milestone", "xp": 150, "target": 7},
]

# Map from achievement key to its definition for fast lookup
ACHIEVEMENT_MAP: dict[str, dict] = {a["key"]: a for a in ACHIEVEMENT_DEFINITIONS}


class UserAchievement(db.Model):
    """Tracks which achievements a user has unlocked and their progress."""

    __tablename__ = "user_achievements"

    id            = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id       = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    achievement_key = db.Column(db.String(80), nullable=False, index=True)
    unlocked      = db.Column(db.Boolean, default=False, nullable=False)
    progress      = db.Column(db.Float, default=0.0, nullable=False)
    unlocked_at   = db.Column(db.DateTime, nullable=True)

    __table_args__ = (
        db.UniqueConstraint("user_id", "achievement_key", name="uq_user_achievement"),
    )

    def to_dict(self) -> dict:
        definition = ACHIEVEMENT_MAP.get(self.achievement_key, {})
        return {
            "key": self.achievement_key,
            "name": definition.get("name", self.achievement_key),
            "description": definition.get("description", ""),
            "category": definition.get("category", "milestone"),
            "xp": definition.get("xp", 0),
            "target": definition.get("target", 1),
            "progress": self.progress,
            "unlocked": self.unlocked,
            "unlocked_at": self.unlocked_at.isoformat() if self.unlocked_at else None,
        }
