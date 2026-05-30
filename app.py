import streamlit as st
import os
import pandas as pd
from typing import Dict, List
from src.loader import list_available_scenarios, load_scenario_from_file
from src.scheduler import GreedyScheduler
from src.models import Scenario, OptimizationWeights, SchedulerResult

# Set page configuration for a premium, wide layout
st.set_page_config(
    page_title="Bus Charging Scheduler",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Inject custom Google Font and subtle design elements
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
    
    html, body, [class*="css"] {
        font-family: 'Inter', sans-serif;
    }
    
    .main-header {
        background: linear-gradient(135deg, #1f4068, #162447);
        padding: 2rem;
        border-radius: 12px;
        color: white;
        margin-bottom: 2rem;
        box-shadow: 0 4px 15px rgba(0,0,0,0.1);
    }
    
    .stMetric {
        background-color: var(--background-color);
        padding: 1.2rem;
        border-radius: 8px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.05);
        border: 1px solid var(--border-color, #e0e0e0);
        border-left: 5px solid #00b4d8;
    }
</style>
""", unsafe_allow_html=True)

# -------------------------------------------------------------
# 1. Sidebar & Scenario Selection
# -------------------------------------------------------------
st.sidebar.markdown("### ⚡ Scenario Controller")

# Locate scenarios directory
scenarios_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "scenarios")
scenarios_dict = list_available_scenarios(scenarios_dir)

if not scenarios_dict:
    st.error("No JSON scenarios found under the `scenarios/` directory! Please run the scenario generator script first.")
    st.stop()

selected_scenario_name = st.sidebar.selectbox(
    "Select Scenario",
    options=list(scenarios_dict.keys()),
    index=0
)

# Load base scenario configuration
scenario_path = scenarios_dict[selected_scenario_name]
base_scenario: Scenario = load_scenario_from_file(scenario_path)

# Live Weights Tuning Sliders (Dynamic optimization control)
st.sidebar.markdown("---")
st.sidebar.markdown("### 🎛️ Live Weight Tuning")
st.sidebar.markdown("Tune the optimization weights below to immediately see how the charging scheduler reorganizes priorities:")

weight_ind = st.sidebar.slider(
    "Individual Wait Weight ($w_{ind}$)",
    min_value=0.0,
    max_value=10.0,
    value=base_scenario.weights.individual,
    step=0.5,
    help="Higher values heavily penalize any single bus waiting in queue for too long."
)

weight_op = st.sidebar.slider(
    "Operator Fleet Weight ($w_{op}$)",
    min_value=0.0,
    max_value=10.0,
    value=base_scenario.weights.operator,
    step=0.5,
    help="Higher values prioritize balancing fairness and minimizing delay across an operator's fleet as a group."
)

weight_overall = st.sidebar.slider(
    "Overall Network Weight ($w_{overall}$)",
    min_value=0.0,
    max_value=10.0,
    value=base_scenario.weights.overall,
    step=0.5,
    help="Higher values prioritize minimizing the total trip duration across all buses combined."
)

# Reset weights button
if st.sidebar.button("Reset to Scenario Defaults"):
    st.rerun()

# Scenario Constants Preview (Collapsible)
st.sidebar.markdown("---")
with st.sidebar.expander("🛠️ Scenario Specifications", expanded=False):
    st.markdown(f"**Battery Capacity:** {base_scenario.constants.battery_capacity_km} km")
    st.markdown(f"**Speed:** {base_scenario.constants.bus_speed_kmh} km/h")
    st.markdown(f"**Charging Time:** {base_scenario.constants.charging_duration_min} min (to full)")
    
    st.markdown("**Station Chargers Capacity:**")
    for station in base_scenario.stations:
        st.markdown(f"- Station {station.name}: {station.num_chargers} charger(s)")

# -------------------------------------------------------------
# 2. Solver Execution
# -------------------------------------------------------------
# Instantiate the customized optimization weights
custom_weights = OptimizationWeights(
    individual=weight_ind,
    operator=weight_op,
    overall=weight_overall
)

# Bind custom weights to scenario
scenario = Scenario(
    name=base_scenario.name,
    description=base_scenario.description,
    route=base_scenario.route,
    stations=base_scenario.stations,
    buses=base_scenario.buses,
    constants=base_scenario.constants,
    weights=custom_weights
)

# Execute Greedy Scheduler in-memory
scheduler = GreedyScheduler(scenario)
result: SchedulerResult = scheduler.schedule()

# -------------------------------------------------------------
# 3. Main Dashboard UI
# -------------------------------------------------------------
# Main Header Card
st.markdown(f"""
<div class="main-header">
    <h1 style="margin: 0; font-size: 2.2rem; font-weight: 700;">⚡ Bus Charging Scheduler</h1>
    <p style="margin: 0.5rem 0 0 0; font-size: 1rem; font-weight: 300; opacity: 0.9;">
        {scenario.name} &mdash; {scenario.description}
    </p>
</div>
""", unsafe_allow_html=True)

# -------------------------------------------------------------
# KPI Metrics Row (Using Native Theme-Aware st.metric)
# -------------------------------------------------------------
c1, c2, c3, c4, c5 = st.columns(5)

with c1:
    st.metric(
        label="Optimization Cost",
        value=f"{result.total_cost:.1f}",
        help="Weighted composite penalty score."
    )

with c2:
    st.metric(
        label="Max Individual Wait",
        value=f"{result.metrics['max_individual_wait']:.0f} min",
        help="Worst-case queue wait time."
    )

with c3:
    st.metric(
        label="Operator Average Wait",
        value=f"{result.metrics['operator_fleet_avg_wait']:.1f} min",
        help="Fleet average delay fairness."
    )

with c4:
    st.metric(
        label="Avg Network Trip Time",
        value=f"{result.metrics['overall_avg_trip_time']:.1f} min",
        help="Total time (travel + charge + wait)."
    )

with c5:
    violations = int(result.metrics['range_violations'])
    st.metric(
        label="Range Violations",
        value=str(violations),
        help="Hard constraint: distance between stops must be <= 240km."
    )

# Helper function to format relative minutes back to chronological "HH:MM"
def format_time_str(time_min: float) -> str:
    total_mins = int(time_min)
    hours = (total_mins // 60) % 24
    minutes = total_mins % 60
    return f"{hours:02d}:{minutes:02d}"

# -------------------------------------------------------------
# Core Tabs Layout
# -------------------------------------------------------------
tab_timetable, tab_chargers, tab_config = st.tabs([
    "📅 Per-Bus Timetable", 
    "🔌 Per-Station Charging Logs", 
    "🔍 Scenario Input Data"
])

# =============================================================
# TAB 1: PER-BUS TIMETABLE
# =============================================================
with tab_timetable:
    st.markdown("### 📅 Timetable Overview")
    st.markdown("The chronological schedule decided by the greedy constructive planner for all 20 buses:")
    
    # Construct a clean DataFrame for the timetable display
    rows = []
    for b_id, timeline in result.bus_timelines.items():
        charges = ", ".join(timeline.path_taken) if timeline.path_taken else "No stops (Direct)"
        rows.append({
            "Bus ID": b_id,
            "Operator": timeline.operator.upper(),
            "Direction": timeline.direction,
            "Departure": format_time_str(timeline.departure_time),
            "Arrival": format_time_str(timeline.arrival_time),
            "Trip Duration": f"{int(timeline.total_trip_time)} min",
            "Queue Wait Time": f"{int(timeline.total_wait_time)} min",
            "Stations Charged": charges
        })
        
    df_timetable = pd.DataFrame(rows)
    st.dataframe(df_timetable, use_container_width=True, hide_index=True)
    
    st.markdown("---")
    st.markdown("### 🔬 Inspect Bus Charging Journey & Battery SoC")
    st.markdown("Select a specific bus below to see its exact segment-by-segment timeline, charging details, and battery level verification:")
    
    selected_bus_id = st.selectbox(
        "Choose Bus to Inspect",
        options=sorted(list(result.bus_timelines.keys()))
    )
    
    timeline = result.bus_timelines[selected_bus_id]
    ordered_nodes = scenario.route.get_ordered_nodes(timeline.direction)
    
    st.markdown(f"**Journey Details: {selected_bus_id} ({timeline.operator.upper()})** | Departure: `{format_time_str(timeline.departure_time)}` | Arrival: `{format_time_str(timeline.arrival_time)}` | Total Wait: `{int(timeline.total_wait_time)} minutes`")
    
    # Render interactive steps in a clean column list
    timeline_cols = st.columns(len(ordered_nodes))
    
    # We rebuild step-by-step state
    curr_time = timeline.departure_time
    curr_soc = scenario.constants.battery_capacity_km
    
    for idx, node in enumerate(ordered_nodes):
        with timeline_cols[idx]:
            # Check if this node had a charge event
            charge_event = next((e for e in timeline.charging_events if e.station_name == node), None)
            
            if idx == 0:
                # Origin Node
                st.markdown(f"""
                <div style="background-color: #e3f2fd; border: 1px solid #90caf9; padding: 10px; border-radius: 8px; text-align: center; color: #1b262c;">
                    <div style="font-weight: bold; font-size: 1.1rem; color: #0d47a1;">{node}</div>
                    <div style="font-size: 0.8rem; margin-top: 5px;">Departure</div>
                    <div style="font-size: 0.9rem; font-weight: bold; margin-top: 3px;">{format_time_str(curr_time)}</div>
                    <div style="font-size: 0.8rem; color: #2e7d32; font-weight: bold; margin-top: 5px;">⚡ {int(curr_soc)} km</div>
                </div>
                """, unsafe_allow_html=True)
            elif idx == len(ordered_nodes) - 1:
                # Destination Node
                prev_node = ordered_nodes[idx - 1]
                dist = scenario.route.get_segment_distance(prev_node, node)
                curr_soc -= dist
                st.markdown(f"""
                <div style="background-color: #eceff1; border: 1px solid #b0bec5; padding: 10px; border-radius: 8px; text-align: center; color: #1b262c;">
                    <div style="font-weight: bold; font-size: 1.1rem; color: #37474f;">{node}</div>
                    <div style="font-size: 0.8rem; margin-top: 5px;">Arrival</div>
                    <div style="font-size: 0.9rem; font-weight: bold; margin-top: 3px;">{format_time_str(timeline.arrival_time)}</div>
                    <div style="font-size: 0.8rem; color: {'#2e7d32' if curr_soc >= 0 else '#c62828'}; font-weight: bold; margin-top: 5px;">🔋 {int(curr_soc)} km</div>
                </div>
                """, unsafe_allow_html=True)
            else:
                # Intermediate station stop
                prev_node = ordered_nodes[idx - 1]
                dist = scenario.route.get_segment_distance(prev_node, node)
                curr_soc -= dist
                
                if charge_event:
                    # Charged here
                    wait_time = charge_event.wait_time_min
                    arr_time = charge_event.arrival_time
                    start_time = charge_event.charge_start_time
                    end_time = charge_event.charge_end_time
                    
                    st.markdown(f"""
                    <div style="background-color: #e8f5e9; border: 2px solid #81c784; padding: 10px; border-radius: 8px; text-align: center; color: #1b262c;">
                        <div style="font-weight: bold; font-size: 1.1rem; color: #2e7d32;">Station {node}</div>
                        <div style="font-size: 0.75rem; color: #558b2f; font-weight: bold; margin-top: 3px;">⚡ CHARGED</div>
                        <div style="font-size: 0.75rem; color: #555; margin-top: 5px;">Arrived: {format_time_str(arr_time)}</div>
                        <div style="font-size: 0.75rem; color: #555;">Wait: <span style="color: {'#c62828' if wait_time > 0 else '#555'}; font-weight: bold;">{int(wait_time)} min</span></div>
                        <div style="font-size: 0.75rem; color: #555;">Charged: {format_time_str(start_time)}-{format_time_str(end_time)}</div>
                        <div style="font-size: 0.8rem; color: #37474f; font-weight: bold; margin-top: 5px;">🔋 {int(curr_soc)} km &rarr; 240 km</div>
                    </div>
                    """, unsafe_allow_html=True)
                    # Charger fills range back to full
                    curr_soc = scenario.constants.battery_capacity_km
                else:
                    # Skipped station
                    st.markdown(f"""
                    <div style="background-color: #fafafa; border: 1px dashed #bdbdbd; padding: 10px; border-radius: 8px; text-align: center; color: #1b262c;">
                        <div style="font-weight: bold; font-size: 1.1rem; color: #757575;">Station {node}</div>
                        <div style="font-size: 0.75rem; color: #9e9e9e; margin-top: 3px;">SKIPPED (Bypassed)</div>
                        <div style="font-size: 0.8rem; color: #2e7d32; font-weight: bold; margin-top: 15px;">🔋 {int(curr_soc)} km</div>
                    </div>
                    """, unsafe_allow_html=True)

# =============================================================
# TAB 2: PER-STATION CHARGING LOGS
# =============================================================
with tab_chargers:
    st.markdown("### 🔌 Station Charger Utilization schedules")
    st.markdown("For each station, see the chronological order of buses that charged there, along with wait times and battery entry levels:")
    
    st_cols = st.columns(4)
    stations_ordered = ["A", "B", "C", "D"]
    
    for i, st_name in enumerate(stations_ordered):
        with st_cols[i]:
            st.markdown(f"#### 🔌 Station {st_name} (Capacity: {scenario.get_station_chargers(st_name)} charger)")
            history = result.station_schedules.get(st_name, [])
            
            if not history:
                st.markdown("*No buses scheduled to charge at this station.*")
                continue
                
            st_rows = []
            for evt in history:
                st_rows.append({
                    "Queue Order": len(st_rows) + 1,
                    "Bus ID": evt.bus_id,
                    "Operator": evt.operator.upper(),
                    "Arrival": format_time_str(evt.arrival_time),
                    "Start Charge": format_time_str(evt.charge_start_time),
                    "End Charge": format_time_str(evt.charge_end_time),
                    "Wait Time": f"{int(evt.wait_time_min)} min",
                    "Entry SoC": f"{int(evt.soc_before)} km"
                })
            df_st = pd.DataFrame(st_rows)
            st.dataframe(df_st, use_container_width=True, hide_index=True)

# =============================================================
# TAB 3: SCENARIO CONFIGURATION
# =============================================================
with tab_config:
    st.markdown("### 🔎 Scenario Raw Configuration")
    st.markdown("Below is the pure raw JSON scenario specification loaded by the engine:")
    
    # Load and show raw JSON
    with open(scenario_path, "r") as f:
        raw_json = f.read()
    st.json(raw_json)
