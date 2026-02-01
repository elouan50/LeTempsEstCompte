# LeTempsEstCompté ⏳

A minimalist, high-vibe time management application designed for local use. Track your work sessions, manage daily goals, and visualize your productivity with beautiful metrics.

Completely vibe-coded with **Google Antigravity** over multiple iterations.

> [!WARNING]
> **Disclaimer**: This is a local-first application. No security features or authentication are implemented. Do not use it for sensitive data. Use at your own risk.

## ✨ Features

### 📊 Advanced Metrics Dashboard
- **Dynamic Productivity Timeline**: Interactive Bar charts (Work, Sick, Vacation) with automatic today-highlighting for immediate focus.
- **Deep Focus Visualization**: Overlap your specific tasks directly onto the working day to see exactly where your time went.
- **Micro-Insight Popups**: Hover over tag badges to instantly preview the specific tasks associated with them.
- **Smarter Tag Distribution**: 
    - **Task Breakdown**: Shows absolute impact (each task counts for all its tags).
    - **Time Breakdown**: Shows relative effort (time shared equally among tags).
- **Interactive Navigation**: Seamlessly navigate between Day, Week, Month, and Year views.

### 📝 Professional PDF Reports
- **Contextual Generation**: Generate reports for a specific month, year, or your entire history.
- **Dual Perspective**: Export detailed Task Lists or Time-based summaries (including precise pause tracking).
- **Spontaneous Previews**: Dates auto-adjust based on your selection for a frictionless experience.

### 🛠️ High-Efficiency Dashboard
- **Intention Setting**: Start every day with a clear main goal that populates your daily header.
- **Precision Tracking**: Log focus sessions for specific tasks, manage multiple pauses, and manual time overrides if needed.
- **PWA Ready**: Install as a standalone app for an immersive, clutter-free productivity environment.

## 🚀 Getting Started

### Requirements
- Python 3.8+
- Flask & Flask-SQLAlchemy
- FPDF2 (for reporting)

### Installation

1. **Setup environment**:
   ```bash
   pip install -r requirements.txt
   ```
2. **Launch**:
   ```bash
   python app.py
   ```
3. **Access**:
   [http://127.0.0.1:5000](http://127.0.0.1:5000)

## 🛠️ Technical Stack
- **Backend**: Python / Flask
- **Database**: SQLAlchemy (SQLite)
- **Frontend**: Vanilla JS (Chart.js), CSS, HTML5
- **Reports**: FPDF2

---
*Created with ❤️ by Antigravity*
