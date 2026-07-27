<div align="center">

# PoseAI — AI Fitness Trainer

**Real-time exercise tracking, repetition counting, and posture feedback powered by Computer Vision and Pose Estimation.**

[![Python](https://img.shields.io/badge/Python-3.10+-3776AB?style=flat-square&logo=python&logoColor=white)](https://www.python.org/)
[![OpenCV](https://img.shields.io/badge/OpenCV-Computer%20Vision-5C3EE8?style=flat-square&logo=opencv&logoColor=white)](https://opencv.org/)
[![MediaPipe](https://img.shields.io/badge/MediaPipe-Pose%20Landmarker-00897B?style=flat-square&logo=google&logoColor=white)](https://developers.google.com/mediapipe)
[![Flask](https://img.shields.io/badge/Flask-Backend-000000?style=flat-square&logo=flask&logoColor=white)](https://flask.palletsprojects.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg?style=flat-square)](LICENSE)
[![Status](https://img.shields.io/badge/Status-Active-success?style=flat-square)]()

</div>

---

## Overview

**PoseAI** is a computer-vision-based fitness trainer that analyzes body movement in real time to count exercise repetitions, evaluate form, and deliver instant posture feedback. It combines **MediaPipe's pose landmark detection** with custom joint-angle geometry to give users a lightweight, camera-only alternative to wearable fitness trackers — all running locally through a Flask web dashboard.

---

## Features

| Capability | Description |
|---|---|
| **Real-Time Pose Detection** | Tracks 33 body landmarks per frame using MediaPipe's pose estimation pipeline |
| **Repetition Counting** | Calculates joint angles to detect and count exercise repetitions automatically |
| **Posture Analysis** | Flags incorrect form and range of motion during each rep |
| **Live Feedback** | Displays on-screen corrective cues as the user performs the exercise |
| **Workout Selection** | Choose between supported exercises directly from the dashboard |
| **Web Dashboard** | Clean browser-based UI for starting sessions and viewing live stats |

---

## Supported Exercises

| Exercise | Tracked Joints | Metric |
|---|---|---|
| Bicep Curl | Shoulder – Elbow – Wrist | Elbow flexion angle |
| Bodyweight Squat | Hip – Knee – Ankle | Knee flexion angle |

> Additional exercises can be added by defining new angle thresholds in `workouts/`.

---

## Tech Stack

<div align="center">

| Layer | Technology |
|---|---|
| Core Logic | Python |
| Computer Vision | OpenCV |
| Pose Estimation | MediaPipe |
| Numerical Computation | NumPy |
| Backend / Server | Flask |
| Frontend | HTML, CSS, JavaScript |

</div>

---

## Project Structure

```
PoseAI/
│
├── app.py                 # Flask application entry point
├── requirements.txt        # Python dependencies
│
├── dashboard/               # Web frontend
│   ├── index.html
│   ├── css/
│   ├── js/
│   └── assets/
│
├── core/                    # Pose detection & angle-calculation logic
├── models/                  # Pose landmark model files
├── workouts/                 # Exercise-specific rep-counting logic
└── README.md
```

---

## Installation

**1. Clone the repository**
```bash
git clone https://github.com/Sandesh-Narkar/PoseAI.git
```

**2. Navigate to the project directory**
```bash
cd PoseAI
```

**3. (Recommended) Create a virtual environment**
```bash
python -m venv venv
source venv/bin/activate      # On Windows: venv\Scripts\activate
```

**4. Install dependencies**
```bash
pip install -r requirements.txt
```

**5. Run the application**
```bash
python app.py
```

**6. Open the dashboard**
```
http://127.0.0.1:5000
```

---

## Screenshots

> Add screenshots of the dashboard and live workout detection to a `screenshots/` folder and reference them here.

```
screenshots/
├── dashboard.png
├── squat.png
└── curl.png
```

```markdown
![Dashboard](screenshots/dashboard.png)
![Squat Detection](screenshots/squat.png)
![Curl Detection](screenshots/curl.png)
```

---

## Roadmap

- [ ] Support for additional exercises (push-ups, lunges, planks)
- [ ] Workout history and session logging
- [ ] Performance analytics and progress charts
- [ ] AI-driven workout recommendations
- [ ] User authentication
- [ ] Cloud database integration

---

## Contributing

Contributions are welcome. To contribute:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/your-feature`)
3. Commit your changes (`git commit -m "Add your feature"`)
4. Push to the branch (`git push origin feature/your-feature`)
5. Open a Pull Request

---

## Author

**Sandesh Narkar**
B.Sc. Information Technology Student

[![Email](https://img.shields.io/badge/Email-your--email%40example.com-D14836?style=flat-square&logo=gmail&logoColor=white)](mailto:your-email@example.com)
[![LinkedIn](https://img.shields.io/badge/LinkedIn-Sandesh%20Narkar-0A66C2?style=flat-square&logo=linkedin&logoColor=white)](https://www.linkedin.com/in/sandesh-narkar-2339a03a5)
[![GitHub](https://img.shields.io/badge/GitHub-Sandesh--Narkar-181717?style=flat-square&logo=github&logoColor=white)](https://github.com/Sandesh-Narkar)

---

## Support

If you find this project useful, consider giving it a star on GitHub — it helps others discover the project and supports further development.

---

## License

This project is licensed under the [MIT License](LICENSE).
