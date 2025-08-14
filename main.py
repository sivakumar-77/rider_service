"""Ride Service Mini-Uber Backend

A backend simulation of a ride-hailing platform built with a clean and modular architecture.
This application models a realistic ride flow and pricing mechanism with time and distance tracking.

Commands:
  - Initialize DB (creates tables):
      python main.py init_db

  - Run simulation (generates riders/drivers and simulates 2 days):
      python main.py simulate

  - Run server (Flask admin endpoints to inspect DB):
      python main.py runserver

Ride Lifecycle:
  - create_ride: A ride request is created with pickup and drop coordinates
  - driver_assigned: A nearby driver is automatically assigned
  - driver_at_location: Driver has reached the pickup location
  - start_ride: Ride begins
  - end_ride: Ride ends and fare is computed
"""

import os
import sys
import time
import random
import logging
from datetime import datetime, timedelta
from flask import Flask, jsonify, request
from faker import Faker
from utils import haversine

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Configuration constants
CITY_CENTER = (12.9716, 77.5946)  # Bangalore coordinates
CITY_RADIUS_KM = 20
NUM_RIDERS = 10
NUM_DRIVERS = 15
SIM_DAYS = 2
AVG_DRIVER_SPEED_KMH = 30.0  # used to simulate travel times

# Initialize faker for generating random names
faker = Faker()

from app import create_app, db
from models import Rider, Driver, Ride, PricingConfig
from pricing import calculate_fare
from allocation import allocate_drivers

# Create Flask application
app = create_app()

# ---------------- HELPERS ----------------
def random_point_within_km(center, radius_km):
    """Generate a random point within a given radius from a center point"""
    import math
    # Approximate random point within radius using simple offset
    # 1 deg lat ~ 111 km; 1 deg lon ~ 111 km * cos(lat)
    r = random.random()**0.5 * radius_km
    theta = random.random() * 2 * math.pi
    dx = r * math.cos(theta)
    dy = r * math.sin(theta)
    dlat = dy / 111.0
    dlng = dx / (111.0 * math.cos(math.radians(center[0])))
    return (center[0] + dlat, center[1] + dlng)

# ---------------- SIMULATION FUNCTIONS ----------------
def seed_pricing():
    """Initialize pricing configuration in the database"""
    with app.app_context():
        # Check if pricing config already exists
        if PricingConfig.query.count() == 0:
            rates = {
                "base_fare": 20,
                "rate_per_km": 10,
                "rate_per_minute": 2,
                "waiting_charge_per_minute": 1
            }
            for k, v in rates.items():
                db.session.add(PricingConfig(key=k, value=str(v)))
            db.session.commit()
            logger.info("Pricing configuration seeded")
        else:
            logger.info("Pricing configuration already exists")

def seed_users():
    """Create random riders and drivers in the database"""
    with app.app_context():
        # Check if users already exist
        if Rider.query.count() > 0 or Driver.query.count() > 0:
            logger.info("Users already exist in the database")
            return
            
        # Create 10 riders
        for i in range(NUM_RIDERS):
            lat, lng = random_point_within_km(CITY_CENTER, CITY_RADIUS_KM)
            r = Rider(name=f"Rider{i+1}", latitude=lat, longitude=lng)
            db.session.add(r)

        # Create 15 drivers
        for i in range(NUM_DRIVERS):
            lat, lng = random_point_within_km(CITY_CENTER, CITY_RADIUS_KM)
            d = Driver(name=f"Driver{i+1}", latitude=lat, longitude=lng, available=True)
            db.session.add(d)
            
        db.session.commit()
        logger.info(f"Created {NUM_RIDERS} riders and {NUM_DRIVERS} drivers")

def simulate_ride_flow(ride):
    """Simulate the lifecycle of a ride from driver assignment to completion"""
    logger.info(f"===== STARTING RIDE FLOW SIMULATION FOR RIDE {ride.id} =====")
    logger.info(f"Ride {ride.id} - Initial state: {ride.status}, Driver: {ride.driver_id}, Rider: {ride.rider_id}")
    logger.info(f"Ride {ride.id} - Pickup: ({ride.pickup_lat:.4f}, {ride.pickup_long:.4f}), Drop: ({ride.drop_lat:.4f}, {ride.drop_long:.4f})")
    
    # Simulate driver reaching pickup location (2-5 minutes)
    driver_travel_minutes = random.randint(2, 5)
    ride.driver_at_location_at = ride.driver_assigned_at + timedelta(minutes=driver_travel_minutes)
    ride.status = "driver_at_location"
    db.session.commit()
    logger.info(f"Ride {ride.id} - DRIVER_AT_LOCATION: Driver {ride.driver_id} reached pickup location after {driver_travel_minutes} minutes")

    # Simulate waiting time before starting ride (1-3 minutes)
    waiting_minutes = random.randint(1, 3)
    ride.start_ride_at = ride.driver_at_location_at + timedelta(minutes=waiting_minutes)
    ride.status = "start_ride"
    db.session.commit()
    logger.info(f"Ride {ride.id} - START_RIDE: Ride started after {waiting_minutes} minutes of waiting time")

    # Calculate distance if not already set
    if not ride.distance_km or ride.distance_km == 0:
        # For simulation, generate a random distance between 3-15 km
        ride.distance_km = round(random.uniform(3, 15), 2)
        logger.info(f"Ride {ride.id} - Generated random distance: {ride.distance_km} km")
    else:
        logger.info(f"Ride {ride.id} - Using existing distance: {ride.distance_km} km")
    
    # Simulate ride duration based on distance and average speed
    duration_hours = ride.distance_km / AVG_DRIVER_SPEED_KMH
    duration_minutes = duration_hours * 60
    ride.end_ride_at = ride.start_ride_at + timedelta(hours=duration_hours)
    ride.status = "end_ride"
    logger.info(f"Ride {ride.id} - END_RIDE: Ride completed after {duration_minutes:.1f} minutes at {AVG_DRIVER_SPEED_KMH} km/h")
    
    # Calculate fare
    original_fare = ride.fare
    calculate_fare(ride)
    logger.info(f"Ride {ride.id} - Fare calculated: ${ride.fare:.2f}")
    
    # Log fare breakdown if available
    if hasattr(ride, 'base_fare') and hasattr(ride, 'distance_fare') and hasattr(ride, 'time_fare') and hasattr(ride, 'waiting_fare'):
        logger.info(f"Ride {ride.id} - Fare breakdown: Base=${ride.base_fare:.2f}, Distance=${ride.distance_fare:.2f}, Time=${ride.time_fare:.2f}, Waiting=${ride.waiting_fare:.2f}")
    
    # Update driver status
    driver = Driver.query.get(ride.driver_id)
    if driver:
        driver.available = True
        driver.active_ride_id = None
        driver.last_ride_end_time = ride.end_ride_at
        logger.info(f"Ride {ride.id} - Updated driver {driver.id} status: available=True, active_ride_id=None")
    else:
        logger.warning(f"Ride {ride.id} - Could not find driver {ride.driver_id} to update status")
    
    db.session.commit()
    
    # Calculate total ride time
    if ride.driver_assigned_at and ride.end_ride_at:
        total_minutes = (ride.end_ride_at - ride.driver_assigned_at).total_seconds() / 60
        logger.info(f"Ride {ride.id} - COMPLETED: Total ride time from assignment to completion: {total_minutes:.1f} minutes")
    
    logger.info(f"===== COMPLETED RIDE FLOW SIMULATION FOR RIDE {ride.id} =====\n")
    return ride

# ---------------- SIMULATION FUNCTIONS ----------------
def generate_rides(days=SIM_DAYS):
    """Generate random rides for the specified number of days"""
    with app.app_context():
        logger.info("\n========== STARTING RIDE GENERATION ==========\n")
        
        riders = Rider.query.all()
        logger.info(f"Found {len(riders)} riders for ride generation")
        
        total_rides_generated = 0
        rides_by_day = {}
        
        for day in range(days):
            day_rides = 0
            logger.info(f"\n----- GENERATING RIDES FOR DAY {day+1} -----")
            
            for rider_index, rider in enumerate(riders, 1):
                # Each rider generates 1-2 ride requests per day
                num_requests = random.randint(1, 2)
                
                for req in range(num_requests):
                    # Generate random pickup and drop locations
                    pickup = random_point_within_km((rider.latitude, rider.longitude), 5)
                    drop = random_point_within_km((rider.latitude, rider.longitude), 10)
                    
                    # Calculate straight-line distance between pickup and drop
                    distance = haversine(pickup[0], pickup[1], drop[0], drop[1])
                    
                    # Create ride request with random time during the day
                    created_time = datetime.utcnow() + timedelta(days=day, seconds=random.randint(0, 86400))
                    
                    ride = Ride(
                        rider_id=rider.id,
                        pickup_lat=pickup[0],
                        pickup_long=pickup[1],
                        drop_lat=drop[0],
                        drop_long=drop[1],
                        status="create_ride",
                        created_at=created_time,
                        distance_km=round(distance, 2)  # Pre-calculate the distance
                    )
                    db.session.add(ride)
                    
                    day_rides += 1
                    
                    # Log every 10th ride for performance reasons
                    if (day_rides % 10 == 0) or (rider_index == len(riders) and req == num_requests - 1):
                        logger.info(f"Generated {day_rides} rides for day {day+1} so far")
            
            db.session.commit()
            total_rides_generated += day_rides
            rides_by_day[day+1] = day_rides
            logger.info(f"Completed: Generated {day_rides} rides for day {day+1}")
        
        # Log summary of ride generation
        logger.info("\n----- RIDE GENERATION SUMMARY -----")
        logger.info(f"Total rides generated: {total_rides_generated}")
        for day, count in rides_by_day.items():
            logger.info(f"Day {day}: {count} rides")
        logger.info(f"Average rides per day: {total_rides_generated / days:.1f}")
        logger.info("\n========== RIDE GENERATION COMPLETED ==========\n")

def simulate_rides():
    """Simulate the entire ride lifecycle for all rides"""
    with app.app_context():
        logger.info("\n========== STARTING RIDE SIMULATION ==========\n")
        
        # Count initial rides by status
        total_rides = Ride.query.count()
        unassigned_rides = Ride.query.filter_by(status="create_ride").count()
        logger.info(f"Initial state: {total_rides} total rides, {unassigned_rides} unassigned rides")
        
        # Run the allocator to assign drivers
        logger.info("\n----- PHASE 1: DRIVER ALLOCATION -----")
        start_time = time.time()
        allocate_drivers()
        allocation_time = time.time() - start_time
        logger.info(f"Driver allocation completed in {allocation_time:.2f} seconds")
        
        # Wait for a moment to let the allocation complete
        time.sleep(1)
        
        # Process assigned rides
        assigned_rides = Ride.query.filter_by(status="driver_assigned").all()
        unassigned_after = Ride.query.filter_by(status="create_ride").count()
        assignment_success_rate = (unassigned_rides - unassigned_after) / unassigned_rides * 100 if unassigned_rides > 0 else 0
        
        logger.info(f"\n----- PHASE 2: RIDE FLOW SIMULATION -----")
        logger.info(f"Driver assignment results: {len(assigned_rides)} rides assigned ({assignment_success_rate:.1f}% success rate)")
        logger.info(f"Processing {len(assigned_rides)} assigned rides")
        
        # Track simulation time
        start_time = time.time()
        for i, ride in enumerate(assigned_rides, 1):
            logger.info(f"Simulating ride {i} of {len(assigned_rides)} (ID: {ride.id})")
            simulate_ride_flow(ride)
        
        simulation_time = time.time() - start_time
        logger.info(f"\nRide flow simulation completed in {simulation_time:.2f} seconds")
        
        # Generate summary statistics
        logger.info("\n----- PHASE 3: GENERATING SUMMARY STATISTICS -----")
        generate_summary()
        
        logger.info("\n========== SIMULATION COMPLETED ==========\n")

def generate_summary():
    """Generate and display summary metrics for the simulation"""
    with app.app_context():
        from sqlalchemy import func
        
        total_rides = Ride.query.count()
        completed_rides = Ride.query.filter_by(status="end_ride").count()
        unmatched_rides = Ride.query.filter_by(status="create_ride").count()
        cancelled_rides = Ride.query.filter_by(status="cancelled").count() if hasattr(Ride, 'cancelled') else 0
        
        # Driver statistics
        driver_stats = db.session.query(
            Driver.id,
            Driver.name,
            func.count(Ride.id).label("rides_count"),
            func.sum(Ride.fare).label("total_fare"),
            func.avg(Ride.fare).label("avg_fare")
        ).outerjoin(
            Ride, (Ride.driver_id == Driver.id) & (Ride.status == "end_ride")
        ).group_by(Driver.id).order_by(Driver.id).all()
        
        # Calculate global average wait time and ride duration
        completed_rides_data = Ride.query.filter_by(status="end_ride").all()

        wait_times = []
        ride_durations = []

        for ride in completed_rides_data:
            if ride.driver_at_location_at and ride.start_ride_at:
                wait_time = (ride.start_ride_at - ride.driver_at_location_at).total_seconds() / 60
                wait_times.append(wait_time)
            
            if ride.start_ride_at and ride.end_ride_at:
                duration = (ride.end_ride_at - ride.start_ride_at).total_seconds() / 60
                ride_durations.append(duration)

        avg_wait_time = sum(wait_times) / len(wait_times) if wait_times else 0
        avg_ride_duration = sum(ride_durations) / len(ride_durations) if ride_durations else 0
                
        # Print summary
        logger.info("\n=== SIMULATION SUMMARY ===")
        logger.info(f"Total rides: {total_rides}")
        logger.info(f"Completed rides: {completed_rides}")
        logger.info(f"Unmatched rides: {unmatched_rides}")
        logger.info(f"Cancelled rides: {cancelled_rides}")
        logger.info(f"Average wait time: {avg_wait_time:.2f} minutes")
        logger.info(f"Average ride duration: {avg_ride_duration:.2f} minutes")
        
        logger.info("\n--- DRIVER STATISTICS ---")
        for stat in driver_stats:
            driver_id, name, rides_count, total_fare, avg_fare = stat
            driver = Driver.query.get(driver_id)
            cancelled = driver.cancelled_rides_count if driver else 0
            
            # Calculate per-driver averages
            driver_rides = Ride.query.filter_by(driver_id=driver_id, status="end_ride").all()
            driver_wait_times = [
                (r.start_ride_at - r.driver_at_location_at).total_seconds() / 60
                for r in driver_rides if r.driver_at_location_at and r.start_ride_at
            ]
            driver_durations = [
                (r.end_ride_at - r.start_ride_at).total_seconds() / 60
                for r in driver_rides if r.start_ride_at and r.end_ride_at
            ]
            
            avg_driver_wait = sum(driver_wait_times) / len(driver_wait_times) if driver_wait_times else 0
            avg_driver_duration = sum(driver_durations) / len(driver_durations) if driver_durations else 0
        
            if rides_count > 0:
                logger.info(f"Driver {driver_id} ({name}):")
                logger.info(f"  - Total rides: {rides_count}")
                logger.info(f"  - Total fare: ${total_fare or 0:.2f}")
                logger.info(f"  - Average fare per ride: ${avg_fare or 0:.2f}")
                logger.info(f"  - Cancelled rides: {cancelled}")
                logger.info(f"  - Average wait time: {avg_driver_wait:.2f} minutes")
                logger.info(f"  - Average ride duration: {avg_driver_duration:.2f} minutes")
        
        return {
            "total_rides": total_rides,
            "completed_rides": completed_rides,
            "unmatched_rides": unmatched_rides,
            "cancelled_rides": cancelled_rides,
            "avg_wait_time": avg_wait_time,
            "avg_ride_duration": avg_ride_duration
        }

# ---------------- API ENDPOINTS ----------------
@app.route('/api/health')
def health():
    return jsonify({'status': 'ok'})

@app.route('/api/rides')
def list_rides():
    with app.app_context():
        rides = Ride.query.all()
        result = []
        for ride in rides:
            result.append({
                'id': ride.id,
                'rider_id': ride.rider_id,
                'driver_id': ride.driver_id,
                'status': ride.status,
                'pickup_location': (ride.pickup_lat, ride.pickup_long),
                'drop_location': (ride.drop_lat, ride.drop_long),
                'created_at': ride.created_at.isoformat() if ride.created_at else None,
                'driver_assigned_at': ride.driver_assigned_at.isoformat() if ride.driver_assigned_at else None,
                'driver_at_location_at': ride.driver_at_location_at.isoformat() if ride.driver_at_location_at else None,
                'start_ride_at': ride.start_ride_at.isoformat() if ride.start_ride_at else None,
                'end_ride_at': ride.end_ride_at.isoformat() if ride.end_ride_at else None,
                'distance_km': ride.distance_km,
                'fare': ride.fare
            })
        return jsonify(result)

@app.route('/api/drivers')
def list_drivers():
    with app.app_context():
        drivers = Driver.query.all()
        result = []
        for driver in drivers:
            result.append({
                'id': driver.id,
                'name': driver.name,
                'location': (driver.latitude, driver.longitude),
                'available': driver.available,
                'active_ride_id': driver.active_ride_id,
                'cancelled_rides_count': driver.cancelled_rides_count
            })
        return jsonify(result)

@app.route('/api/riders')
def list_riders():
    with app.app_context():
        riders = Rider.query.all()
        result = []
        for rider in riders:
            result.append({
                'id': rider.id,
                'name': rider.name,
                'location': (rider.latitude, rider.longitude)
            })
        return jsonify(result)

@app.route('/api/metrics')
def get_metrics():
    with app.app_context():
        return jsonify(generate_summary())

# ---------------- CLI ENTRYPOINT ----------------
def init_db():
    """Initialize the database tables"""
    with app.app_context():
        db.create_all()
        logger.info("Database initialized")

def run_simulation():
    """Run the complete simulation"""
    with app.app_context():
        # Initialize database
        db.create_all()
        
        # Seed initial data
        seed_pricing()
        seed_users()
        
        # Generate rides for simulation
        generate_rides(SIM_DAYS)
        
        # Run simulation
        simulate_rides()
        
        logger.info("Simulation completed successfully")

def run_server():
    """Run the Flask server"""
    # Make sure database is initialized
    with app.app_context():
        db.create_all()
    
    # Run the Flask application
    app.run(debug=True, host='0.0.0.0', port=5000)

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python main.py [init_db|simulate|runserver]")
        sys.exit(1)
    
    command = sys.argv[1]
    
    if command == 'init_db':
        init_db()
    elif command == 'simulate':
        run_simulation()
    elif command == 'runserver':
        run_server()
    else:
        print("Unknown command. Available commands: init_db, simulate, runserver")
        sys.exit(1)
