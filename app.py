from flask import Flask, render_template, request, jsonify, redirect, url_for, send_file
from models import db, DailySession, Task, Pause
from datetime import datetime, timedelta, date
from fpdf import FPDF
from fpdf.enums import XPos, YPos
import textwrap
import io
import os
from sqlalchemy import text

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)

def ensure_status_column():
    try:
        columns = [row[1] for row in db.session.execute(text("PRAGMA table_info(daily_session)")).all()]
        if 'status' not in columns:
            db.session.execute(text(
                "ALTER TABLE daily_session ADD COLUMN status VARCHAR(20) NOT NULL DEFAULT 'work'"
            ))
            db.session.commit()
    except Exception:
        db.session.rollback()
        raise

with app.app_context():
    db.create_all()
    ensure_status_column()

@app.route('/')
def index():
    sessions = DailySession.query.order_by(DailySession.date.desc()).all()
    return render_template('metrics.html', sessions=sessions) # Metrics is now Home

@app.route('/new')
def new_day_form():
    return render_template('start_day.html') # Old index content

@app.route('/start', methods=['POST'])
def start_day():
    date_str = request.form.get('date')
    
    # Determine date first
    if date_str:
        try:
            session_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        except ValueError:
            session_date = datetime.now().date()
    else:
        session_date = datetime.now().date()

    goal = request.form.get('goal')
    
    # If goal is empty, use the Day Name (e.g. "Monday") as the goal
    if not goal or not goal.strip():
        goal = session_date.strftime('%A')
        
    # Check if session exists for this date
    existing_session = DailySession.query.filter_by(date=session_date).first()
    
    if existing_session:
        # Update goal if new one provided? Or keep old? 
        # User intention "Start Day" implies setting input.
        existing_session.goal = goal
        db.session.commit()
        return redirect(url_for('dashboard', session_id=existing_session.id))
    
    # If creating a past/future session, what should start_time be?
    # If today, use now. If other day, maybe use 9:00 AM?
    # For now, let's behave as if we started 'now' but on that date, 
    # OR if it's not today, maybe set start_time to None (waiting) or a default?
    # Current model defaults start_time to datetime.now().
    # Let's construct a datetime for that date.
    
    if session_date == datetime.now().date():
        start_dt = datetime.now()
    else:
        # Default to 9 AM on that day
        start_dt = datetime.combine(session_date, datetime.min.time()).replace(hour=9)
    
    session = DailySession(goal=goal, date=session_date, start_time=start_dt)
    db.session.add(session)
    db.session.commit()
    return redirect(url_for('dashboard', session_id=session.id))

@app.route('/dashboard/<int:session_id>')
def dashboard(session_id):
    session = DailySession.query.get_or_404(session_id)
    return render_template('dashboard.html', session=session)

@app.route('/api/task/add', methods=['POST'])
def add_task():
    data = request.json
    session_id = data.get('session_id')
    description = data.get('description')
    
    if not session_id or not description:
        return jsonify({'error': 'Missing data'}), 400
        
    task = Task(session_id=session_id, description=description)
    db.session.add(task)
    db.session.commit()
    return jsonify({'id': task.id, 'description': task.description, 'is_completed': task.is_completed})

@app.route('/api/task/toggle', methods=['POST'])
def toggle_task():
    data = request.json
    task_id = data.get('task_id')
    
    task = db.session.get(Task, task_id)
    if not task:
        return jsonify({'error': 'Task not found'}), 404
        
    task.is_completed = not task.is_completed
    db.session.commit()
    return jsonify({'id': task.id, 'is_completed': task.is_completed})

@app.route('/api/task/update', methods=['POST'])
def update_task():
    data = request.json
    task_id = data.get('task_id')
    description = data.get('description')
    
    task = db.session.get(Task, task_id)
    if not task:
        return jsonify({'error': 'Task not found'}), 404
        
    task.description = description.strip() if description else task.description
    db.session.commit()
    return jsonify({'status': 'success'})

@app.route('/api/task/delete', methods=['POST'])
def delete_task():
    data = request.json
    task_id = data.get('task_id')
    
    task = db.session.get(Task, task_id)
    if not task:
        return jsonify({'error': 'Task not found'}), 404
    
    db.session.delete(task)
    db.session.commit()
    return jsonify({'status': 'success'})

@app.route('/api/pause/add', methods=['POST'])
def add_pause():
    data = request.json
    session_id = data.get('session_id')
    start_time_str = data.get('start_time')
    end_time_str = data.get('end_time')
    
    session = db.session.get(DailySession, session_id)
    if not session:
        return jsonify({'error': 'Session not found'}), 404
    
    pause = Pause(session_id=session_id)
    if start_time_str:
        pause.start_time = datetime.fromisoformat(start_time_str.replace('Z', ''))
    if end_time_str:
        pause.end_time = datetime.fromisoformat(end_time_str.replace('Z', ''))
    
    db.session.add(pause)
    db.session.commit()
    return jsonify({
        'id': pause.id,
        'start_time': pause.start_time.isoformat() if pause.start_time else None,
        'end_time': pause.end_time.isoformat() if pause.end_time else None
    })

@app.route('/api/pause/update', methods=['POST'])
def update_pause():
    data = request.json
    pause_id = data.get('pause_id')
    start_time_str = data.get('start_time')
    end_time_str = data.get('end_time')
    
    pause = db.session.get(Pause, pause_id)
    if not pause:
        return jsonify({'error': 'Pause not found'}), 404
    
    if start_time_str:
        pause.start_time = datetime.fromisoformat(start_time_str.replace('Z', ''))
    if end_time_str:
        pause.end_time = datetime.fromisoformat(end_time_str.replace('Z', ''))
    
    db.session.commit()
    return jsonify({'status': 'success'})

@app.route('/api/pause/delete', methods=['POST'])
def delete_pause():
    data = request.json
    pause_id = data.get('pause_id')
    
    pause = db.session.get(Pause, pause_id)
    if not pause:
        return jsonify({'error': 'Pause not found'}), 404
    
    db.session.delete(pause)
    db.session.commit()
    return jsonify({'status': 'success'})





@app.route('/api/session/delete', methods=['POST'])
def delete_session():
    data = request.json
    session_id = data.get('session_id')
    
    session = db.session.get(DailySession, session_id)
    if not session:
        return jsonify({'error': 'Session not found'}), 404
    
    db.session.delete(session)
    db.session.commit()
    
    return jsonify({'status': 'success'})

@app.route('/api/session/update_times', methods=['POST'])
def update_session_times():
    data = request.json
    session_id = data.get('session_id')
    start_time_str = data.get('start_time')
    end_time_str = data.get('end_time')
    
    session = db.session.get(DailySession, session_id)
    if not session:
        return jsonify({'error': 'Session not found'}), 404
        
    if 'start_time' in data and data['start_time']:
        # Parse as naive datetime (local time)
        session.start_time = datetime.fromisoformat(data['start_time'].replace('Z', ''))
    
    if 'end_time' in data:
        if data['end_time']:
            # Parse as naive datetime (local time)
            session.end_time = datetime.fromisoformat(data['end_time'].replace('Z', ''))
        else:
            session.end_time = None
        
    db.session.commit()
    return jsonify({'status': 'success'})

@app.route('/api/session/update_goal', methods=['POST'])
def update_session_goal():
    data = request.json
    session_id = data.get('session_id')
    new_goal = data.get('goal')
    
    session = db.session.get(DailySession, session_id)
    if not session:
        return jsonify({'error': 'Session not found'}), 404
        
    session.goal = new_goal
    db.session.commit()
    return jsonify({'status': 'success'})

@app.route('/api/session/update_status', methods=['POST'])
def update_session_status():
    data = request.json
    session_id = data.get('session_id')
    new_status = data.get('status')

    if new_status not in ('work', 'sick', 'vacation'):
        return jsonify({'error': 'Invalid status'}), 400

    session = db.session.get(DailySession, session_id)
    if not session:
        return jsonify({'error': 'Session not found'}), 404

    session.status = new_status

    if new_status in ('sick', 'vacation'):
        session.start_time = None
        session.end_time = None
        for pause in list(session.pauses):
            db.session.delete(pause)

    db.session.commit()
    return jsonify({'status': 'success'})

@app.route('/api/metrics/data')
def metrics_data():
    sessions = DailySession.query.order_by(DailySession.date.asc()).all()
    data = []
    for s in sessions:
        pauses_data = []
        for p in s.pauses:
            pauses_data.append({
                'id': p.id,
                'start_time': p.start_time.isoformat() if p.start_time else None,
                'end_time': p.end_time.isoformat() if p.end_time else None
            })
        data.append({
            'id': s.id,
            'date': s.date.isoformat(),
            'status': s.status,
            'start_time': s.start_time.isoformat() if s.start_time and s.status == 'work' else None,
            'end_time': s.end_time.isoformat() if s.end_time and s.status == 'work' else None,
            'pauses': pauses_data
        })
    return jsonify(data)

def format_minutes(total_minutes):
    if total_minutes is None:
        return "--"
    total_minutes = max(0, int(total_minutes))
    hours = total_minutes // 60
    minutes = total_minutes % 60
    return f"{hours}:{minutes:02d}"

def sum_pause_minutes(pauses):
    total = 0
    for pause in pauses:
        if pause.start_time and pause.end_time:
            total += int((pause.end_time - pause.start_time).total_seconds() / 60)
    return total

def add_time_report_table(pdf, rows):
    col_widths = [35, 75, 30, 30, 20]
    headers = ["Date", "Note", "Work", "Pause", "Total"]
    pdf.set_font("Helvetica", size=10)
    for idx, header in enumerate(headers):
        pdf.cell(col_widths[idx], 8, header, border=1, align="L")
    pdf.ln(8)

    if not rows:
        pdf.cell(sum(col_widths), 8, "No sessions in selected period.", border=1, align="L")
        pdf.ln(8)
        return

    for row in rows:
        if row.get("type") == "week_total":
            pdf.set_font("Helvetica", style="B", size=10)
        else:
            pdf.set_font("Helvetica", size=10)
        pdf.cell(col_widths[0], 8, row["date"], border=1, align="L")
        pdf.cell(col_widths[1], 8, row["note"], border=1, align="L")
        pdf.cell(col_widths[2], 8, row["work"], border=1, align="R")
        pdf.cell(col_widths[3], 8, row["pause"], border=1, align="R")
        pdf.cell(col_widths[4], 8, row["total"], border=1, align="R")
        pdf.ln(8)
    pdf.set_font("Helvetica", size=10)

def add_task_report_table(pdf, task_rows):
    col_date = 35
    col_tasks = 155
    line_height = 6

    def add_header():
        pdf.set_font("Helvetica", size=10)
        pdf.cell(col_date, 8, "Date", border=1, align="L")
        pdf.cell(col_tasks, 8, "Tasks", border=1, align="L")
        pdf.ln(8)

    add_header()

    if not task_rows:
        pdf.cell(col_date + col_tasks, 8, "No sessions in selected period.", border=1, align="L")
        pdf.ln(8)
        return

    for row in task_rows:
        tasks_text = row["tasks"] if row["tasks"] else "-"
        tasks_lines = textwrap.wrap(tasks_text, width=90) or ["-"]
        row_height = line_height * len(tasks_lines)

        if pdf.get_y() + row_height > pdf.page_break_trigger:
            pdf.add_page()
            add_header()

        x = pdf.get_x()
        y = pdf.get_y()
        pdf.multi_cell(col_date, row_height, row["date"], border=1, align="L")
        pdf.set_xy(x + col_date, y)
        pdf.multi_cell(col_tasks, line_height, "\n".join(tasks_lines), border=1, align="L")
        pdf.set_xy(x, y + row_height)

@app.route('/reports')
def reports():
    today = datetime.now().date()
    default_start = today - timedelta(days=6)
    return render_template('reports.html',
                           default_start=default_start.isoformat(),
                           default_end=today.isoformat())

@app.route('/reports/pdf', methods=['POST'])
def reports_pdf():
    report_type = request.form.get('report_type')
    start_str = request.form.get('date_start')
    end_str = request.form.get('date_end')

    if not start_str or not end_str:
        return redirect(url_for('reports'))

    try:
        start_date = datetime.strptime(start_str, '%Y-%m-%d').date()
        end_date = datetime.strptime(end_str, '%Y-%m-%d').date()
    except ValueError:
        return redirect(url_for('reports'))

    if end_date < start_date:
        start_date, end_date = end_date, start_date

    sessions = DailySession.query.filter(
        DailySession.date.between(start_date, end_date)
    ).order_by(DailySession.date.asc()).all()

    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    pdf.set_font("Helvetica", size=16)

    date_range_label = f"{start_date.isoformat()} to {end_date.isoformat()}"

    pdf.set_font("Helvetica", size=11)
    pdf.cell(0, 8, "Felix Walger", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(2)

    if report_type == "tasks":
        pdf.cell(0, 10, "Task Report", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.set_font("Helvetica", size=11)
        pdf.cell(0, 8, f"Period: {date_range_label}", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.ln(4)

        task_rows = []
        for session in sessions:
            if session.status == "sick":
                task_texts = ["KRANKHEIT"]
            elif session.status == "vacation":
                task_texts = ["URLAUB"]
            else:
                task_texts = [t.description for t in session.tasks]
            task_rows.append({
                "date": session.date.strftime('%Y-%m-%d'),
                "tasks": "; ".join(task_texts) if task_texts else "-"
            })

        add_task_report_table(pdf, task_rows)
        filename = f"tasks_{start_date.isoformat()}_{end_date.isoformat()}.pdf"

    else:
        pdf.cell(0, 10, "Time Report", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.set_font("Helvetica", size=11)
        pdf.cell(0, 8, f"Period: {date_range_label}", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.cell(0, 8, "Includes pauses.", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.ln(4)

        rows = []
        weekly_totals = {}

        for session in sessions:
            iso_year, iso_week, _ = session.date.isocalendar()
            weekly_totals.setdefault((iso_year, iso_week), {"work": 0, "pause": 0, "total": 0})

            if session.status in ("sick", "vacation"):
                work_minutes = 7 * 60 + 50
                pause_minutes = 30
                total_minutes = work_minutes + pause_minutes
                note = "Krank" if session.status == "sick" else "Urlaub"
            else:
                if not session.start_time or not session.end_time:
                    work_minutes = 0
                    pause_minutes = 0
                    total_minutes = 0
                    note = "Unvollständig"
                else:
                    total_minutes = int((session.end_time - session.start_time).total_seconds() / 60)
                    pause_minutes = sum_pause_minutes(session.pauses)
                    work_minutes = max(total_minutes - pause_minutes, 0)
                    note = "Arbeit"

            weekly_totals[(iso_year, iso_week)]["work"] += work_minutes
            weekly_totals[(iso_year, iso_week)]["pause"] += pause_minutes
            weekly_totals[(iso_year, iso_week)]["total"] += total_minutes

            rows.append({
                "type": "day",
                "date": session.date.strftime('%Y-%m-%d'),
                "note": note,
                "work": format_minutes(work_minutes),
                "pause": format_minutes(pause_minutes),
                "total": format_minutes(total_minutes)
            })

        detailed_rows = []
        current_week = None
        for row in rows:
            row_date = datetime.strptime(row["date"], "%Y-%m-%d").date()
            iso_year, iso_week, _ = row_date.isocalendar()
            if current_week is None:
                current_week = (iso_year, iso_week)
            if (iso_year, iso_week) != current_week:
                totals = weekly_totals[current_week]
                week_start = date.fromisocalendar(current_week[0], current_week[1], 1)
                week_end = week_start + timedelta(days=6)
                detailed_rows.append({
                    "type": "week_total",
                    "date": f"{current_week[0]}-W{current_week[1]:02d}",
                    "note": f"Wochensumme ({week_start:%Y-%m-%d} - {week_end:%Y-%m-%d})",
                    "work": format_minutes(totals["work"]),
                    "pause": format_minutes(totals["pause"]),
                    "total": format_minutes(totals["total"])
                })
                current_week = (iso_year, iso_week)
            detailed_rows.append(row)

        if current_week is not None:
            totals = weekly_totals[current_week]
            week_start = date.fromisocalendar(current_week[0], current_week[1], 1)
            week_end = week_start + timedelta(days=6)
            detailed_rows.append({
                "type": "week_total",
                "date": f"{current_week[0]}-W{current_week[1]:02d}",
                "note": f"Wochensumme ({week_start:%Y-%m-%d} - {week_end:%Y-%m-%d})",
                "work": format_minutes(totals["work"]),
                "pause": format_minutes(totals["pause"]),
                "total": format_minutes(totals["total"])
            })

        add_time_report_table(pdf, detailed_rows)

        filename = f"time_{start_date.isoformat()}_{end_date.isoformat()}.pdf"

    pdf_bytes = pdf.output()
    pdf_stream = io.BytesIO(pdf_bytes if isinstance(pdf_bytes, (bytes, bytearray)) else pdf_bytes.encode("latin-1"))
    pdf_stream.seek(0)
    return send_file(pdf_stream, mimetype='application/pdf', as_attachment=True, download_name=filename)

if __name__ == '__main__':
    app.run(debug=True)
