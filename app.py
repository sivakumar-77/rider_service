from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from apscheduler.schedulers.background import BackgroundScheduler
import atexit

db = SQLAlchemy()
scheduler = None

def create_app(config_class='config.Config'):
    app = Flask(__name__)
    app.config.from_object(config_class)
    
    db.init_app(app)
    
    with app.app_context():
        from allocation import allocate_drivers
        
        global scheduler
        if not scheduler:
            scheduler = BackgroundScheduler()
            scheduler.add_job(func=lambda: allocate_drivers(), trigger="interval", seconds=10)
            scheduler.start()
            # Shut down the scheduler when exiting the app
            atexit.register(lambda: scheduler.shutdown())
    
    return app
