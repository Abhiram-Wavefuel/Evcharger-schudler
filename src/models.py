from dataclasses import dataclass, field
from typing import List, Dict, Tuple, Optional

@dataclass(frozen=True)
class Segment:
    from_node: str
    to_node: str
    distance_km: float

@dataclass
class Route:
    segments: List[Segment]
    endpoints: List[str]
    stations: List[str]

    def get_segment_distance(self, from_node: str, to_node: str) -> float:
        """Finds the distance of a segment between two consecutive nodes."""
        for seg in self.segments:
            if (seg.from_node == from_node and seg.to_node == to_node) or \
               (seg.from_node == to_node and seg.to_node == from_node):
                return seg.distance_km
        raise ValueError(f"No route segment exists between '{from_node}' and '{to_node}'")

    def get_ordered_nodes(self, direction: str) -> List[str]:
        """Returns the list of all nodes (endpoints + stations) in route order for the direction."""
        nodes = [self.endpoints[0]] + self.stations + [self.endpoints[1]]
        if direction == "Bengaluru->Kochi":
            return nodes
        elif direction == "Kochi->Bengaluru":
            return list(reversed(nodes))
        else:
            raise ValueError(f"Invalid direction: {direction}")

@dataclass(frozen=True)
class PhysicalConstants:
    battery_capacity_km: float = 240.0
    charging_duration_min: float = 25.0
    bus_speed_kmh: float = 60.0

@dataclass(frozen=True)
class OptimizationWeights:
    individual: float = 1.0
    operator: float = 1.0
    overall: float = 1.0

@dataclass(frozen=True)
class BusConfig:
    id: str
    operator: str
    direction: str
    departure_time_str: str
    priority_weight: float = 1.0  # Supports VIP / Priority buses out of the box

    @property
    def departure_minutes(self) -> int:
        """Minutes from reference epoch (19:00 = 1140 minutes)."""
        hours, mins = map(int, self.departure_time_str.split(":"))
        return hours * 60 + mins

@dataclass(frozen=True)
class StationConfig:
    name: str
    num_chargers: int = 1

@dataclass
class Scenario:
    name: str
    description: str
    route: Route
    stations: List[StationConfig]
    buses: List[BusConfig]
    constants: PhysicalConstants
    weights: OptimizationWeights
    
    def get_station_chargers(self, station_name: str) -> int:
        for st in self.stations:
            if st.name == station_name:
                return st.num_chargers
        return 1  # Default to 1 charger if not specified

@dataclass
class ChargingEvent:
    bus_id: str
    operator: str
    station_name: str
    arrival_time: float      # in minutes from base epoch (19:00)
    charge_start_time: float
    charge_end_time: float
    wait_time_min: float
    soc_before: float        # Battery range in km before charging (for debugging/validation)

@dataclass
class BusTimeline:
    bus_id: str
    operator: str
    direction: str
    departure_time: float    # relative minutes from 19:00
    arrival_time: float      # relative minutes from 19:00
    total_trip_time: float
    total_wait_time: float
    charging_events: List[ChargingEvent] = field(default_factory=list)
    path_taken: List[str] = field(default_factory=list)  # list of charging stations visited
    soc_timeline: List[Tuple[float, float]] = field(default_factory=list)  # list of (time_min, range_km)

@dataclass
class SchedulerResult:
    scenario_name: str
    bus_timelines: Dict[str, BusTimeline]
    station_schedules: Dict[str, List[ChargingEvent]]  # station_name -> chronological charging events
    metrics: Dict[str, float]
    total_cost: float
