from flask import Flask, render_template, request, jsonify, redirect, url_for
from models import db, DailySession, Task, Pause
from datetime import datetime
import os

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)

with app.app_context():
    db.create_all()

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
    
    task = Task.query.get(task_id)
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
    
    task = Task.query.get(task_id)
    if not task:
        return jsonify({'error': 'Task not found'}), 404
        
    task.description = description.strip() if description else task.description
    db.session.commit()
    return jsonify({'status': 'success'})

@app.route('/api/task/delete', methods=['POST'])
def delete_task():
    data = request.json
    task_id = data.get('task_id')
    
    task = Task.query.get(task_id)
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
    
    session = DailySession.query.get(session_id)
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
    
    pause = Pause.query.get(pause_id)
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
    
    pause = Pause.query.get(pause_id)
    if not pause:
        return jsonify({'error': 'Pause not found'}), 404
    
    db.session.delete(pause)
    db.session.commit()
    return jsonify({'status': 'success'})





@app.route('/api/session/delete', methods=['POST'])
def delete_session():
    data = request.json
    session_id = data.get('session_id')
    
    session = DailySession.query.get(session_id)
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
    
    session = DailySession.query.get(session_id)
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
    
    session = DailySession.query.get(session_id)
    if not session:
        return jsonify({'error': 'Session not found'}), 404
        
    session.goal = new_goal
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
            'start_time': s.start_time.isoformat() if s.start_time else None,
            'end_time': s.end_time.isoformat() if s.end_time else None,
            'pauses': pauses_data
        })
    return jsonify(data)

if __name__ == '__main__':
    app.run(debug=True)
