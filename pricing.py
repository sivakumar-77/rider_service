import math
from datetime import datetime
from models import PricingConfig
from app import db

def haversine(lat1, lon1, lat2, lon2):
    """Calculate the great circle distance between two points on the earth"""
    R = 6371  # Earth radius in km
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi/2)**2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda/2)**2
    return R * (2 * math.atan2(math.sqrt(a), math.sqrt(1-a)))

def get_rate(key, default=0):
    """Get pricing rate from the key-value store"""
    config = PricingConfig.query.filter_by(key=key).first()
    return float(config.value) if config else default

def calculate_fare(ride):
    """Calculate fare based on ride details"""
    import logging
    logger = logging.getLogger(__name__)
    
    logger.info(f"===== CALCULATING FARE FOR RIDE {ride.id} =====")
    
    # Get rates from key-value store
    base_fare = get_rate("base_fare", 20)
    rate_per_km = get_rate("rate_per_km", 10)
    rate_per_minute = get_rate("rate_per_minute", 2)
    waiting_charge_per_minute = get_rate("waiting_charge_per_minute", 1)
    
    logger.info(f"Ride {ride.id} - Pricing rates: Base=${base_fare}, Per km=${rate_per_km}, Per min=${rate_per_minute}, Waiting=${waiting_charge_per_minute}/min")

    # Calculate distance if not already set
    if not ride.distance_km or ride.distance_km == 0:
        ride.distance_km = haversine(
            ride.pickup_lat, ride.pickup_long, 
            ride.drop_lat, ride.drop_long
        )
        logger.info(f"Ride {ride.id} - Calculated distance using haversine: {ride.distance_km:.2f} km")
    else:
        logger.info(f"Ride {ride.id} - Using existing distance: {ride.distance_km:.2f} km")
    
    # Calculate duration and waiting time
    duration_min = 0
    waiting_min = 0
    
    if ride.start_ride_at and ride.end_ride_at:
        duration_min = (ride.end_ride_at - ride.start_ride_at).total_seconds() / 60
        logger.info(f"Ride {ride.id} - Ride duration: {duration_min:.2f} minutes")
    else:
        logger.warning(f"Ride {ride.id} - Cannot calculate duration: start_ride_at={ride.start_ride_at}, end_ride_at={ride.end_ride_at}")
    
    if ride.driver_at_location_at and ride.start_ride_at:
        waiting_min = (ride.start_ride_at - ride.driver_at_location_at).total_seconds() / 60
        logger.info(f"Ride {ride.id} - Waiting time: {waiting_min:.2f} minutes")
    else:
        logger.warning(f"Ride {ride.id} - Cannot calculate waiting time: driver_at_location_at={ride.driver_at_location_at}, start_ride_at={ride.start_ride_at}")

    # Calculate fare components
    base_fare_component = base_fare
    distance_fare_component = ride.distance_km * rate_per_km
    time_fare_component = duration_min * rate_per_minute
    waiting_fare_component = waiting_min * waiting_charge_per_minute
    
    # Store fare components for logging
    ride.base_fare = base_fare_component
    ride.distance_fare = distance_fare_component
    ride.time_fare = time_fare_component
    ride.waiting_fare = waiting_fare_component
    
    # Calculate total fare using the formula
    fare = base_fare_component + distance_fare_component + time_fare_component + waiting_fare_component

    # Log fare breakdown
    logger.info(f"Ride {ride.id} - Fare breakdown:")
    logger.info(f"  Base fare: ${base_fare_component:.2f}")
    logger.info(f"  Distance fare: ${distance_fare_component:.2f} ({ride.distance_km:.2f} km × ${rate_per_km}/km)")
    logger.info(f"  Time fare: ${time_fare_component:.2f} ({duration_min:.2f} min × ${rate_per_minute}/min)")
    logger.info(f"  Waiting fare: ${waiting_fare_component:.2f} ({waiting_min:.2f} min × ${waiting_charge_per_minute}/min)")
    logger.info(f"  Total fare: ${fare:.2f}")

    ride.fare = round(fare, 2)
    db.session.commit()
    logger.info(f"===== FARE CALCULATION COMPLETED FOR RIDE {ride.id} =====\n")
    return fare
