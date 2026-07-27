"""
workout_manager.py
------------------
Manages all available workouts.
"""

import time
from workouts.bicep import BicepWorkout
from workouts.pushup import PushupWorkout
from workouts.squat import SquatWorkout
from workouts.lunges import LungesWorkout
from workouts.jumping_jacks import JumpingJacksWorkout
from workouts.shoulder_press import ShoulderPressWorkout
from workouts.burpees import BurpeesWorkout
from workouts.warrior2 import Warrior2Workout
from workouts.goblet_squat import GobletSquatWorkout
from workouts.crossover_toe_touch import CrossoverToeTouchWorkout
from workouts.triceps_pushdown import TricepsPushdownWorkout

class WorkoutManager:

    def __init__(self):

        self.workouts = {
            "bicep": BicepWorkout(),
            "pushup": PushupWorkout(),
            "squat": SquatWorkout(),
            "triceps": TricepsPushdownWorkout(),
            "lunges": LungesWorkout(),
            "jumpingjacks": JumpingJacksWorkout(),
            "shoulder_press": ShoulderPressWorkout(),
            "burpees": BurpeesWorkout(),
            "warrior2": Warrior2Workout(),
            "goblet": GobletSquatWorkout(),
            "toe_touch": CrossoverToeTouchWorkout(),
        }

        self.current_workout = self.workouts["bicep"]
        
        # Session statistics and state attributes tracking metrics across workouts
        self.session_start_time = time.time()
        self.total_reps = 0
        self.exercises_completed = 0
        self.calories_burned = 0.0
        self.xp = 0
        self.streak = 0
        
        # Track historical records for session summaries
        self.best_set = 0
        self.rep_times = []
        self.camera_status = "online"

    def select_workout(self, workout_name):

        if workout_name not in self.workouts:
            return False

        self.current_workout = self.workouts[workout_name]
        self.current_workout.reset()

        return True

    def update(self, *args):

        if self.current_workout is None:
            return None

        # Capture timestamp before and after update to compute tracking speeds if necessary
        start_time = time.time()
        result = self.current_workout.update(*args)
        end_time = time.time()
        
        # Track statistics from the updated result payload if valid
        if isinstance(result, dict):
            reps = result.get("reps", 0)
            if reps > 0:
                self.rep_times.append(end_time - start_time)
                if reps > self.best_set:
                    self.best_set = reps

        return result

    def get_current_workout(self):

        return self.current_workout

    def get_data(self):

        if self.current_workout is None:
            return None

        return self.current_workout.get_data()

    def get_available_workouts(self):

        return list(self.workouts.keys())

    def get_dashboard_data(self):
        """
        Exposes the workout state in a standard dictionary format required for the Flask dashboard.
        """
        data = self.get_data() or {}
        elapsed = int(time.time() - self.session_start_time)
        minutes, seconds = divmod(elapsed, 60)
        workout_time_str = f"{minutes:02d}:{seconds:02d}"

        return {
            "exercise": getattr(self.current_workout, "name", "Unknown"),
            "currentRep": data.get("reps", 0),
            "goalRep": data.get("goal_reps", 15),
            "currentSet": data.get("sets", 1),
            "goalSet": data.get("goal_sets", 3),
            "stage": data.get("stage", "down"),
            "angle": int(data.get("angle", 0)),
            "calories": round(self.calories_burned, 1),
            "workoutTime": workout_time_str,
            "feedback": data.get("feedback", ""),
            "xp": self.xp,
            "streak": self.streak,
            "cameraStatus": self.camera_status
        }

    def get_session_summary(self):
        """
        Exposes full history metrics for rendering the final session overlay display.
        """
        data = self.get_data() or {}
        elapsed = int(time.time() - self.session_start_time)
        minutes, seconds = divmod(elapsed, 60)
        workout_time_str = f"{minutes:02d}:{seconds:02d}"
        
        avg_rep_time = sum(self.rep_times) / len(self.rep_times) if self.rep_times else 0.0

        return {
            "Exercise": getattr(self.current_workout, "name", "Unknown"),
            "Completed Sets": data.get("sets", 1) - 1 if data.get("sets", 1) > 1 else 0,
            "Completed Reps": self.total_reps,
            "Workout Time": workout_time_str,
            "Calories": round(self.calories_burned, 1),
            "XP Earned": self.xp,
            "Average Rep Time": round(avg_rep_time, 2),
            "Best Set": self.best_set,
            "Current Streak": self.streak
        }

    def get_statistics(self):
        """
        Exposes historical counters for tracking global performance parameters.
        """
        elapsed = int(time.time() - self.session_start_time)
        minutes, seconds = divmod(elapsed, 60)
        workout_time_str = f"{minutes:02d}:{seconds:02d}"

        return {
            "Total Reps": self.total_reps,
            "Exercises Completed": self.exercises_completed,
            "Workout Time": workout_time_str,
            "Calories": round(self.calories_burned, 1),
            "XP": self.xp
        }

    def get_workout_status(self):
        """
        Retrieves internal runtime flags mapping the ongoing status configuration.
        """
        data = self.get_data() or {}
        return {
            "status": "active" if self.current_workout else "inactive",
            "camera": self.camera_status,
            "reps_completed": data.get("reps", 0) >= data.get("goal_reps", 15)
        }

    def reset_session(self):
        """
        Resets tracking stats globally without swapping the selected exercise algorithm module.
        """
        self.session_start_time = time.time()
        self.total_reps = 0
        self.exercises_completed = 0
        self.calories_burned = 0.0
        self.xp = 0
        self.streak = 0
        self.best_set = 0
        self.rep_times = []
        self.camera_status = "online"