from flask import Flask, render_template, request, jsonify, redirect, url_for, send_file, make_response
from models import db, DailySession, Task, Pause, FocusSession, FocusPause
from datetime import datetime, timedelta, date
from fpdf import FPDF
from fpdf.enums import XPos, YPos
import textwrap
import io
import os
from sqlalchemy import text
from translations import TRANSLATIONS

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)

SNAPSHOTS = {}

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

def get_locale():
    return request.cookies.get('lang', 'en')

@app.context_processor
def inject_translations():
    lang = get_locale()
    if lang not in TRANSLATIONS:
        lang = 'en'
    return dict(lang=lang, t=TRANSLATIONS[lang], all_translations=TRANSLATIONS)

@app.route('/set_language/<lang>')
def set_language(lang):
    if lang not in TRANSLATIONS:
        lang = 'en'
    response = redirect(request.referrer or url_for('index'))
    response.set_cookie('lang', lang, max_age=31536000) # 1 year
    return response

@app.route('/')
def index():
    sessions = DailySession.query.order_by(DailySession.date.desc()).all()
    response = make_response(render_template('metrics.html', sessions=sessions))
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    return response

@app.route('/new')
def new_day_form():
    return render_template('start_day.html') # Old index content

@app.route('/sw.js')
def serve_sw():
    return send_file('static/sw.js', mimetype='application/javascript')

@app.route('/manifest.json')
def serve_manifest():
    return send_file('static/manifest.json', mimetype='application/json')

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
        lang = get_locale()
        trans = TRANSLATIONS.get(lang, TRANSLATIONS['en'])
        goal = trans['full_days'][session_date.weekday()]
        
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
    session_obj = DailySession.query.get_or_404(session_id)
    
    # Create a snapshot of the session state for rollback on every visit
    SNAPSHOTS[session_id] = {
        'goal': session_obj.goal,
        'status': session_obj.status,
        'start_time': session_obj.start_time.isoformat() if session_obj.start_time else None,
        'end_time': session_obj.end_time.isoformat() if session_obj.end_time else None,
        'tasks': [{'description': t.description, 'is_completed': t.is_completed} for t in session_obj.tasks],
        'pauses': [{'start_time': p.start_time.isoformat() if p.start_time else None, 
                    'end_time': p.end_time.isoformat() if p.end_time else None} for p in session_obj.pauses]
    }
        
    return render_template('dashboard.html', session=session_obj)

@app.route('/focus/task/<int:task_id>')
def focus_task(task_id):
    task = db.session.get(Task, task_id)
    if not task:
        return redirect(url_for('index'))
    session = db.session.get(DailySession, task.session_id)
    focus_sessions = FocusSession.query.filter_by(task_id=task_id).order_by(FocusSession.start_time.desc()).all()
    focus_rows = []
    active_focus = None
    for fs in focus_sessions:
        pause_seconds = 0
        active_pause = False
        for p in fs.pauses:
            if p.start_time and p.end_time:
                pause_seconds += int((p.end_time - p.start_time).total_seconds())
            elif p.start_time:
                pause_seconds += int((datetime.now() - p.start_time).total_seconds())
                active_pause = True

        if fs.start_time and fs.end_time:
            total_seconds = int((fs.end_time - fs.start_time).total_seconds())
        elif fs.start_time:
            total_seconds = int((datetime.now() - fs.start_time).total_seconds())
        else:
            total_seconds = 0
        work_seconds = max(total_seconds - pause_seconds, 0)
        if fs.end_time is None and active_focus is None:
            active_focus = {
                "id": fs.id,
                "start_iso": fs.start_time.isoformat() if fs.start_time else "",
                "pomodoro": fs.pomodoro_mode or "",
                "note": fs.note or "",
                "pause_seconds": pause_seconds,
                "active_pause": active_pause
            }
        focus_rows.append({
            "id": fs.id,
            "start": fs.start_time,
            "end": fs.end_time,
            "pomodoro": fs.pomodoro_mode or "",
            "note": fs.note or "",
            "start_date": fs.start_time.strftime('%Y-%m-%d') if fs.start_time else "",
            "start_time": fs.start_time.strftime('%H:%M') if fs.start_time else "",
            "end_date": fs.end_time.strftime('%Y-%m-%d') if fs.end_time else "",
            "end_time": fs.end_time.strftime('%H:%M') if fs.end_time else "",
            "pauses": [{
                "id": p.id,
                "duration": format_seconds(
                    int((p.end_time - p.start_time).total_seconds()) if p.start_time and p.end_time else 0
                )
            } for p in fs.pauses],
            "work": format_seconds(work_seconds),
            "pause": format_seconds(pause_seconds),
            "pause_total": format_seconds(pause_seconds),
            "total": format_seconds(total_seconds),
            "active": fs.end_time is None,
            "active_pause": active_pause
        })
    return render_template('focus.html', session=session, task=task, focus_rows=focus_rows, mode="task", active_focus=active_focus)

@app.route('/focus/day/<int:session_id>')
def focus_day(session_id):
    session = DailySession.query.get_or_404(session_id)
    focus_sessions = FocusSession.query.filter_by(session_id=session_id, task_id=None).order_by(FocusSession.start_time.desc()).all()
    focus_rows = []
    active_focus = None
    for fs in focus_sessions:
        pause_seconds = 0
        active_pause = False
        for p in fs.pauses:
            if p.start_time and p.end_time:
                pause_seconds += int((p.end_time - p.start_time).total_seconds())
            elif p.start_time:
                pause_seconds += int((datetime.now() - p.start_time).total_seconds())
                active_pause = True

        if fs.start_time and fs.end_time:
            total_seconds = int((fs.end_time - fs.start_time).total_seconds())
        elif fs.start_time:
            total_seconds = int((datetime.now() - fs.start_time).total_seconds())
        else:
            total_seconds = 0
        work_seconds = max(total_seconds - pause_seconds, 0)
        if fs.end_time is None and active_focus is None:
            active_focus = {
                "id": fs.id,
                "start_iso": fs.start_time.isoformat() if fs.start_time else "",
                "pomodoro": fs.pomodoro_mode or "",
                "note": fs.note or "",
                "pause_seconds": pause_seconds,
                "active_pause": active_pause
            }
        focus_rows.append({
            "id": fs.id,
            "start": fs.start_time,
            "end": fs.end_time,
            "pomodoro": fs.pomodoro_mode or "",
            "note": fs.note or "",
            "start_date": fs.start_time.strftime('%Y-%m-%d') if fs.start_time else "",
            "start_time": fs.start_time.strftime('%H:%M') if fs.start_time else "",
            "end_date": fs.end_time.strftime('%Y-%m-%d') if fs.end_time else "",
            "end_time": fs.end_time.strftime('%H:%M') if fs.end_time else "",
            "pauses": [{
                "id": p.id,
                "duration": format_seconds(
                    int((p.end_time - p.start_time).total_seconds()) if p.start_time and p.end_time else 0
                )
            } for p in fs.pauses],
            "work": format_seconds(work_seconds),
            "pause": format_seconds(pause_seconds),
            "pause_total": format_seconds(pause_seconds),
            "total": format_seconds(total_seconds),
            "active": fs.end_time is None,
            "active_pause": active_pause
        })
    return render_template('focus.html', session=session, task=None, focus_rows=focus_rows, mode="day", active_focus=active_focus)

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

@app.route('/api/focus/start', methods=['POST'])
def start_focus():
    data = request.json
    session_id = data.get('session_id')
    task_id = data.get('task_id')
    pomodoro_mode = data.get('pomodoro_mode')
    note = data.get('note')

    if not session_id:
        return jsonify({'error': 'Missing session_id'}), 400

    active = FocusSession.query.filter_by(session_id=session_id, task_id=task_id, end_time=None).first()
    if active:
        return jsonify({'error': 'Focus session already active', 'focus_session_id': active.id}), 409

    focus = FocusSession(session_id=session_id, task_id=task_id, pomodoro_mode=pomodoro_mode, note=note)
    db.session.add(focus)
    db.session.commit()
    return jsonify({'status': 'success', 'focus_session_id': focus.id})

@app.route('/api/focus/stop', methods=['POST'])
def stop_focus():
    data = request.json
    focus_session_id = data.get('focus_session_id')

    focus = db.session.get(FocusSession, focus_session_id)
    if not focus:
        return jsonify({'error': 'Focus session not found'}), 404

    open_pause = FocusPause.query.filter_by(focus_session_id=focus.id, end_time=None).first()
    if open_pause:
        open_pause.end_time = datetime.now()

    focus.end_time = datetime.now()
    db.session.commit()
    return jsonify({'status': 'success'})

@app.route('/api/focus/pause/start', methods=['POST'])
def start_focus_pause():
    data = request.json
    focus_session_id = data.get('focus_session_id')
    focus = db.session.get(FocusSession, focus_session_id)
    if not focus:
        return jsonify({'error': 'Focus session not found'}), 404

    open_pause = FocusPause.query.filter_by(focus_session_id=focus.id, end_time=None).first()
    if open_pause:
        return jsonify({'error': 'Pause already active', 'pause_id': open_pause.id}), 409

    pause = FocusPause(focus_session_id=focus.id, start_time=datetime.now())
    db.session.add(pause)
    db.session.commit()
    return jsonify({'status': 'success', 'pause_id': pause.id})

@app.route('/api/focus/pause/end', methods=['POST'])
def end_focus_pause():
    data = request.json
    focus_session_id = data.get('focus_session_id')
    focus = db.session.get(FocusSession, focus_session_id)
    if not focus:
        return jsonify({'error': 'Focus session not found'}), 404

    open_pause = FocusPause.query.filter_by(focus_session_id=focus.id, end_time=None).first()
    if not open_pause:
        return jsonify({'error': 'No active pause'}), 404

    open_pause.end_time = datetime.now()
    db.session.commit()
    return jsonify({'status': 'success'})

@app.route('/api/focus/pause_total', methods=['POST'])
def update_focus_pause_total():
    data = request.json
    focus_session_id = data.get('focus_session_id')
    duration = data.get('duration')
    focus = db.session.get(FocusSession, focus_session_id)
    if not focus:
        return jsonify({'error': 'Focus session not found'}), 404

    seconds = parse_duration_to_seconds(duration)
    if seconds is None:
        return jsonify({'error': 'Invalid duration'}), 400

    # Replace pauses with a single aggregate pause
    for p in list(focus.pauses):
        db.session.delete(p)

    if seconds > 0:
        base_time = focus.start_time if focus.start_time else datetime.now()
        pause = FocusPause(focus_session_id=focus.id, start_time=base_time, end_time=base_time + timedelta(seconds=seconds))
        db.session.add(pause)

    db.session.commit()
    return jsonify({'status': 'success'})

@app.route('/api/focus/update', methods=['POST'])
def update_focus_session():
    data = request.json
    focus_session_id = data.get('focus_session_id')
    focus = db.session.get(FocusSession, focus_session_id)
    if not focus:
        return jsonify({'error': 'Focus session not found'}), 404

    start_date = data.get('start_date')
    start_time = data.get('start_time')
    end_date = data.get('end_date')
    end_time = data.get('end_time')
    note = data.get('note')
    pomodoro_mode = data.get('pomodoro_mode')

    if start_date and start_time:
        parsed = parse_local_datetime(start_date, start_time)
        if not parsed:
            return jsonify({'error': 'Invalid start time'}), 400
        focus.start_time = parsed
    if end_date and end_time:
        parsed = parse_local_datetime(end_date, end_time)
        if not parsed:
            return jsonify({'error': 'Invalid end time'}), 400
        focus.end_time = parsed
    if note is not None:
        focus.note = note.strip() if note else None
    if pomodoro_mode is not None:
        focus.pomodoro_mode = pomodoro_mode if pomodoro_mode != 'off' else None

    db.session.commit()
    return jsonify({'status': 'success'})

@app.route('/api/focus/pause/update', methods=['POST'])
def update_focus_pause():
    data = request.json
    pause_id = data.get('pause_id')
    pause = db.session.get(FocusPause, pause_id)
    if not pause:
        return jsonify({'error': 'Focus pause not found'}), 404

    duration = data.get('duration')
    seconds = parse_duration_to_seconds(duration)
    if seconds is None:
        return jsonify({'error': 'Invalid duration'}), 400

    focus = db.session.get(FocusSession, pause.focus_session_id)
    base_time = focus.start_time if focus and focus.start_time else datetime.now()
    pause.start_time = base_time
    pause.end_time = base_time + timedelta(seconds=seconds)

    db.session.commit()
    return jsonify({'status': 'success'})

@app.route('/api/focus/pause/delete', methods=['POST'])
def delete_focus_pause():
    data = request.json
    pause_id = data.get('pause_id')
    pause = db.session.get(FocusPause, pause_id)
    if not pause:
        return jsonify({'error': 'Focus pause not found'}), 404
    db.session.delete(pause)
    db.session.commit()
    return jsonify({'status': 'success'})

@app.route('/api/focus/delete', methods=['POST'])
def delete_focus_session():
    data = request.json
    focus_session_id = data.get('focus_session_id')
    focus = db.session.get(FocusSession, focus_session_id)
    if not focus:
        return jsonify({'error': 'Focus session not found'}), 404
    db.session.delete(focus)
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

@app.route('/api/session/rollback', methods=['POST'])
def rollback_session():
    data = request.json
    session_id = data.get('session_id')
    
    if not session_id or session_id not in SNAPSHOTS:
        return jsonify({'error': 'No snapshot found for this session'}), 404
        
    snapshot = SNAPSHOTS[session_id]
    session_obj = db.session.get(DailySession, session_id)
    
    if not session_obj:
        return jsonify({'error': 'Session not found'}), 404
        
    # Restore main fields
    session_obj.goal = snapshot['goal']
    session_obj.status = snapshot['status']
    session_obj.start_time = datetime.fromisoformat(snapshot['start_time']) if snapshot['start_time'] else None
    session_obj.end_time = datetime.fromisoformat(snapshot['end_time']) if snapshot['end_time'] else None
    
    # Restore tasks
    # Delete current tasks
    for task in list(session_obj.tasks):
        db.session.delete(task)
    # Re-add from snapshot
    for t_snap in snapshot['tasks']:
        new_task = Task(session_id=session_id, description=t_snap['description'], is_completed=t_snap['is_completed'])
        db.session.add(new_task)
        
    # Restore pauses
    # Delete current pauses
    for pause in list(session_obj.pauses):
        db.session.delete(pause)
    # Re-add from snapshot
    for p_snap in snapshot['pauses']:
        new_pause = Pause(session_id=session_id)
        if p_snap['start_time']:
            new_pause.start_time = datetime.fromisoformat(p_snap['start_time'])
        if p_snap['end_time']:
            new_pause.end_time = datetime.fromisoformat(p_snap['end_time'])
        db.session.add(new_pause)
        
    db.session.commit()
    
    # Optional: remove snapshot after rollback? 
    # Usually better to keep it in case they click it again before navigating away, 
    # but they are redirected to / anyway.
    del SNAPSHOTS[session_id]
    
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

def sum_focus_pause_minutes(pauses):
    total = 0
    for pause in pauses:
        if pause.start_time and pause.end_time:
            total += int((pause.end_time - pause.start_time).total_seconds() / 60)
    return total

def format_seconds(total_seconds):
    if total_seconds is None:
        return "--:--:--"
    total_seconds = max(0, int(total_seconds))
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    seconds = total_seconds % 60
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"

def parse_local_datetime(date_str, time_str):
    if not date_str or not time_str:
        return None
    try:
        return datetime.strptime(f"{date_str}T{time_str}", "%Y-%m-%dT%H:%M")
    except ValueError:
        return None

def parse_duration_to_seconds(value):
    if not value:
        return None
    parts = value.strip().split(":")
    try:
        if len(parts) == 1:
            minutes = int(parts[0])
            return minutes * 60
        if len(parts) == 2:
            minutes = int(parts[0])
            seconds = int(parts[1])
            return minutes * 60 + seconds
        if len(parts) == 3:
            hours = int(parts[0])
            minutes = int(parts[1])
            seconds = int(parts[2])
            return hours * 3600 + minutes * 60 + seconds
    except ValueError:
        return None
    return None

def add_time_report_table(pdf, rows, t):
    col_widths = [45, 65, 27, 27, 26]
    headers = [t['date'], t['note'], t['work'], t['pause'], t['total']]
    
    def render_header():
        pdf.set_fill_color(30, 41, 59) # Slate 800
        pdf.set_text_color(255, 255, 255)
        pdf.set_font("Helvetica", style="B", size=10)
        for idx, header in enumerate(headers):
            pdf.cell(col_widths[idx], 10, header, border=0, align="C", fill=True)
        pdf.ln(10)
        pdf.set_text_color(0, 0, 0)

    if not rows:
        pdf.set_font("Helvetica", size=10)
        pdf.cell(sum(col_widths), 10, "No sessions in selected period.", border=1, align="L")
        pdf.ln(10)
        return

    current_month = None
    render_header()

    for idx, row in enumerate(rows):
        # Month header logic
        if row.get("type") == "day":
            row_date = datetime.strptime(row["date_raw"], "%Y-%m-%d")
            row_month = row_date.strftime("%Y-%m")
            if row_month != current_month:
                current_month = row_month
                pdf.ln(2)
                pdf.set_fill_color(241, 245, 249) # Slate 100
                pdf.set_font("Helvetica", style="B", size=11)
                month_name = t['full_months'][row_date.month - 1]
                pdf.cell(sum(col_widths), 10, f"{month_name} {row_date.year}", border="B", align="L", fill=True)
                pdf.ln(10)

        # Style based on type
        if row.get("type") == "week_total":
            pdf.set_fill_color(248, 250, 252) # Slate 50
            pdf.set_font("Helvetica", style="B", size=9)
            border = 1
        else:
            pdf.set_font("Helvetica", size=10)
            if idx % 2 == 0:
                pdf.set_fill_color(255, 255, 255)
            else:
                pdf.set_fill_color(252, 252, 252)
            border = "B"

        # Background color for status
        if row.get("status") == "sick":
            pdf.set_fill_color(245, 243, 255) # Light Violet
        elif row.get("status") == "vacation":
            pdf.set_fill_color(255, 247, 237) # Light Orange

        pdf.cell(col_widths[0], 9, row["date"], border=border, align="L", fill=True)
        pdf.cell(col_widths[1], 9, row["note"], border=border, align="L", fill=True)
        pdf.cell(col_widths[2], 9, row["work"], border=border, align="R", fill=True)
        pdf.cell(col_widths[3], 9, row["pause"], border=border, align="R", fill=True)
        pdf.cell(col_widths[4], 9, row["total"], border=border, align="R", fill=True)
        pdf.ln(9)

        if pdf.get_y() > 260:
            pdf.add_page()
            render_header()

def add_task_report_table(pdf, task_rows, t):
    col_date = 45
    col_tasks = 145
    line_height = 6

    def render_header():
        pdf.set_fill_color(30, 41, 59)
        pdf.set_text_color(255, 255, 255)
        pdf.set_font("Helvetica", style="B", size=10)
        pdf.cell(col_date, 10, t['date'], border=0, align="C", fill=True)
        pdf.cell(col_tasks, 10, t['tasks'], border=0, align="C", fill=True)
        pdf.ln(10)
        pdf.set_text_color(0, 0, 0)

    render_header()

    if not task_rows:
        pdf.set_font("Helvetica", size=10)
        pdf.cell(col_date + col_tasks, 10, "No sessions in selected period.", border=1, align="L")
        pdf.ln(10)
        return

    current_month = None

    for idx, row in enumerate(task_rows):
        row_date = datetime.strptime(row["date_raw"], "%Y-%m-%d")
        row_month = row_date.strftime("%Y-%m")
        if row_month != current_month:
            current_month = row_month
            pdf.ln(2)
            pdf.set_fill_color(241, 245, 249)
            pdf.set_font("Helvetica", style="B", size=11)
            month_name = t['full_months'][row_date.month - 1]
            pdf.cell(col_date + col_tasks, 10, f"{month_name} {row_date.year}", border="B", align="L", fill=True)
            pdf.ln(10)

        tasks_text = row["tasks"] if row["tasks"] else "-"
        tasks_lines = textwrap.wrap(tasks_text, width=80) or ["-"]
        row_height = max(line_height * len(tasks_lines), 9)

        if pdf.get_y() + row_height > 270:
            pdf.add_page()
            render_header()

        if row.get("status") == "sick":
            pdf.set_fill_color(245, 243, 255)
        elif row.get("status") == "vacation":
            pdf.set_fill_color(255, 247, 237)
        else:
            pdf.set_fill_color(255, 255, 255) if idx % 2 == 0 else pdf.set_fill_color(252, 252, 252)

        x, y = pdf.get_x(), pdf.get_y()
        pdf.set_font("Helvetica", size=10)
        pdf.multi_cell(col_date, row_height, row["date"], border="B", align="L", fill=True)
        pdf.set_xy(x + col_date, y)
        pdf.multi_cell(col_tasks, line_height if len(tasks_lines) > 1 else row_height, "\n".join(tasks_lines), border="B", align="L", fill=True)
        pdf.set_xy(x, y + row_height)

@app.route('/reports')
def reports():
    import calendar
    today = datetime.now().date()
    # Default to current month
    default_start = today.replace(day=1)
    last_day = calendar.monthrange(today.year, today.month)[1]
    default_end = today.replace(day=last_day)
    
    return render_template('reports.html',
                           default_start=default_start.isoformat(),
                           default_end=default_end.isoformat())

@app.route('/reports/pdf', methods=['POST'])
def reports_pdf():
    report_type = request.form.get('report_type')
    start_str = request.form.get('date_start')
    end_str = request.form.get('date_end')
    reporter_name = request.form.get('reporter_name', 'Felix Walger')

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
    pdf.cell(0, 8, reporter_name, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(2)

    lang = get_locale()
    trans = TRANSLATIONS.get(lang, TRANSLATIONS['en'])

    if report_type == "tasks":
        pdf.set_font("Helvetica", style="B", size=16)
        pdf.cell(0, 10, trans['task_report'], new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.set_font("Helvetica", size=10)
        pdf.set_text_color(100, 100, 100)
        pdf.cell(0, 6, f"{trans['period']}: {date_range_label}", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.ln(6)
        pdf.set_text_color(0, 0, 0)

        task_rows = []
        for session in sessions:
            if session.status == "sick":
                task_texts = [trans['krank']]
            elif session.status == "vacation":
                task_texts = [trans['urlaub']]
            else:
                task_texts = [task.description for task in session.tasks]
            
            day_name = trans['days'][session.date.strftime('%a')]
            date_display = f"{day_name} {session.date.strftime('%d.%m.%Y')}"
            
            task_rows.append({
                "date": date_display,
                "date_raw": session.date.strftime('%Y-%m-%d'),
                "status": session.status,
                "tasks": "; ".join(task_texts) if task_texts else "-"
            })

        add_task_report_table(pdf, task_rows, trans)
        filename = f"tasks_{start_date.isoformat()}_{end_date.isoformat()}.pdf"

    else:
        pdf.set_font("Helvetica", style="B", size=16)
        pdf.cell(0, 10, trans['time_report'], new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.set_font("Helvetica", size=10)
        pdf.set_text_color(100, 100, 100)
        pdf.cell(0, 6, f"{trans['period']}: {date_range_label}", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.cell(0, 6, trans['includes_pauses'], new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.ln(6)
        pdf.set_text_color(0, 0, 0)

        rows = []
        weekly_totals = {}

        for session in sessions:
            iso_year, iso_week, _ = session.date.isocalendar()
            weekly_totals.setdefault((iso_year, iso_week), {"work": 0, "pause": 0, "total": 0})

            if session.status in ("sick", "vacation"):
                work_minutes = 7 * 60 + 50
                pause_minutes = 30
                total_minutes = work_minutes + pause_minutes
                note = trans['krank'] if session.status == "sick" else trans['urlaub']
            else:
                if not session.start_time or not session.end_time:
                    work_minutes = 0
                    pause_minutes = 0
                    total_minutes = 0
                    note = trans['unfinished']
                else:
                    total_minutes = int((session.end_time - session.start_time).total_seconds() / 60)
                    pause_minutes = sum_pause_minutes(session.pauses)
                    work_minutes = max(total_minutes - pause_minutes, 0)
                    note = trans['work']

            weekly_totals[(iso_year, iso_week)]["work"] += work_minutes
            weekly_totals[(iso_year, iso_week)]["pause"] += pause_minutes
            weekly_totals[(iso_year, iso_week)]["total"] += total_minutes

            day_name = trans['days'][session.date.strftime('%a')]
            date_display = f"{day_name} {session.date.strftime('%d.%m.%Y')}"

            rows.append({
                "type": "day",
                "date": date_display,
                "date_raw": session.date.strftime('%Y-%m-%d'),
                "status": session.status,
                "note": note,
                "work": format_minutes(work_minutes),
                "pause": format_minutes(pause_minutes),
                "total": format_minutes(total_minutes)
            })

        detailed_rows = []
        current_week = None
        for row in rows:
            row_date = datetime.strptime(row["date_raw"], "%Y-%m-%d").date()
            iso_year, iso_week, _ = row_date.isocalendar()
            if current_week is None:
                current_week = (iso_year, iso_week)
            if (iso_year, iso_week) != current_week:
                totals = weekly_totals[current_week]
                week_start = date.fromisocalendar(current_week[0], current_week[1], 1)
                week_end = week_start + timedelta(days=6)
                detailed_rows.append({
                    "type": "week_total",
                    "date": f"W{current_week[1]:02d} Total",
                    "note": f"({week_start:%d.%m} - {week_end:%d.%m})",
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
                "date": f"W{current_week[1]:02d} Total",
                "note": f"({week_start:%d.%m} - {week_end:%d.%m})",
                "work": format_minutes(totals["work"]),
                "pause": format_minutes(totals["pause"]),
                "total": format_minutes(totals["total"])
            })

        add_time_report_table(pdf, detailed_rows, trans)
        filename = f"time_{start_date.isoformat()}_{end_date.isoformat()}.pdf"

    pdf_bytes = pdf.output()
    pdf_stream = io.BytesIO(pdf_bytes if isinstance(pdf_bytes, (bytes, bytearray)) else pdf_bytes.encode("latin-1"))
    pdf_stream.seek(0)
    return send_file(pdf_stream, mimetype='application/pdf', as_attachment=True, download_name=filename)

if __name__ == '__main__':
    app.run(debug=True)
