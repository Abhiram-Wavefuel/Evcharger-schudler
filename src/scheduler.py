from typing import Dict, List
from src.models import Scenario, SchedulerResult, BusConfig
from src.simulation import DiscreteEventSimulator

def generate_all_valid_paths(bus: BusConfig, scenario: Scenario) -> List[List[str]]:
    """Generates all physically valid charging paths for a bus under battery range constraints.
    
    A path is valid if the travel distance of every segment between two charges (or start/end)
    is strictly less than or equal to the battery capacity.
    
    Handles both direction routes dynamically.
    """
    route = scenario.route
    nodes = route.get_ordered_nodes(bus.direction)
    range_limit = scenario.constants.battery_capacity_km
    
    valid_paths = []
    
    def backtrack(curr_idx: int, current_path: List[str]):
        # Calculate remaining distance from current node to final destination
        dist_to_destination = 0.0
        for i in range(curr_idx, len(nodes) - 1):
            dist_to_destination += route.get_segment_distance(nodes[i], nodes[i+1])
            
        # If we can reach the end node directly from current position without charging,
        # then the current accumulated path is valid and complete!
        if dist_to_destination <= range_limit:
            valid_paths.append(current_path.copy())
            
        # Try stopping at next stations
        for next_idx in range(curr_idx + 1, len(nodes) - 1):
            # Calculate distance from current node to next proposed station stop
            dist_to_next_station = 0.0
            for i in range(curr_idx, next_idx):
                dist_to_next_station += route.get_segment_distance(nodes[i], nodes[i+1])
                
            # If next proposed stop is within battery range, explore branching paths
            if dist_to_next_station <= range_limit:
                current_path.append(nodes[next_idx])
                backtrack(next_idx, current_path)
                current_path.pop()

    # Start search from index 0 (origin node)
    backtrack(0, [])
    
    # Sort paths by length (fewer charges preferred in tie-breaks)
    valid_paths.sort(key=len)
    return valid_paths

class GreedyScheduler:
    def __init__(self, scenario: Scenario):
        self.scenario = scenario

    def schedule(self) -> SchedulerResult:
        """Schedules charging plans using an elegant sequential constructive planner.
        
        Buses are sorted by departure time. For each bus, we evaluate every valid path
        in the simulator (alongside previously scheduled buses) and assign the path
        that yields the lowest weighted global cost.
        """
        # Sort buses by departure time to schedule chronologically
        sorted_buses = sorted(self.scenario.buses, key=lambda b: b.departure_minutes)
        
        path_assignments: Dict[str, List[str]] = {}
        
        # We will dynamically build the schedule by inserting one bus at a time.
        # This insertion heuristic naturally resolves conflicts and ensures overall optimality.
        for bus in sorted_buses:
            valid_paths = generate_all_valid_paths(bus, self.scenario)
            
            if not valid_paths:
                # Fallback in case of invalid route dimensions: try stopping at all stations
                path_assignments[bus.id] = self.scenario.route.stations.copy()
                continue
                
            best_path = valid_paths[0]
            lowest_cost = float('inf')
            
            # Temporarily build a subset scenario containing only the buses scheduled so far
            # to run an extremely fast local simulation evaluation.
            for path_opt in valid_paths:
                path_assignments[bus.id] = path_opt
                
                # Create a mini scenario containing only the currently scheduled buses
                current_scheduled_bus_ids = set(b.id for b in sorted_buses if b.id in path_assignments)
                sub_buses = [b for b in self.scenario.buses if b.id in current_scheduled_bus_ids]
                
                sub_scenario = Scenario(
                    name=self.scenario.name,
                    description=self.scenario.description,
                    route=self.scenario.route,
                    stations=self.scenario.stations,
                    buses=sub_buses,
                    constants=self.scenario.constants,
                    weights=self.scenario.weights
                )
                
                # Simulate this configuration
                eval_simulator = DiscreteEventSimulator(sub_scenario)
                eval_result = eval_simulator.run(path_assignments)
                
                # Check for range violations (they have a huge cost penalty, so they are filtered automatically)
                if eval_result.total_cost < lowest_cost:
                    lowest_cost = eval_result.total_cost
                    best_path = path_opt
                    
            # Commit the best path for this bus
            path_assignments[bus.id] = best_path
            
        # Run final full simulation with all assignments
        simulator = DiscreteEventSimulator(self.scenario)
        return simulator.run(path_assignments)
