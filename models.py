from datetime import datetime
from app import db

class Rider(db.Model):
    __tablename__ = 'riders'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100))
    latitude = db.Column(db.Float)
    longitude = db.Column(db.Float)
    rides = db.relationship('Ride', backref='rider', lazy=True)

class Driver(db.Model):
    __tablename__ = 'drivers'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100))
    latitude = db.Column(db.Float)
    longitude = db.Column(db.Float)
    available = db.Column(db.Boolean, default=True)
    active_ride_id = db.Column(db.Integer, nullable=True)
    cancelled_rides_count = db.Column(db.Integer, default=0)
    last_ride_end_time = db.Column(db.DateTime)

class Ride(db.Model):
    __tablename__ = 'rides'
    id = db.Column(db.Integer, primary_key=True)
    rider_id = db.Column(db.Integer, db.ForeignKey('riders.id'), nullable=False)
    driver_id = db.Column(db.Integer, db.ForeignKey('drivers.id'), nullable=True)
    pickup_lat = db.Column(db.Float)
    pickup_long = db.Column(db.Float)
    drop_lat = db.Column(db.Float)
    drop_long = db.Column(db.Float)
    status = db.Column(db.String(50), default="create_ride")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    driver_assigned_at = db.Column(db.DateTime)
    driver_at_location_at = db.Column(db.DateTime)
    start_ride_at = db.Column(db.DateTime)
    end_ride_at = db.Column(db.DateTime)
    distance_km = db.Column(db.Float, default=0.0)  # Added to store ride distance
    fare = db.Column(db.Float, default=0.0)

class PricingConfig(db.Model):
    __tablename__ = 'pricing_config'
    key = db.Column(db.String(50), primary_key=True)
    value = db.Column(db.String(50), nullable=False)
