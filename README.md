# Rider Service

A ride-hailing service backend application that simulates ride allocation, pricing, and management.

## Overview

This application simulates a ride-hailing service with the following features:

- Driver allocation based on proximity and eligibility rules
- Dynamic fare calculation based on distance, duration, and waiting time
- Ride lifecycle management (creation, driver assignment, pickup, start, end)
- Simulation capabilities for testing and demonstration
- RESTful API endpoints for accessing ride, driver, and rider data

## Architecture

The application follows a modular architecture with the following components:

- **Models** (`models.py`): Data models for Rider, Driver, Ride, and PricingConfig
- **Allocation** (`allocation.py`): Logic for matching riders with available drivers
- **Pricing** (`pricing.py`): Fare calculation based on distance, time, and waiting periods
- **App** (`app.py`): Flask application setup and background scheduler configuration
- **Main** (`main.py`): Application entry point with CLI commands and API endpoints
- **Config** (`config.py`): Application configuration and environment variables
- **Simulation** (`scripts/simulate_rides.py`): Ride simulation for testing

### Component Diagram

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│             │     │             │     │             │
│   models.py │◄────┤    app.py   │────►│ allocation.py│
│             │     │             │     │             │
└─────┬───────┘     └──────┬──────┘     └──────┬──────┘
      │                    │                   │
      │                    ▼                   │
      │              ┌─────────────┐           │
      │              │             │           │
      └─────────────►│   main.py   │◄──────────|
                     │             │
      ┌─────────────►│             │◄───────────┐
      │              └──────┬──────┘            │
      │                     │                   │
┌─────┴───────┐     ┌──────┴──────┐     ┌──────┴──────┐
│             │     │             │     │             │
│  pricing.py │     │  config.py  │     │ simulate.py │
│             │     │             │     │             │
└─────────────┘     └─────────────┘     └─────────────┘
```

## Setup

### Prerequisites

- Python 3.7+
- SQLite (default) or PostgreSQL

### Installation

1. Clone the repository

```bash
git clone <repository-url>
cd rider_service
```

2. Create and activate a virtual environment

```bash
# On Windows
python -m venv venv
venv\Scripts\activate

# On macOS/Linux
python -m venv venv
source venv/bin/activate
```

3. Install dependencies

```bash
pip install -r requirements.txt
```

4. Initialize the database

```bash
python main.py init_db
```

### Environment Variables

Create a `.env` file in the project root with the following variables:

```
SQLALCHEMY_DATABASE_URI=sqlite:///rider_service.db
SQLALCHEMY_TRACK_MODIFICATIONS=False
```

For PostgreSQL, use:

```
SQLALCHEMY_DATABASE_URI=postgresql://username:password@localhost/rider_service
```

## Usage

### Running the Server

```bash
python main.py runserver
```

The server will start on http://localhost:5000

### Running a Simulation

```bash
python main.py simulate
```

This will:
1. Initialize the database with default pricing configurations
2. Create sample riders and drivers
3. Generate random ride requests
4. Simulate the ride lifecycle (allocation, pickup, start, end)
5. Calculate fares and generate a summary

### API Endpoints

- `/api/health` - Health check endpoint
- `/api/rides` - List all rides with details
- `/api/drivers` - List all drivers with status
- `/api/riders` - List all riders
- `/api/metrics` - Get simulation metrics and statistics

### Testing

You can test the application using the simulation feature:

```bash
python main.py simulate
```

This will generate a summary of the simulation results, including:
- Total number of rides
- Completed rides
- Cancelled rides
- Unmatched rides
- Average wait time
- Average ride duration
- Per-driver statistics

## Ride Lifecycle

1. **Ride Creation**: Ride is created with `create_ride` status
2. **Driver Assignment**: Background allocator assigns closest eligible driver
3. **Driver at Location**: Driver arrives at pickup location
4. **Ride Start**: Rider enters vehicle and ride begins
5. **Ride End**: Ride completes at drop-off location and fare is calculated

## Driver Allocation Logic

Drivers are allocated based on the following rules:

1. Driver must not be on an active ride
2. Driver who completed a ride with the same rider less than 30 minutes ago is excluded
3. Driver who cancelled their last 2 rides is excluded
4. The closest eligible driver within the search radius is assigned

### Allocation Flowchart

```
┌─────────────────────┐
│ Ride Created        │
│ (create_ride status)│
└──────────┬──────────┘
           ▼
┌──────────────────────┐
│ Background Allocator │
│ Runs Every 10 Seconds│
└──────────┬───────────┘
           ▼
┌──────────────────────┐
│ For Each Unassigned  │
│ Ride                 │
└──────────┬───────────┘
           ▼
┌──────────────────────┐
│ Set Initial Search   │
│ Radius (1 km)        │
└──────────┬───────────┘
           ▼
┌──────────────────────┐
│ While Radius < 20 km │
└──────────┬───────────┘
           ▼
┌──────────────────────┐
│ Find Drivers Within  │
│ Current Radius       │
└──────────┬───────────┘
           ▼
┌──────────────────────┐
│ Apply Filtering Rules│
│ 1. Not on active ride│
│ 2. No recent ride    │
│   with same rider    │
│ 3. Not cancelled last│
│   2 rides            │
└──────────┬───────────┘
           ▼
┌──────────────────────┐     ┌───────────────────┐
│ Eligible Driver      │ Yes │ Assign Driver to  │
│ Found?               ├────►│ Ride              │
└──────────┬───────────┘     └───────────────────┘
           │ No
           ▼
┌──────────────────────┐
│ Increase Search      │
│ Radius by 1 km       │
└──────────┬───────────┘
           │
           └─────────► (Back to While Loop)
```

## Pricing Model

Fare is calculated using:

- Base fare
- Rate per kilometer
- Rate per minute
- Waiting charge per minute

## Technology Stack

This application is built using the following technologies:

- **Python**: Core programming language
- **Flask**: Lightweight web framework for API endpoints
- **SQLAlchemy**: ORM for database interactions
- **APScheduler**: Background scheduler for driver allocation
- **PostgreSQL/SQLite**: Database options for data persistence
- **Docker**: Containerization for the database

## Assumptions

1. **Geographic Scope**: The service operates within a single city with a defined center and radius
2. **Driver Behavior**: Drivers move at a constant average speed (for simulation purposes)
3. **Ride Requests**: Riders make 1-2 ride requests per day within their vicinity
4. **Cancellations**: Approximately 10% of unassigned rides may be cancelled
5. **Waiting Time**: Riders wait 0-3 minutes after driver arrival before starting the ride
6. **Driver Availability**: Drivers become available immediately after completing a ride
7. **Driver Allocation**: Drivers are allocated based on proximity and eligibility rules
8. **Fare Calculation**: Fare is calculated based on distance, time, and waiting periods
9. **Simulation Time**: For simulation purposes, ride durations are compressed
10. **Driver Location**: Drivers remain at the drop-off location after completing a ride
11. **No Traffic Conditions**: Traffic conditions are not considered in the simulation
12. **No Surge Pricing**: Pricing remains constant regardless of demand or time of day

## Docker Support

The application includes Docker support for the PostgreSQL database:

```bash
docker-compose up -d
```

This will start a PostgreSQL database with the following configuration:
- Database: ride_db
- Username: rideuser
- Password: ridepass
- Port: 5432

To use this database with the application, update your `.env` file:

```
SQLALCHEMY_DATABASE_URI=postgresql://rideuser:ridepass@localhost:5432/ride_db
```

## Simulation Outputs

When running the simulation, you'll see output similar to the following:

```
--- Simulation Summary ---
Total rides: 42
Completed: 35
Cancelled: 4
Unmatched: 3

Driver 1 (John Smith): rides=5, total_fare=1250.75
Driver 2 (Jane Doe): rides=4, total_fare=980.25
Driver 3 (Mike Johnson): rides=6, total_fare=1520.50
...

Average wait (s): 85.32
Average duration (s): 720.45
```

### Key Metrics

- **Driver Utilization**: Percentage of drivers completing at least one ride
- **Average Rides per Driver**: Total completed rides divided by number of drivers
- **Unmatched Rate**: Percentage of rides that couldn't be matched with a driver
- **Cancellation Rate**: Percentage of rides that were cancelled
- **Average Wait Time**: Average time riders waited after driver arrival
- **Average Ride Duration**: Average duration of completed rides

### Screenshots

![Simulation Output](screenshots/simulation_output.png)
*Example of simulation output showing ride statistics*

![API Endpoints](screenshots/api_endpoints.png)
*Example of API endpoints for accessing ride data*

> Note: To generate these screenshots, run the simulation and capture the terminal output, and access the API endpoints through a browser or API client.

## Contributing

Contributions are welcome! Here's how you can contribute to this project:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add some amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

### Development Guidelines

- Follow PEP 8 style guidelines for Python code
- Write unit tests for new features
- Update documentation as needed

## License

This project is licensed under the MIT License - see the LICENSE file for details.