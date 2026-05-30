import heapq
from typing import Dict, List, Tuple
from src.models import (
    Scenario, SchedulerResult, BusTimeline, ChargingEvent, BusConfig
)

class DiscreteEventSimulator:
    def __init__(self, scenario: Scenario):
        self.scenario = scenario
        self.constants = scenario.constants
        self.weights = scenario.weights
        self.route = scenario.route

    def run(self, path_assignments: Dict[str, List[str]]) -> SchedulerResult:
        """Runs a discrete event simulation with the given path assignments for each bus.
        
        Args:
            path_assignments: Dict of bus_id -> list of station names where it should charge.
            
        Returns:
            A SchedulerResult containing timelines, station queues, and optimization metrics.
        """
        # Event queue: list of tuples (time_min, event_id, event_type, bus_id, payload)
        event_queue = []
        event_counter = 0

        def add_event(time: float, event_type: str, bus_id: str, payload: dict = None):
            nonlocal event_counter
            heapq.heappush(event_queue, (time, event_counter, event_type, bus_id, payload or {}))
            event_counter += 1

        # Global state
        current_time = 0.0
        
        # Station state
        station_busy_chargers: Dict[str, int] = {st.name: 0 for st in self.scenario.stations}
        # station_name -> list of dicts {"bus_id": str, "arrival_time": float, "soc_before": float}
        station_queues: Dict[str, List[dict]] = {st.name: [] for st in self.scenario.stations}
        # station_name -> list of ChargingEvent
        station_charge_history: Dict[str, List[ChargingEvent]] = {st.name: [] for st in self.scenario.stations}

        # Bus state
        bus_configs: Dict[str, BusConfig] = {bus.id: bus for bus in self.scenario.buses}
        bus_timelines: Dict[str, BusTimeline] = {}
        
        # Dynamic tracking state per bus
        bus_curr_node_idx: Dict[str, int] = {}  # index of current node in ordered nodes list
        bus_soc: Dict[str, float] = {}          # current range in km remaining
        bus_dep_time: Dict[str, float] = {}      # actual departure time
        bus_wait_time: Dict[str, float] = {}     # total wait time so far
        bus_events: Dict[str, List[ChargingEvent]] = {bus.id: [] for bus in self.scenario.buses}
        bus_soc_timeline: Dict[str, List[Tuple[float, float]]] = {bus.id: [] for bus in self.scenario.buses}

        # Dynamic metrics: operator -> list of accumulated wait times so far
        operator_wait_times: Dict[str, List[float]] = {}
        for bus in self.scenario.buses:
            if bus.operator not in operator_wait_times:
                operator_wait_times[bus.operator] = []

        # Helper functions defined at the top of run() to avoid UnboundLocalError in scope
        def get_operator_avg_wait(op: str) -> float:
            waits = operator_wait_times.get(op, [])
            if not waits:
                return 0.0
            return sum(waits) / len(waits)

        def resolve_station_queue(station_name: str, sim_time: float):
            num_chargers = self.scenario.get_station_chargers(station_name)
            queue = station_queues[station_name]
            
            while station_busy_chargers[station_name] < num_chargers and queue:
                scored_queue = []
                for entry in queue:
                    b_id = entry["bus_id"]
                    b_config = bus_configs[b_id]
                    
                    wait_time = sim_time - entry["arrival_time"]
                    op_avg_wait = get_operator_avg_wait(b_config.operator)
                    elapsed_time = sim_time - bus_dep_time[b_id]
                    
                    score = (
                        self.weights.individual * wait_time * b_config.priority_weight +
                        self.weights.operator * op_avg_wait +
                        self.weights.overall * elapsed_time
                    )
                    scored_queue.append((score, entry))
                
                scored_queue.sort(key=lambda x: x[0], reverse=True)
                _, selected_entry = scored_queue[0]
                
                queue.remove(selected_entry)
                station_busy_chargers[station_name] += 1
                
                selected_bus_id = selected_entry["bus_id"]
                selected_bus = bus_configs[selected_bus_id]
                wait_duration = sim_time - selected_entry["arrival_time"]
                
                operator_wait_times[selected_bus.operator].append(wait_duration)
                bus_wait_time[selected_bus_id] += wait_duration
                
                evt = ChargingEvent(
                    bus_id=selected_bus_id,
                    operator=selected_bus.operator,
                    station_name=station_name,
                    arrival_time=selected_entry["arrival_time"],
                    charge_start_time=sim_time,
                    charge_end_time=sim_time + self.constants.charging_duration_min,
                    wait_time_min=wait_duration,
                    soc_before=selected_entry["soc_before"]
                )
                
                bus_events[selected_bus_id].append(evt)
                station_charge_history[station_name].append(evt)
                
                add_event(
                    sim_time + self.constants.charging_duration_min,
                    "CHARGE_COMPLETED",
                    selected_bus_id,
                    {"station_name": station_name}
                )

        # Schedule initial departures
        for bus in self.scenario.buses:
            dep_min = float(bus.departure_minutes)
            add_event(dep_min, "DEPARTURE", bus.id)
            bus_timelines[bus.id] = BusTimeline(
                bus_id=bus.id,
                operator=bus.operator,
                direction=bus.direction,
                departure_time=dep_min,
                arrival_time=dep_min,
                total_trip_time=0.0,
                total_wait_time=0.0
            )

        # Main Event Loop
        while event_queue:
            time_min, _, event_type, bus_id, payload = heapq.heappop(event_queue)
            current_time = time_min
            bus = bus_configs[bus_id]
            ordered_nodes = self.route.get_ordered_nodes(bus.direction)

            if event_type == "DEPARTURE":
                bus_curr_node_idx[bus_id] = 0
                bus_soc[bus_id] = self.constants.battery_capacity_km
                bus_dep_time[bus_id] = current_time
                bus_wait_time[bus_id] = 0.0
                bus_soc_timeline[bus_id].append((current_time, self.constants.battery_capacity_km))
                
                next_node = ordered_nodes[1]
                dist = self.route.get_segment_distance(ordered_nodes[0], next_node)
                travel_time = dist / (self.constants.bus_speed_kmh / 60.0)
                add_event(current_time + travel_time, "ARRIVAL", bus_id, {"node_idx": 1, "dist_traveled": dist})

            elif event_type == "ARRIVAL":
                node_idx = payload["node_idx"]
                dist_traveled = payload["dist_traveled"]
                node_name = ordered_nodes[node_idx]
                
                bus_soc[bus_id] -= dist_traveled
                bus_soc_timeline[bus_id].append((current_time, bus_soc[bus_id]))
                bus_curr_node_idx[bus_id] = node_idx
                
                if node_idx == len(ordered_nodes) - 1:
                    timeline = bus_timelines[bus_id]
                    timeline.arrival_time = current_time
                    timeline.total_trip_time = current_time - bus_dep_time[bus_id]
                    timeline.total_wait_time = bus_wait_time[bus_id]
                    timeline.charging_events = bus_events[bus_id]
                    timeline.path_taken = path_assignments.get(bus_id, [])
                    timeline.soc_timeline = bus_soc_timeline[bus_id]
                    continue
                
                path = path_assignments.get(bus_id, [])
                if node_name in path:
                    station_queues[node_name].append({
                        "bus_id": bus_id,
                        "arrival_time": current_time,
                        "soc_before": bus_soc[bus_id]
                    })
                    resolve_station_queue(node_name, current_time)
                else:
                    next_node = ordered_nodes[node_idx + 1]
                    dist = self.route.get_segment_distance(node_name, next_node)
                    travel_time = dist / (self.constants.bus_speed_kmh / 60.0)
                    add_event(current_time + travel_time, "ARRIVAL", bus_id, {
                        "node_idx": node_idx + 1,
                        "dist_traveled": dist
                    })

            elif event_type == "CHARGE_COMPLETED":
                station_name = payload["station_name"]
                station_busy_chargers[station_name] -= 1
                
                bus_soc[bus_id] = self.constants.battery_capacity_km
                bus_soc_timeline[bus_id].append((current_time, self.constants.battery_capacity_km))
                
                node_idx = bus_curr_node_idx[bus_id]
                next_node = ordered_nodes[node_idx + 1]
                dist = self.route.get_segment_distance(ordered_nodes[node_idx], next_node)
                travel_time = dist / (self.constants.bus_speed_kmh / 60.0)
                add_event(current_time + travel_time, "ARRIVAL", bus_id, {
                    "node_idx": node_idx + 1,
                    "dist_traveled": dist
                })
                
                resolve_station_queue(station_name, current_time)

        # -------------------------------------------------------------
        # Pluggable Rule Engine Evaluation
        # -------------------------------------------------------------
        from src.rules import (
            MaxIndividualWaitRule, OperatorFleetAverageWaitRule,
            OverallAverageTripTimeRule, RangeViolationPenaltyRule
        )
        
        rules = [
            MaxIndividualWaitRule(),
            OperatorFleetAverageWaitRule(),
            OverallAverageTripTimeRule(),
            RangeViolationPenaltyRule()
        ]
        
        total_cost = 0.0
        metrics = {}
        
        # Helper unweighted cumulative wait tracked separately for reference
        metrics["total_wait_time"] = sum(t.total_wait_time for t in bus_timelines.values())
        
        for rule in rules:
            penalty, name, val = rule.evaluate(bus_timelines, self.scenario)
            total_cost += penalty
            metrics[name] = val

        return SchedulerResult(
            scenario_name=self.scenario.name,
            bus_timelines=bus_timelines,
            station_schedules=station_charge_history,
            metrics=metrics,
            total_cost=total_cost
        )
