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

    tasks = db.relationship('Task', backref='session', lazy=True, cascade='all, delete-orphan')
    pauses = db.relationship('Pause', backref='session', lazy=True, cascade='all, delete-orphan', order_by='Pause.start_time')

class Task(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.Integer, db.ForeignKey('daily_session.id'), nullable=False)
    description = db.Column(db.String(200), nullable=False)
    is_completed = db.Column(db.Boolean, default=False)

class Pause(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.Integer, db.ForeignKey('daily_session.id'), nullable=False)
    start_time = db.Column(db.DateTime, nullable=True)
    end_time = db.Column(db.DateTime, nullable=True)
