from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()

class DailySession(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date, nullable=False, default=datetime.now)
    goal = db.Column(db.String(200), nullable=False)
    status = db.Column(db.String(20), nullable=False, default="work")
    start_time = db.Column(db.DateTime, default=datetime.now)
    end_time = db.Column(db.DateTime, nullable=True)

    tasks = db.relationship('Task', backref='session', lazy=True, cascade='all, delete-orphan', order_by='Task.order')
    pauses = db.relationship('Pause', backref='session', lazy=True, cascade='all, delete-orphan', order_by='Pause.start_time')

task_tags = db.Table('task_tags',
    db.Column('task_id', db.Integer, db.ForeignKey('task.id'), primary_key=True),
    db.Column('tag_id', db.Integer, db.ForeignKey('tag.id'), primary_key=True)
)

class Tag(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)
    color = db.Column(db.String(7), default="#38bdf8") # Hex color

class SuperTag(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    color = db.Column(db.String(7), unique=True, nullable=False) # Hex color group
    name = db.Column(db.String(50), nullable=False)

class Task(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.Integer, db.ForeignKey('daily_session.id'), nullable=False)
    description = db.Column(db.String(200), nullable=False)
    is_completed = db.Column(db.Boolean, default=False)
    # tag column is deprecated but kept for safety until full migration
    tag = db.Column(db.String(50), nullable=True) 
    order = db.Column(db.Integer, default=0)
    
    tags = db.relationship('Tag', secondary=task_tags, lazy='subquery',
        backref=db.backref('tasks', lazy=True))

class Pause(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.Integer, db.ForeignKey('daily_session.id'), nullable=False)
    start_time = db.Column(db.DateTime, nullable=True)
    end_time = db.Column(db.DateTime, nullable=True)

class FocusSession(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.Integer, db.ForeignKey('daily_session.id'), nullable=False)
    task_id = db.Column(db.Integer, db.ForeignKey('task.id'), nullable=False)
    start_time = db.Column(db.DateTime, default=datetime.now)
    end_time = db.Column(db.DateTime, nullable=True)
    pomodoro_mode = db.Column(db.String(10), nullable=True)  # "50/10" or "75/15"
    note = db.Column(db.String(200), nullable=True)

    pauses = db.relationship('FocusPause', backref='focus_session', lazy=True, cascade='all, delete-orphan', order_by='FocusPause.start_time')

class FocusPause(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    focus_session_id = db.Column(db.Integer, db.ForeignKey('focus_session.id'), nullable=False)
    start_time = db.Column(db.DateTime, nullable=True)
    end_time = db.Column(db.DateTime, nullable=True)
