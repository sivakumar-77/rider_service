import math
import logging
from datetime import datetime, timedelta
from app import db
from models import Ride, Driver

# Configuration constants
SEARCH_EXPANSION_KM = 2  # Expand search radius by 2 km every 10 seconds
MAX_SEARCH_RADIUS_KM = 20  # Maximum search radius

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def haversine(lat1, lon1, lat2, lon2):
    """Calculate the great circle distance between two points on the earth"""
    R = 6371  # Earth radius in km
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi/2)**2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda/2)**2
    return R * (2 * math.atan2(math.sqrt(a), math.sqrt(1-a)))

def allocate_drivers():
    """Background job that scans unassigned rides and matches them with available drivers"""
    try:
        # Get all unassigned rides in 'create_ride' state, ordered by creation time
        rides = Ride.query.filter_by(status="create_ride").order_by(Ride.created_at).all()
        logger.info(f"Found {len(rides)} unassigned rides")
        
        for ride in rides:
            logger.info(f"Processing ride {ride.id} - Pickup: ({ride.pickup_lat:.4f}, {ride.pickup_long:.4f}), Rider ID: {ride.rider_id}")
            radius = SEARCH_EXPANSION_KM
            assigned_driver = None

            # Expand search radius until a match is found or max radius is reached
            while radius <= MAX_SEARCH_RADIUS_KM and not assigned_driver:
                # Get all available drivers
                drivers = Driver.query.filter_by(available=True).all()
                logger.info(f"Found {len(drivers)} available drivers for ride {ride.id} within {radius} km radius")
                eligible_drivers = []
                excluded_drivers = {"active_ride": 0, "recent_ride": 0, "cancelled_rides": 0, "out_of_range": 0}

                for driver in drivers:
                    # Rule 1: Driver must not be assigned to more than one active ride
                    if driver.active_ride_id:
                        logger.debug(f"Driver {driver.id} excluded: Already has active ride {driver.active_ride_id}")
                        excluded_drivers["active_ride"] += 1
                        continue

                    # Rule 2: Exclude drivers who recently completed a ride with the same rider within 30 minutes
                    thirty_min_ago = datetime.utcnow() - timedelta(minutes=30)
                    recent_ride = Ride.query.filter(
                        Ride.driver_id == driver.id,
                        Ride.rider_id == ride.rider_id,
                        Ride.status == "end_ride",
                        Ride.end_ride_at > thirty_min_ago
                    ).first()
                    
                    if recent_ride:
                        logger.debug(f"Driver {driver.id} excluded: Recently completed ride {recent_ride.id} with rider {ride.rider_id}")
                        excluded_drivers["recent_ride"] += 1
                        continue

                    # Rule 3: Exclude drivers who cancelled their last 2 rides
                    if driver.cancelled_rides_count >= 2:
                        logger.debug(f"Driver {driver.id} excluded: Has {driver.cancelled_rides_count} cancelled rides")
                        excluded_drivers["cancelled_rides"] += 1
                        continue

                    # Check if driver is within the current search radius
                    dist = haversine(ride.pickup_lat, ride.pickup_long, driver.latitude, driver.longitude)
                    logger.debug(f"Driver {driver.id} is {dist:.2f} km away from pickup location")
                    
                    if dist <= radius:
                        eligible_drivers.append((driver, dist))
                        logger.debug(f"Driver {driver.id} is eligible at distance {dist:.2f} km")
                    else:
                        excluded_drivers["out_of_range"] += 1

                # Log exclusion statistics
                logger.info(f"Ride {ride.id} - Radius {radius} km - Exclusion stats: {excluded_drivers}")
                logger.info(f"Ride {ride.id} - Found {len(eligible_drivers)} eligible drivers within {radius} km radius")

                # If eligible drivers found, assign the closest one
                if eligible_drivers:
                    eligible_drivers.sort(key=lambda x: x[1])  # Sort by distance
                    assigned_driver = eligible_drivers[0][0]
                    logger.info(f"Selected closest driver {assigned_driver.id} at {eligible_drivers[0][1]:.2f} km for ride {ride.id}")
                    break

                # Expand search radius for next iteration
                radius += SEARCH_EXPANSION_KM
                logger.info(f"No eligible drivers found. Expanding search radius to {radius} km for ride {ride.id}")

            # If a driver was found, update ride and driver status
            if assigned_driver:
                ride.driver_id = assigned_driver.id
                ride.driver_assigned_at = datetime.utcnow()
                ride.status = "driver_assigned"
                assigned_driver.available = False
                assigned_driver.active_ride_id = ride.id
                db.session.commit()
                logger.info(f"SUCCESS: Assigned driver {assigned_driver.id} to ride {ride.id} at distance {eligible_drivers[0][1]:.2f} km")
            else:
                logger.warning(f"FAILED: No eligible driver found for ride {ride.id} within maximum radius of {MAX_SEARCH_RADIUS_KM} km")
    
    except Exception as e:
        logger.error(f"Error in driver allocation: {str(e)}")
        db.session.rollback()
    finally:
        db.session.close()
