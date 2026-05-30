import json
import os
from typing import List, Dict, Any
from src.models import (
    Scenario, Route, Segment, PhysicalConstants, 
    OptimizationWeights, BusConfig, StationConfig
)

def load_scenario_from_dict(data: Dict[str, Any]) -> Scenario:
    """Parses a dictionary matching the scenario JSON structure into a Scenario model."""
    
    # 1. Parse route
    route_data = data["route"]
    segments = [
        Segment(
            from_node=seg["from_node"],
            to_node=seg["to_node"],
            distance_km=float(seg["distance_km"])
        )
        for seg in route_data["segments"]
    ]
    route = Route(
        segments=segments,
        endpoints=route_data["endpoints"],
        stations=route_data["stations"]
    )
    
    # 2. Parse stations
    stations = [
        StationConfig(
            name=st["name"],
            num_chargers=st.get("num_chargers", 1)
        )
        for st in data["stations"]
    ]
    
    # 3. Parse buses
    buses = [
        BusConfig(
            id=bus["id"],
            operator=bus["operator"],
            direction=bus["direction"],
            departure_time_str=bus["departure_time_str"],
            priority_weight=bus.get("priority_weight", 1.0)
        )
        for bus in data["buses"]
    ]
    
    # 4. Parse constants
    const_data = data.get("physical_constants", {})
    constants = PhysicalConstants(
        battery_capacity_km=float(const_data.get("battery_capacity_km", 240.0)),
        charging_duration_min=float(const_data.get("charging_duration_min", 25.0)),
        bus_speed_kmh=float(const_data.get("bus_speed_kmh", 60.0))
    )
    
    # 5. Parse weights
    weights_data = data.get("weights", {})
    weights = OptimizationWeights(
        individual=float(weights_data.get("individual", 1.0)),
        operator=float(weights_data.get("operator", 1.0)),
        overall=float(weights_data.get("overall", 1.0))
    )
    
    return Scenario(
        name=data["name"],
        description=data["description"],
        route=route,
        stations=stations,
        buses=buses,
        constants=constants,
        weights=weights
    )

def load_scenario_from_file(file_path: str) -> Scenario:
    """Reads a JSON file from disk and parses it into a Scenario model."""
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Scenario file not found at: {file_path}")
        
    with open(file_path, "r") as f:
        data = json.load(f)
        
    return load_scenario_from_dict(data)

def list_available_scenarios(directory_path: str) -> Dict[str, str]:
    """Scans the directory for .json scenario files, returning a dict of scenario name -> file path."""
    scenarios = {}
    if not os.path.exists(directory_path):
        return scenarios
        
    for filename in sorted(os.listdir(directory_path)):
        if filename.endswith(".json"):
            full_path = os.path.join(directory_path, filename)
            try:
                with open(full_path, "r") as f:
                    data = json.load(f)
                    if "name" in data:
                        scenarios[data["name"]] = full_path
            except Exception:
                # Silently ignore malformed files during scan
                continue
    return scenarios
