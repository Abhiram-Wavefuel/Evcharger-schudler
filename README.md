# Electric Bus Charging Scheduler ⚡

A Python and Streamlit application for modeling, simulating, and scheduling electric bus fleets running on a fixed highway segment with charging stations. The scheduler uses a deterministic **Greedy Constructive Simulation** with **Cost-Based Queue Prioritization** to optimize schedules across individual, operator, and overall network constraints.

This codebase has been architected specifically to show foresight for future operational changes (such as adding stations, changing capacities, adding priority buses, or implementing live pricing rules) **without rewriting the core simulation engine**.

---

## 🛠️ Installation & Setup

### 1. Installation
Clone the repository and install the dependencies (only Streamlit is required):
```bash
pip install -r requirements.txt
```

### 2. Run the Web Application
Start the interactive Streamlit dashboard on your local machine:
```bash
streamlit run app.py
```
This will start a local server and automatically open the application in your browser (usually at `http://localhost:8501`).

---

## ⏱️ Live Interview Evaluation Guide (Step-by-Step)

If you are an interviewer testing this submission live, here are three quick curveballs to test the flexibility of our architecture:

### Curveball 1: "Station B now has 3 chargers instead of 1"
1. Open `scenarios/scenario_1.json`.
2. Locate the `"stations"` block and change Station B's chargers:
   ```json
   {
     "name": "B",
     "num_chargers": 3
   }
   ```
3. Save the file. The Streamlit dashboard and simulator automatically update in real-time. No code changes are required!

### Curveball 2: "Add a VIP Bus that must charge first in case of contention"
1. Open `scenarios/scenario_2.json` (or any scenario file).
2. Locate any bus (e.g., `bus-BK-03`) and add a `"priority_weight"` property:
   ```json
   {
     "id": "bus-BK-03",
     "operator": "flixbus",
     "direction": "Bengaluru->Kochi",
     "departure_time_str": "19:16",
     "priority_weight": 5.0
   }
   ```
3. Save the file. The dynamic queue resolved in the simulation immediately pushes `bus-BK-03` to the front of any charging queue because its wait time priority is multiplied by `5.0`. No code changes are required!

---

## ⚙️ How to Change Optimization Weights (JSON)

Tuning optimization weights is fully configuration-driven. In any scenario JSON file under the `scenarios/` directory, simply edit the `"weights"` object:

```json
"weights": {
  "individual": 3.0,
  "operator": 1.0,
  "overall": 2.0
}
```

- `individual`: Multiplies the worst-case individual wait time (prevents individual bus starvation).
- `operator`: Multiplies the average wait time of an operator's fleet as a group (fairness across brands).
- `overall`: Multiplies the average total journey duration (prevents unnecessary charging stops).

*Note: In the Streamlit dashboard, you can also tune these weights live in real-time using the sidebar sliders to see the timetable reorganize instantly.*

---

## 🔌 How to Add a New Rule Live (Code Example)

If asked to add a new soft rule (e.g., **Peak Hour Charging Pricing**) during the live coding segment:

### Step 1: Create the Rule in `src/rules.py`
Add your new rule class inheriting from `BaseRule` at the bottom of `src/rules.py` (approx. 12 lines of code):

```python
# In src/rules.py:
class PeakHourPricingRule(BaseRule):
    def evaluate(self, timelines: Dict[str, BusTimeline], scenario: Scenario) -> Tuple[float, str, float]:
        peak_charges = 0
        for timeline in timelines.values():
            for event in timeline.charging_events:
                # 18:00 = 1080 mins from midnight, 22:00 = 1320 mins
                if 1080 <= event.charge_start_time <= 1320:
                    peak_charges += 1
        
        # Penalize each peak hour charge by 50.0 points
        weighted_penalty = peak_charges * 50.0
        return weighted_penalty, "peak_hour_charges", float(peak_charges)
```

### Step 2: Register the Rule in the Simulator
Open `src/simulation.py` and import/append the new rule to the evaluation list (inside `DiscreteEventSimulator.run()`):

```python
# In src/simulation.py around line 215:
from src.rules import (
    MaxIndividualWaitRule, OperatorFleetAverageWaitRule,
    OverallAverageTripTimeRule, RangeViolationPenaltyRule,
    PeakHourPricingRule  # 1. Import
)

rules = [
    MaxIndividualWaitRule(),
    OperatorFleetAverageWaitRule(),
    OverallAverageTripTimeRule(),
    RangeViolationPenaltyRule(),
    PeakHourPricingRule()  # 2. Append to list
]
```

### That's It!
The core event-driven simulator (`simulation.py`) and sequential optimizer (`scheduler.py`) remain completely untouched. The optimizer will automatically evaluate the new pricing penalty and reroute buses to bypass chargers during peak hours where possible.
