"""
base_workout.py
----------------
Base class for all workout types.
"""


class BaseWorkout:

    def __init__(self, name):

        self.name = name

        self.reps = 0

        self.stage = None

        self.feedback = ""

    def update(self, landmarks):
        """
        This method will be implemented
        by each specific workout.
        """
        raise NotImplementedError

    def reset(self):

        self.reps = 0

        self.stage = None

        self.feedback = ""

    def get_data(self):

        return {
            "exercise": self.name,
            "reps": self.reps,
            "stage": self.stage,
            "feedback": self.feedback
        }