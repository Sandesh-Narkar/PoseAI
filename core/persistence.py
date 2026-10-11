"""
Persistence Layer for Completed Workout Sessions

Manages saving and retrieving completed workout sessions from disk.
Uses file-based storage (JSON) in the data/ folder.

Responsibilities:
    - Create and save completed workout sessions
    - Retrieve all sessions or sessions for a specific date
    - Generate session IDs and timestamps
    - Calculate streak from persisted session dates
    - Ensure data persists across backend restarts
"""

import json
import os
import uuid
from datetime import datetime, date
from pathlib import Path
from typing import Any, Optional


class Session:
    """Represents a completed workout session."""

    def __init__(
        self,
        exercise: str,
        reps: int,
        sets: int,
        duration: int,  # in seconds
        calories: float,
        accuracy: float,  # 0-100, performance rating
        timestamp: str = None,  # ISO format string
    ) -> None:
        self.id = str(uuid.uuid4())
        self.exercise = exercise
        self.reps = reps
        self.sets = sets
        self.duration = duration
        self.calories = round(calories, 2)
        self.accuracy = round(accuracy, 1)
        self.status = "completed"
        
        if timestamp is None:
            self.timestamp = datetime.now().isoformat()
        else:
            self.timestamp = timestamp
        
        # Extract date from timestamp for streak calculation
        dt = datetime.fromisoformat(self.timestamp)
        self.date = dt.strftime("%Y-%m-%d")

    def to_dict(self) -> dict[str, Any]:
        """Convert session to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "exercise": self.exercise,
            "reps": self.reps,
            "sets": self.sets,
            "duration": self.duration,
            "calories": self.calories,
            "accuracy": self.accuracy,
            "status": self.status,
            "date": self.date,
            "timestamp": self.timestamp,
        }

    @staticmethod
    def from_dict(data: dict[str, Any]) -> "Session":
        """Create a session from a dictionary (loaded from JSON)."""
        session = Session(
            exercise=data.get("exercise", "Unknown"),
            reps=int(data.get("reps", 0)),
            sets=int(data.get("sets", 0)),
            duration=int(data.get("duration", 0)),
            calories=float(data.get("calories", 0)),
            accuracy=float(data.get("accuracy", 0)),
            timestamp=data.get("timestamp"),
        )
        # Preserve the original ID and date
        session.id = data.get("id", session.id)
        session.date = data.get("date", session.date)
        session.status = data.get("status", "completed")
        return session


class SessionManager:
    """Manages persistence of workout sessions to disk."""

    def __init__(self, data_dir: str = "data") -> None:
        """Initialize the session manager with a data directory."""
        self.data_dir = Path(data_dir)
        self.sessions_dir = self.data_dir / "sessions"
        self._ensure_directories()

    def _ensure_directories(self) -> None:
        """Create necessary directories if they don't exist."""
        self.data_dir.mkdir(exist_ok=True)
        self.sessions_dir.mkdir(exist_ok=True)

    def _get_session_file(self, session_id: str) -> Path:
        """Get the file path for a session by ID."""
        return self.sessions_dir / f"{session_id}.json"

    def save_session(self, session: Session) -> bool:
        """
        Save a completed session to disk.
        Returns True if successful, False otherwise.
        """
        try:
            session_file = self._get_session_file(session.id)
            with open(session_file, "w") as f:
                json.dump(session.to_dict(), f, indent=2)
            return True
        except Exception as e:
            print(f"[SessionManager] Error saving session: {e}")
            return False

    def get_session(self, session_id: str) -> Optional[Session]:
        """Retrieve a specific session by ID."""
        try:
            session_file = self._get_session_file(session_id)
            if not session_file.exists():
                return None
            
            with open(session_file, "r") as f:
                data = json.load(f)
            return Session.from_dict(data)
        except Exception as e:
            print(f"[SessionManager] Error loading session {session_id}: {e}")
            return None

    def get_all_sessions(self) -> list[dict[str, Any]]:
        """
        Retrieve all saved sessions.
        Returns a list of session dictionaries, sorted by timestamp (newest first).
        """
        sessions = []
        try:
            if not self.sessions_dir.exists():
                return sessions
            
            for session_file in sorted(self.sessions_dir.glob("*.json"), reverse=True):
                try:
                    with open(session_file, "r") as f:
                        data = json.load(f)
                    sessions.append(data)
                except Exception as e:
                    print(f"[SessionManager] Error loading {session_file}: {e}")
                    continue
        except Exception as e:
            print(f"[SessionManager] Error reading sessions directory: {e}")
        
        return sessions

    def get_sessions_for_date(self, target_date: date) -> list[Session]:
        """
        Retrieve all sessions completed on a specific date (YYYY-MM-DD).
        """
        target_date_str = target_date.strftime("%Y-%m-%d")
        sessions = []
        try:
            for session_file in self.sessions_dir.glob("*.json"):
                try:
                    with open(session_file, "r") as f:
                        data = json.load(f)
                    if data.get("date") == target_date_str:
                        session = Session.from_dict(data)
                        sessions.append(session)
                except Exception as e:
                    print(f"[SessionManager] Error loading {session_file}: {e}")
                    continue
        except Exception as e:
            print(f"[SessionManager] Error reading sessions directory: {e}")
        
        return sessions

    def calculate_streak(self) -> int:
        """
        Calculate the current streak based on completed sessions.
        
        Streak logic:
        - One session per calendar day = 1 streak day
        - Multiple sessions on the same day count as 1 day
        - Streak breaks if a day has no completed sessions
        - Count backwards from today
        """
        try:
            all_sessions = self.get_all_sessions()
            if not all_sessions:
                return 0
            
            # Get unique dates from sessions, sorted newest first
            unique_dates = sorted(set(s.get("date") for s in all_sessions), reverse=True)
            
            if not unique_dates:
                return 0
            
            # Start from today and count consecutive days backwards
            today = date.today()
            streak = 0
            
            for date_str in unique_dates:
                session_date = datetime.strptime(date_str, "%Y-%m-%d").date()
                
                # If this date is before today minus streak, the streak is broken
                expected_date = today - __import__("datetime").timedelta(days=streak)
                
                if session_date == expected_date:
                    streak += 1
                elif session_date < expected_date:
                    # Streak is broken
                    break
            
            return streak
        except Exception as e:
            print(f"[SessionManager] Error calculating streak: {e}")
            return 0

    def delete_session(self, session_id: str) -> bool:
        """Delete a session file (for testing/cleanup purposes)."""
        try:
            session_file = self._get_session_file(session_id)
            if session_file.exists():
                session_file.unlink()
                return True
            return False
        except Exception as e:
            print(f"[SessionManager] Error deleting session {session_id}: {e}")
            return False

    def clear_all_sessions(self) -> bool:
        """Delete all session files (for testing/cleanup purposes)."""
        try:
            for session_file in self.sessions_dir.glob("*.json"):
                session_file.unlink()
            return True
        except Exception as e:
            print(f"[SessionManager] Error clearing all sessions: {e}")
            return False


# Global session manager instance
_session_manager: Optional[SessionManager] = None


def get_session_manager(data_dir: str = "data") -> SessionManager:
    """
    Get or create the global session manager.
    Returns the singleton SessionManager instance.
    """
    global _session_manager
    if _session_manager is None:
        _session_manager = SessionManager(data_dir)
    return _session_manager
