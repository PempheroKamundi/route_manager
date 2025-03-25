# Route Manager

A Django-based application for planning and managing transportation routes with Hours of Service (HOS) compliance for commercial drivers.

## Overview

Route Manager is a sophisticated logistics planning system that calculates optimal routes for commercial drivers while ensuring full compliance with Federal Motor Carrier Safety Administration (FMCSA) Hours of Service (HOS) regulations. The application intelligently plans routes between pickup and delivery locations, incorporating mandatory breaks, rest periods, refueling stops, and activity planning.

## Features

- **Compliant Route Planning**: Generate routes that adhere to HOS regulations, including:
  - 11-hour driving limit
  - 14-hour on-duty window
  - 30-minute break requirement
  - 70-hour/8-day limit
  - 10-hour rest periods
  - 34-hour restart rule

- **Asynchronous Route Calculation**: High-performance routing using asynchronous processing
  
- **Flexible Architecture**: Support for different rule sets (currently interstate commerce)

- **Detailed Trip Segments**: Break down trips into precise segments with timing information

- **Visualization-Ready Data**: Route information includes coordinates for map visualization

## Architecture & Design Decisions

### Asynchronous Programming

A core design decision was to implement asynchronous programming throughout the routing components:

- **Performance Benefits**: Allows handling of multiple routing requests simultaneously
- **Non-Blocking API Calls**: External routing service calls (OSRM) are non-blocking
- **Parallel Route Retrieval**: Pickup and delivery routes are fetched concurrently using `asyncio.gather`

```python
async def get_routes_in_between(self) -> RoutesInBetween:
    pickup_route, drop_off_route = await asyncio.gather(
        get_route_information(self._current_location, self._pickup_location),
        get_route_information(self._pickup_location, self._drop_off_location),
    )
    
    return RoutesInBetween(
        to_pickup_route=pickup_route,
        to_drop_off_route=drop_off_route,
    )
```

### Design Patterns

The project implements several design patterns to create clean, maintainable code:

#### 1. Template Method Pattern

Used in the route planning components to define the skeleton of the routing algorithm while allowing subclasses to override specific steps:

- `BaseAbstractRoutePlanner`: Defines the template method `plan_route_trip()` that orchestrates the entire route planning process
- `BaseAbstractTripSegmentPlanner`: Provides the skeleton for planning route segments with customizable steps

```python
async def plan_route_trip(self, start_time: datetime.datetime) -> RoutePlan:
    """Template method that defines the skeleton of the route planning algorithm."""
    route_in_between_data = await self.get_routes_in_between()
    
    # Step 1: Plan route to pickup
    pickup_info = self._plan_to_pickup(...)
    
    # Step 2: Handle pickup activity
    pickup_result = self._handle_pickup(...)
    
    # Step 3: Plan route to drop_off
    drop_off_info = self._plan_to_drop_off(...)
    
    # Step 4: Handle drop_off activity
    drop_off_result = self._handle_drop_off(...)
    
    # Step 5: Calculate trip summary
    return self._calculate_trip_summary(...)
```

#### 2. Factory Method Pattern

Implemented to create concrete instances of routers and rule sets:

- `HOSRulesFactory`: Creates appropriate HOS rule implementations
- `USAStandardRoutePlanner.create_route()`: Factory method for creating specific route planners

```python
@classmethod
def create_route(cls, current_location, pickup_location, drop_off_location, current_cycle_used):
    """Factory method for creating a USA route planner."""
    return cls(
        current_location=current_location,
        pickup_location=pickup_location,
        drop_off_location=drop_off_location,
        current_cycle_used=current_cycle_used,
        rule_type=RuleType.INTERSTATE,
        segment_planner=USAInterTripSegmentPlanner(),
    )
```

#### 3. Strategy Pattern

Used for different routing strategies:

- `USAInterTripSegmentPlanner`: Concrete strategy for interstate HOS rules
- Future extensibility for international routes or different jurisdictions

#### 4. Composition Over Inheritance

Components are composed rather than relying on deep inheritance hierarchies:

- `USAStandardRoutePlanner` composes `TripSummaryMixin` and `USATripActivityPlannerMixin`
- `DriverState` is a composable component that tracks HOS compliance

### Modular Repository Pattern

The application uses a repository pattern to separate data access concerns:

- `AsyncOSRMRouteRepository`: Handles interactions with the OSRM routing service
- Interface-based design with `AsyncRouteRepositoryMixin` for flexibility

```python
class AsyncOSRMRouteRepository(AsyncRouteRepositoryMixin):
    """Repository for fetching route information from OSRM."""
    
    async def get_route_information(self, origin: Location, destination: Location) -> RouteInformation:
        # Implementation of routing service interaction
```

### Domain-Driven Design Elements

The code organization follows domain-driven design principles:

- **Core Domain**: Routing, planning, and HOS rule enforcement logic
- **Entity Models**: Clearly defined entities like `DriverState`, `RouteSegment`, and `RoutePlan`
- **Value Objects**: Immutable objects like `Location` and `RouteGeometry`

## Installation

### Prerequisites

- Python 3.10+
- Django 5.1+
- ASGI server (Uvicorn recommended)

### Setup

1. Clone the repository
```bash
git clone https://github.com/yourusername/route_manager.git
cd route_manager
```

2. Install dependencies
```bash
pip install -r requirements.txt
```

3. Configure environment variables
```bash
# Create a .env file with the following variables:
DEBUG=True
SECRET_KEY=your-secret-key
ALLOWED_HOSTS=localhost,127.0.0.1
OSRM_URL=http://router.project-osrm.org/route/v1/driving
```

4. Run migrations
```bash
python manage.py migrate
```

5. Start the server
```bash
uvicorn route_manager.asgi:application
```

Alternatively, use the Make command:
```bash
make async-server
```

## API Endpoints

### Plan a Trip

```
POST /planner/api/trips/
```

**Request Body:**
```json
{
  "current_location": {
    "longitude": -73.935242,
    "latitude": 40.730610
  },
  "pickup_location": {
    "longitude": -74.006015,
    "latitude": 40.712784
  },
  "drop_off_location": {
    "longitude": -73.786967,
    "latitude": 40.644501
  },
  "current_cycle_used": 0.0,
  "start_time": "2023-01-15T08:00:00+00:00",
  "timezone_offset_minutes": -240
}
```

**Response:**
Detailed route plan with segments, timing, and coordinates.

#### Sample Response

```json
{
    "segments": [
        {
            "type": "drive to pickup",
            "start_time": "2025-03-25T10:58:37.851000+02:00",
            "end_time": "2025-03-25T18:58:37.851000+02:00",
            "duration_hours": 8.0,
            "distance_miles": 432.60566683080884,
            "location": "location_name",
            "status": "On Duty (Driving)",
            "start_coordinates": [
                40.69746,
                -73.86161
            ],
            "end_coordinates": [
                37.5653256331488,
                -79.69080794348089
            ]
        },
        {
            "type": "mandatory_driving_break",
            "start_time": "2025-03-25T18:58:37.851000+02:00",
            "end_time": "2025-03-25T19:28:37.851000+02:00",
            "duration_hours": 0.5,
            "distance_miles": 0,
            "location": "location_name",
            "status": "Off Duty",
            "start_coordinates": [
                37.5653256331488,
                -79.69080794348089
            ],
            "end_coordinates": [
                37.5653256331488,
                -79.69080794348089
            ]
        },
        // Additional segments omitted for brevity
        {
            "type": "drop_off",
            "start_time": "2025-03-30T04:40:12.451000+02:00",
            "end_time": "2025-03-30T05:40:12.451000+02:00",
            "duration_hours": 1.0,
            "distance_miles": 0,
            "location": "location_name",
            "status": "On Duty (Not Driving)",
            "start_coordinates": [
                37.43154,
                -122.16929
            ],
            "end_coordinates": [
                37.43154,
                -122.16929
            ]
        }
    ],
    "total_distance_miles": 3265.4604371978576,
    "total_duration_hours": 114.69294444444444,
    "start_time": "2025-03-25T10:58:37.851000+02:00",
    "end_time": "2025-03-30T05:40:12.451000+02:00",
    "route_geometry": {
        "type": "LineString",
        "coordinates": [
            [40.69746, -73.86161],
            [40.57106, -75.95889],
            // Additional coordinates omitted for brevity
            [37.43154, -122.16929]
        ]
    },
    "driving_time": 59.19294444444444, # hours
    "resting_time": 1.5                # hours
}
```

The response shows a complete trip from New York to San Francisco with:
- Required 30-minute breaks after 8 hours of driving
- 10-hour rest periods
- Refueling stops
- Pickup and drop-off activities
- Complete route geometry for visualization
- Total trip statistics

### Process Trucker Logs

```
POST /planner/api/process-logs/
```

Processes driver logs for compliance reporting.

## Testing

Run the tests using pytest:

```bash
pytest
```

Or use the Make commands:

```bash
# Run all tests
make test

# Run tests with coverage report
make test-with-coverage

# Run specific tests
make test-specific TEST_NAME=test_name
```

### Current Test Coverage

```
---------- coverage: platform darwin, python 3.13.0-final-0 ----------
Name                                                   Stmts   Miss  Cover   Missing
------------------------------------------------------------------------------------
conftest.py                                                9      0   100%
hos_rules/__init__.py                                      0      0   100%
hos_rules/rules.py                                        27      2    93%   50, 105
manage.py                                                 11     11     0%   3-22
repository/__init__.py                                     0      0   100%
repository/async_/__init__.py                              0      0   100%
repository/async_/client.py                               48      5    90%   61, 112-113, 149-150
repository/async_/mixins.py                               24      1    96%   67
repository/async_/osrm_repository.py                      63      5    92%   39-40, 147-149
repository/async_/tests/__init__.py                        0      0   100%
repository/async_/tests/conftest.py                        0      0   100%
repository/async_/tests/factory.py                        28      0   100%
repository/async_/tests/test_client.py                   135      7    95%   34, 47-55
repository/async_/tests/test_osrm_repository.py           58      0   100%
repository/async_/tests/test_trip_summarizer.py           73      0   100%
route_manager/__init__.py                                  0      0   100%
route_manager/asgi.py                                      4      4     0%   7-14
route_manager/settings.py                                 25      0   100%
route_manager/urls.py                                      3      3     0%   18-21
route_manager/wsgi.py                                      4      4     0%   10-16
routing/__init__.py                                        0      0   100%
routing/activity_planner.py                               36      0   100%
routing/driver_state.py                                  118     14    88%   108, 113-114, 153-165, 300-311
routing/route_planner/__init__.py                          0      0   100%
routing/route_planner/base_route_planner.py               49     49     0%   13-231
routing/route_planner/standard_route_planner.py           43     43     0%   13-299
routing/segment_planner/__init__.py                        0      0   100%
routing/segment_planner/base_segment_planner.py           95     13    86%   181-185, 200-204, 276, 296, 318, 340, 362, 384, 414
routing/segment_planner/usa_inter_segment_planner.py      93     14    85%   78-94, 136, 143, 150, 313-338
routing/tests/__init__.py                                  0      0   100%
routing/tests/factory.py                                  58     13    78%   27-29, 86-104
routing/tests/test_activity_planner.py                    79      0   100%
routing/tests/test_driver_state.py                       238      0   100%
routing/tests/test_trip_segment_planner.py               113     16    86%   119-124, 178, 261-302
routing/trip_summarizer.py                                51      7    86%   35-45
sample.py                                                 40     40     0%   8-402
sample_6.py                                               89     89     0%   1-213
trip_planner/__init__.py                                   0      0   100%
trip_planner/admin.py                                      0      0   100%
trip_planner/apps.py                                       4      4     0%   1-6
trip_planner/migrations/__init__.py                        0      0   100%
trip_planner/normalizer.py                                61     61     0%   1-180
trip_planner/serializers.py                               13     13     0%   1-21
trip_planner/services.py                                  88     88     0%   1-216
trip_planner/tests.py                                      0      0   100%
trip_planner/urls.py                                       3      3     0%   1-5
trip_planner/views.py                                     74     74     0%   1-161
------------------------------------------------------------------------------------
TOTAL                                                   1857    583    69%
```

## Future Improvements

- Support for additional HOS rule sets (Canada, EU, etc.)
- Integration with real-time traffic data
- Machine learning for trip time prediction
- Mobile application for driver interaction
- WebSocket support for real-time updates

## License

[MIT License](LICENSE)
