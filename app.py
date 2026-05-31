import os
from typing import List

import pandas as pd
import streamlit as st

from src.loader import list_available_scenarios, load_scenario_from_file
from src.models import OptimizationWeights, Scenario, SchedulerResult
from src.scheduler import GreedyScheduler


st.set_page_config(
    page_title="EV Bus Charging Scheduler",
    page_icon="EV",
    layout="wide",
    initial_sidebar_state="expanded",
)


def format_time_str(time_min: float) -> str:
    total_mins = int(round(time_min))
    hours = (total_mins // 60) % 24
    minutes = total_mins % 60
    return f"{hours:02d}:{minutes:02d}"


def direction_label(direction: str) -> str:
    return direction.replace("->", " -> ")


def station_color(station_name: str) -> str:
    colors = {
        "A": "#2563EB",
        "B": "#F59E0B",
        "C": "#16A34A",
        "D": "#7C3AED",
        "E": "#DC2626",
    }
    return colors.get(station_name, "#475569")


def build_scenario(base_scenario: Scenario, weights: OptimizationWeights) -> Scenario:
    return Scenario(
        name=base_scenario.name,
        description=base_scenario.description,
        route=base_scenario.route,
        stations=base_scenario.stations,
        buses=base_scenario.buses,
        constants=base_scenario.constants,
        weights=weights,
    )


def departure_rows(buses) -> List[dict]:
    return [
        {
            "Bus ID": bus.id,
            "Operator": bus.operator,
            "Direction": direction_label(bus.direction),
            "Departure Time": bus.departure_time_str,
        }
        for bus in buses
    ]


def timetable_rows(result: SchedulerResult) -> List[dict]:
    rows = []
    for bus_id, timeline in sorted(result.bus_timelines.items()):
        rows.append(
            {
                "Bus ID": bus_id,
                "Operator": timeline.operator,
                "Direction": direction_label(timeline.direction),
                "Charging stations": ", ".join(timeline.path_taken) or "Direct",
                "Total Wait (min)": int(round(timeline.total_wait_time)),
                "Trip Duration (min)": int(round(timeline.total_trip_time)),
                "Arrival Time": format_time_str(timeline.arrival_time),
                
            }
        )
    return rows


st.markdown(
    """
<style>
    :root {
        --navy: #061A34;
        --navy-2: #092747;
        --ink: #0B1533;
        --muted: #64748B;
        --line: #E2E8F0;
        --panel: #FFFFFF;
        --page: #F7FAFE;
        --blue: #1D64D8;
    }

    .stApp {
        background: var(--page);
        color: var(--ink);
        font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    }

    [data-testid="stHeader"] {
        background: var(--page);
    }

    .block-container {
        padding-top: 1.25rem;
        padding-bottom: 1.25rem;
        max-width: 1600px;
    }

    h1, h2, h3, h4, h5, h6, p, label, span, div {
        font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    }

    [data-testid="stSidebar"] {
        background:
            radial-gradient(circle at 20% 0%, rgba(45, 111, 214, 0.36), transparent 30%),
            linear-gradient(180deg, #061A34 0%, #041426 100%);
        color: white;
        border-right: 1px solid rgba(255,255,255,0.08);
    }

    [data-testid="stSidebarContent"] {
        min-height: 100vh;
        padding-top: 1.2rem;
        padding-bottom: 7rem;
    }

    [data-testid="stSidebar"] * {
        color: white;
    }

    [data-testid="stSidebar"] .stSelectbox label,
    [data-testid="stSidebar"] .stSlider label {
        font-size: 0.78rem;
        color: #C7D2FE !important;
    }

    [data-testid="stSidebar"] [data-baseweb="select"] * {
        color: #0B1533 !important;
    }

    [data-testid="stSidebar"] [data-baseweb="select"] {
        background: #FFFFFF !important;
        border-radius: 8px;
    }

    .sidebar-brand {
        display: flex;
        align-items: center;
        gap: 0.85rem;
        padding: 0 0.2rem 1.4rem;
    }

    .brand-mark {
        width: 48px;
        height: 48px;
        border-radius: 999px;
        border: 1px solid rgba(255,255,255,0.65);
        display: grid;
        place-items: center;
        font-size: 1.45rem;
        background: rgba(10, 31, 64, 0.82);
        color: #4ADE80 !important;
    }

    .brand-title {
        font-size: 1.08rem;
        font-weight: 800;
        line-height: 1.15;
        letter-spacing: 0;
    }

    .brand-subtitle {
        margin-top: 0.35rem;
        font-size: 0.72rem;
        color: #C7D2FE !important;
    }

    .side-nav {
        display: grid;
        gap: 0.35rem;
        margin: 0.2rem 0 1.2rem;
    }

    .side-nav-item {
        display: flex;
        align-items: center;
        gap: 0.7rem;
        padding: 0.65rem 0.8rem;
        border-radius: 8px;
        color: #D8E4FF !important;
        font-size: 0.9rem;
        font-weight: 650;
    }

    .side-nav-item.active {
        background: linear-gradient(135deg, #2D70E2, #1554C2);
        color: white !important;
        box-shadow: 0 10px 20px rgba(0,0,0,0.18);
    }

    .side-card {
        background: rgba(255,255,255,0.08);
        border: 1px solid rgba(255,255,255,0.09);
        border-radius: 8px;
        padding: 0.95rem;
        margin-top: 1rem;
    }

    .side-card-title {
        font-size: 0.9rem;
        font-weight: 750;
        margin-bottom: 0.65rem;
    }

    .side-card p {
        color: #E5EDFF !important;
        font-size: 0.82rem;
        line-height: 1.45;
        margin: 0.35rem 0;
    }

    .side-footer {
        position: fixed;
        left: 1.45rem;
        bottom: 1.35rem;
        width: 250px;
        display: flex;
        align-items: center;
        gap: 0.75rem;
        color: #D8E4FF !important;
    }

    .mini-logo {
        width: 38px;
        height: 38px;
        display: grid;
        place-items: center;
        border-radius: 999px;
        background: rgba(37, 99, 235, 0.28);
        color: #4ADE80 !important;
        font-weight: 900;
    }

    .app-header {
        display: flex;
        justify-content: space-between;
        gap: 1rem;
        align-items: flex-start;
        margin-bottom: 1rem;
    }

    .scenario-title {
        display: flex;
        align-items: center;
        gap: 0.65rem;
        margin: 0;
        color: var(--ink);
        font-size: 1.35rem;
        line-height: 1.2;
        font-weight: 820;
        letter-spacing: 0;
    }

    .page-header {
        background: transparent;
        padding: 0.2rem 0 0.95rem;
    }

    .page-title {
        color: #0B1533 !important;
        font-size: 1.35rem;
        line-height: 1.2;
        font-weight: 850;
        letter-spacing: 0;
        margin-bottom: 0.35rem;
    }

    .page-desc {
        color: #23345D !important;
        font-size: 0.88rem;
        line-height: 1.35;
        font-weight: 520;
    }

    .active-badge {
        color: #15803D !important;
        background: #DCFCE7;
        border: 1px solid #86EFAC;
        border-radius: 6px;
        padding: 0.15rem 0.45rem;
        font-size: 0.7rem;
        font-weight: 750;
    }

    .scenario-desc {
        color: #23345D !important;
        font-size: 0.88rem;
        margin-top: 0.35rem;
    }

    .top-actions {
        display: flex;
        justify-content: flex-end;
        align-items: center;
        gap: 0.9rem;
        color: #334155 !important;
        font-size: 0.82rem;
        white-space: nowrap;
        margin-top: 0.25rem;
    }

    .panel {
        background: var(--panel);
        border: 1px solid var(--line);
        border-radius: 8px;
        box-shadow: 0 1px 2px rgba(15,23,42,0.04);
        padding: 0.85rem;
        margin-bottom: 0.9rem;
    }

    .panel-title {
        font-size: 0.94rem;
        font-weight: 820;
        color: var(--ink) !important;
        margin-bottom: 0.15rem;
    }

    .panel-help {
        font-size: 0.75rem;
        color: var(--muted) !important;
        margin-bottom: 0.55rem;
    }

    .metric-card {
        background: white;
        border: 1px solid var(--line);
        border-radius: 8px;
        min-height: 132px;
        padding: 1rem;
        display: flex;
        gap: 0.85rem;
        align-items: flex-start;
        box-shadow: 0 1px 2px rgba(15,23,42,0.04);
    }

    .metric-icon {
        width: 34px;
        height: 34px;
        display: grid;
        place-items: center;
        border-radius: 8px;
        font-size: 1.2rem;
        font-weight: 900;
    }

    .metric-icon::before {
        display: block;
        font-size: 1.15rem;
        line-height: 1;
    }

    .metric-icon-bus::before { content: "🚌"; }
    .metric-icon-plug::before { content: "🔌"; }
    .metric-icon-clock::before { content: "⏱"; }
    .metric-icon-alert::before { content: "!"; font-size: 1rem; font-weight: 900; }
    .metric-icon-route::before { content: "↗"; }
    .metric-icon-shield::before { content: "✓"; font-size: 1rem; font-weight: 900; }

    .metric-label {
        color: #1E2A4A !important;
        font-size: 0.78rem;
        font-weight: 750;
        margin-bottom: 0.4rem;
    }

    .metric-value {
        color: #071435 !important;
        font-size: 1.45rem;
        line-height: 1.05;
        font-weight: 850;
        letter-spacing: 0;
    }

    .metric-sub {
        margin-top: 0.55rem;
        color: #475569 !important;
        font-size: 0.76rem;
        line-height: 1.45;
    }

    div[data-testid="stDataFrame"] {
        border: 1px solid var(--line);
        border-radius: 8px;
        overflow: hidden;
        background: white;
    }

    .selected-panel {
        min-height: 310px;
    }

    .journey-row {
        display: grid;
        grid-template-columns: 28px 1fr auto;
        gap: 0.6rem;
        padding: 0.6rem 0.35rem;
        border-bottom: 1px solid #EEF2F7;
        align-items: start;
    }

    .journey-dot {
        width: 24px;
        height: 24px;
        border-radius: 999px;
        display: grid;
        place-items: center;
        color: white !important;
        font-size: 0.78rem;
        font-weight: 850;
        margin-top: 0.05rem;
    }

    .journey-name {
        color: var(--ink) !important;
        font-size: 0.86rem;
        font-weight: 800;
    }

    .journey-meta {
        color: #334155 !important;
        font-size: 0.78rem;
        line-height: 1.35;
        margin-top: 0.18rem;
    }

    .journey-time {
        color: #0B1533 !important;
        font-size: 0.78rem;
        font-weight: 750;
        white-space: nowrap;
    }

    .summary-strip {
        margin-top: 0.75rem;
        border-radius: 8px;
        background: #EFF6FF;
        border: 1px solid #BFDBFE;
        padding: 0.65rem 0.75rem;
        color: #1E3A8A !important;
        font-size: 0.82rem;
        font-weight: 700;
    }

    .station-card {
        background: white;
        border: 1px solid var(--line);
        border-radius: 8px;
        padding: 0.8rem;
        min-height: 168px;
    }

    .station-title {
        display: flex;
        align-items: center;
        gap: 0.55rem;
        color: var(--ink) !important;
        font-size: 0.86rem;
        font-weight: 850;
        margin-bottom: 0.55rem;
    }

    .station-letter {
        width: 24px;
        height: 24px;
        border-radius: 999px;
        color: white !important;
        display: grid;
        place-items: center;
        font-size: 0.78rem;
        font-weight: 850;
    }

    .station-event {
        display: flex;
        justify-content: space-between;
        gap: 0.75rem;
        color: #0F172A !important;
        font-size: 0.78rem;
        padding: 0.25rem 0;
        border-bottom: 1px solid #F1F5F9;
    }

    .station-event span:last-child {
        color: #334155 !important;
        white-space: nowrap;
    }

    .detail-card {
        background: white;
        border: 1px solid #CBD5E1;
        border-radius: 8px;
        padding: 1.35rem 1.45rem;
        min-height: 420px;
        box-shadow: 0 1px 2px rgba(15,23,42,0.04);
    }

    .footnote {
        color: #64748B !important;
        font-size: 0.76rem;
        margin-top: 0.35rem;
    }

    .stButton > button {
        border-radius: 6px;
        font-weight: 750;
        min-height: 2.4rem;
    }

    @media (max-width: 900px) {
        .app-header {
            display: block;
        }
        .top-actions {
            justify-content: flex-start;
            margin-top: 0.8rem;
        }
        .metric-card {
            min-height: 112px;
        }
    }
</style>
""",
    unsafe_allow_html=True,
)


scenarios_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "scenarios")
scenarios_dict = list_available_scenarios(scenarios_dir)

if not scenarios_dict:
    st.error("No JSON scenarios found under the scenarios/ directory.")
    st.stop()

scenario_names = list(scenarios_dict.keys())
if "current_scenario" not in st.session_state:
    st.session_state.current_scenario = scenario_names[0]

if st.session_state.current_scenario not in scenarios_dict:
    st.session_state.current_scenario = scenario_names[0]

base_scenario = load_scenario_from_file(scenarios_dict[st.session_state.current_scenario])

scenario_changed = st.session_state.get("weights_bound_to") != st.session_state.current_scenario
if scenario_changed:
    st.session_state.weights_bound_to = st.session_state.current_scenario
    st.session_state.pending_individual = base_scenario.weights.individual
    st.session_state.pending_operator = base_scenario.weights.operator
    st.session_state.pending_overall = base_scenario.weights.overall
    st.session_state.applied_individual = base_scenario.weights.individual
    st.session_state.applied_operator = base_scenario.weights.operator
    st.session_state.applied_overall = base_scenario.weights.overall
    st.session_state.selected_bus_id = base_scenario.buses[0].id

applied_weights = OptimizationWeights(
    individual=st.session_state.applied_individual,
    operator=st.session_state.applied_operator,
    overall=st.session_state.applied_overall,
)
scenario = build_scenario(base_scenario, applied_weights)
result = GreedyScheduler(scenario).schedule()

if st.session_state.get("selected_bus_id") not in result.bus_timelines:
    st.session_state.selected_bus_id = next(iter(result.bus_timelines))


with st.sidebar:
    st.markdown(
        """
        <div class="sidebar-brand">
            <div class="brand-mark">EV</div>
            <div>
                <div class="brand-title">EV Bus<br>Charging Scheduler</div>
                <div class="brand-subtitle">Plan - Schedule - Optimize</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    selected_scenario = st.selectbox(
        "Scenario",
        scenario_names,
        index=scenario_names.index(st.session_state.current_scenario),
        key="sidebar_scenario_select",
    )
    if selected_scenario != st.session_state.current_scenario:
        st.session_state.current_scenario = selected_scenario
        st.rerun()

    st.markdown("#### Optimization Weights")
    st.slider(
        "Individual wait",
        min_value=0.0,
        max_value=10.0,
        step=0.5,
        key="pending_individual",
    )
    st.slider(
        "Operator fairness",
        min_value=0.0,
        max_value=10.0,
        step=0.5,
        key="pending_operator",
    )
    st.slider(
        "Overall network",
        min_value=0.0,
        max_value=10.0,
        step=0.5,
        key="pending_overall",
    )

    weights_changed = (
        st.session_state.pending_individual != st.session_state.applied_individual
        or st.session_state.pending_operator != st.session_state.applied_operator
        or st.session_state.pending_overall != st.session_state.applied_overall
    )
    if weights_changed:
        st.caption("Weights changed. Click Recalculate Schedule to apply them.")

    if st.button("Recalculate Schedule", width="stretch", type="primary"):
        st.session_state.applied_individual = st.session_state.pending_individual
        st.session_state.applied_operator = st.session_state.pending_operator
        st.session_state.applied_overall = st.session_state.pending_overall
        st.rerun()

    st.markdown(
        """
        <div class="side-card">
            <div class="side-card-title">How to use</div>
            <p>1. Pick a scenario from the sidebar.</p>
            <p>2. Adjust weights and click Recalculate.</p>
            <p>3. Click any bus row to inspect its charging plan.</p>
            <p>4. Station cards show charger usage order.</p>
        </div>
        <div class="side-footer">
            <div class="mini-logo">EV</div>
            <div>
                <div style="font-weight:800;">EV CHARGE CO.</div>
                <div style="font-size:0.74rem;color:#AFC4F7!important;">Powering the Future</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


st.markdown(
    '<div class="page-header">'
    f'<div class="page-title">{scenario.name}</div>'
    f'<div class="page-desc">{scenario.description}</div>'
    "</div>",
    unsafe_allow_html=True,
)


bk_count = len([bus for bus in scenario.buses if bus.direction == "Bengaluru->Kochi"])
kb_count = len([bus for bus in scenario.buses if bus.direction == "Kochi->Bengaluru"])
station_names = ", ".join(station.name for station in scenario.stations)
charger_counts = {station.num_chargers for station in scenario.stations}
charger_text = (
    f"{next(iter(charger_counts))} charger each"
    if len(charger_counts) == 1
    else "mixed charger counts"
)
bus_count = len(result.bus_timelines)
avg_wait = result.metrics["total_wait_time"] / bus_count if bus_count else 0.0

metric_cols = st.columns(6)
metric_data = [
    ("Bus", "#2563EB", "Total Buses", f"{len(scenario.buses)}", f"{bk_count} -> Kochi<br>{kb_count} -> Bengaluru"),
    ("Plug", "#16A34A", "Stations", f"{len(scenario.stations)}", f"{station_names}<br>{charger_text}"),
    ("Clock", "#7C3AED", "Avg Wait", f"{avg_wait:.1f} min", "Queue wait per bus"),
    ("Alert", "#F59E0B", "Max Wait", f"{result.metrics['max_individual_wait']:.0f} min", "Worst single bus"),
    ("Route", "#2563EB", "Avg Trip Time", f"{result.metrics['overall_avg_trip_time']:.0f} min", "Travel + charge + wait"),
    (
        "Shield",
        "#16A34A",
        "Range Violations",
        f"{int(result.metrics['range_violations'])}",
        "Hard rule check",
    ),
]

for col, (icon, color, label, value, subtext) in zip(metric_cols, metric_data):
    with col:
        value_html = f'<div class="metric-value">{value}</div>' if value else ""
        st.markdown(
            '<div class="metric-card">'
            f'<div class="metric-icon metric-icon-{icon.lower()}" style="background:{color}14;color:{color}!important;border:1px solid {color}33;"></div>'
            "<div>"
            f'<div class="metric-label">{label}</div>'
            f"{value_html}"
            f'<div class="metric-sub">{subtext}</div>'
            "</div>"
            "</div>",
            unsafe_allow_html=True,
        )


output_col, detail_col = st.columns([0.63, 0.37])
df_timetable = pd.DataFrame(timetable_rows(result))

with output_col:
    with st.container(border=True):
        st.markdown(
            """
            <div class="panel-title">Bus Timetable Overview (Output)</div>
            <div class="panel-help">Click a row to see the full charging timeline.</div>
            """,
            unsafe_allow_html=True,
        )
        selection = st.dataframe(
            df_timetable,
            width="stretch",
            hide_index=True,
            height=400,
            on_select="rerun",
            selection_mode="single-row",
        )
        if selection.selection.rows:
            selected_row_idx = selection.selection.rows[0]
            st.session_state.selected_bus_id = df_timetable.iloc[selected_row_idx]["Bus ID"]

with detail_col:
    selected_bus_id = st.session_state.selected_bus_id
    timeline = result.bus_timelines[selected_bus_id]
    ordered_nodes = scenario.route.get_ordered_nodes(timeline.direction)
    current_soc = scenario.constants.battery_capacity_km
    detail_rows = []
    for idx, node in enumerate(ordered_nodes):
        charge_event = next((event for event in timeline.charging_events if event.station_name == node), None)

        if idx == 0:
            detail_rows.append(
                '<div class="journey-row">'
                '<div class="journey-dot" style="background:#2563EB;">D</div>'
                f'<div><div class="journey-name">Depart {node}</div>'
                f'<div class="journey-meta">Range available: {int(current_soc)} km</div></div>'
                f'<div class="journey-time">{format_time_str(timeline.departure_time)}</div>'
                "</div>"
            )
            continue

        previous_node = ordered_nodes[idx - 1]
        distance = scenario.route.get_segment_distance(previous_node, node)
        current_soc -= distance

        if idx == len(ordered_nodes) - 1:
            detail_rows.append(
                '<div class="journey-row">'
                '<div class="journey-dot" style="background:#2563EB;">A</div>'
                f'<div><div class="journey-name">Arrive {node}</div>'
                f'<div class="journey-meta">Remaining range: {int(current_soc)} km</div></div>'
                f'<div class="journey-time">{format_time_str(timeline.arrival_time)}</div>'
                "</div>"
            )
            continue

        if charge_event:
            color = station_color(node)
            detail_rows.append(
                '<div class="journey-row">'
                f'<div class="journey-dot" style="background:{color};">{node}</div>'
                f'<div><div class="journey-name">Station {node}</div>'
                '<div class="journey-meta">'
                f"Arrive {format_time_str(charge_event.arrival_time)}<br>"
                f"Charge {format_time_str(charge_event.charge_start_time)} - {format_time_str(charge_event.charge_end_time)} ({int(scenario.constants.charging_duration_min)} min)<br>"
                f"Wait {int(round(charge_event.wait_time_min))} min"
                "</div></div>"
                f'<div class="journey-time">{format_time_str(charge_event.charge_start_time)}</div>'
                "</div>"
            )
            current_soc = scenario.constants.battery_capacity_km

    st.markdown(
        '<div class="detail-card">'
        f'<div class="panel-title">Selected Bus Details: {selected_bus_id}</div>'
        f"{''.join(detail_rows)}"
        '<div class="summary-strip">'
        f"Total Trip Duration: {int(round(timeline.total_trip_time))} min<br>"
        f"Total Wait Time: {int(round(timeline.total_wait_time))} min"
        "</div>"
        "</div>",
        unsafe_allow_html=True,
    )


with st.container(border=True):
    st.markdown('<div class="panel-title">Station Charging Schedule (Order of Usage)</div>', unsafe_allow_html=True)
    station_cols = st.columns(min(len(scenario.stations), 5))
    for idx, station in enumerate(scenario.stations):
        with station_cols[idx % len(station_cols)]:
            history = result.station_schedules.get(station.name, [])
            color = station_color(station.name)
            event_html = []
            if history:
                for event_idx, event in enumerate(history[:7], start=1):
                    event_html.append(
                        '<div class="station-event">'
                        f"<span>{event_idx}. {event.bus_id}</span>"
                        f"<span>{format_time_str(event.charge_start_time)} - {format_time_str(event.charge_end_time)}</span>"
                        "</div>"
                    )
                if len(history) > 7:
                    event_html.append(f"<div class='footnote'>+ {len(history) - 7} more charging events</div>")
            else:
                event_html.append("<div class='footnote'>No scheduled charging here.</div>")

            st.markdown(
                '<div class="station-card">'
                '<div class="station-title">'
                f'<div class="station-letter" style="background:{color};">{station.name}</div>'
                f"<span>Station {station.name}</span>"
                f'<span style="color:#64748B!important;font-size:0.74rem;font-weight:650;">({station.num_chargers} charger)</span>'
                "</div>"
                f"{''.join(event_html)}"
                "</div>",
                unsafe_allow_html=True,
            )

    st.markdown(
        f"""
        <div class="footnote">
            All times are 24-hour format. Charging time is fixed at {int(scenario.constants.charging_duration_min)} minutes.
            Travel speed = {int(scenario.constants.bus_speed_kmh)} km/h. Range violations: {int(result.metrics["range_violations"])}.
        </div>
        """,
        unsafe_allow_html=True,
    )
