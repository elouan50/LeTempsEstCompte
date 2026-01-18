# LeTempsEstCompté ⏳

A minimalist, high-vibe time management application designed for local use. Track your work sessions, manage daily goals, and visualize your productivity with beautiful metrics.

Completely vibe-coded with **Google Antigravity** in just a few hours.

> [!WARNING]
> **Disclaimer**: This is a local-first application. No security features or authentication are implemented. Do not use it for sensitive data. Use at your own risk.

## ✨ Features

### 📊 Interactive Metrics Dashboard (Homepage)
- **Dynamic Chart**: A Chart.js visualization of your working hours.
- **Effective Work Visualization**: Chart bars automatically show gaps for pauses, giving you a clear view of your actual working segments.
- **Interactive Navigation**: Click any bar in the graph to jump directly to the dashboard for that specific day.
- **Flexible Views**: Toggle between Week, Month, and Year perspectives.
- **Today Highlight**: A dedicated visual frame around the current day's hours.
- **Session History**: A detailed table summarizing starts, ends, total pause durations, and task completion rates.

### 🛠️ Daily Dashboard
- **Goal Management**: Set and edit your daily objective on the fly.
- **Advanced Task Management**: Add, toggle, edit, or delete tasks.
- **Multi-Pause Tracking**: Unlike simple lunch tracking, you can add any number of pauses (coffee breaks, meetings, lunch) with manual time controls.
- **Precise Time Control**: Manually override your session start and end times if you forgot to clock in/out.
- **Automatic Persistence**: All changes are saved instantly to your local database.

## 🚀 Getting Started

### Requirements
- Python 3.8+
- Flask & Flask-SQLAlchemy

### Installation

1. **Clone the repository** (if applicable) or navigate to the project folder.
2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```
3. **Run the application**:
   ```bash
   python app.py
   ```
4. **Access the App**:
   Open your browser at [http://127.0.0.1:5000](http://127.0.0.1:5000)

## 🛠️ Technical Stack
- **Backend**: Python / Flask
- **Database**: SQLAlchemy (SQLite)
- **Frontend**: Vanilla JavaScript, CSS, HTML5
- **Charts**: Chart.js with Date-FNS adapter

## 📄 License
This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---
*Created with ❤️ by Antigravity*
