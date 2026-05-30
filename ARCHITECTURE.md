# Architecture & Design Documentation (Layman-Friendly Guide)

This document explains how the **Bus Charging Scheduler** works under the hood. It is written so that **anyone—even a non-programmer—can easily understand the entire system**, the step-by-step calculations, and how it is built to scale for the future.

---

## 1. The Dispatcher Analogy (How to think about the system)

Imagine you are the **Chief Dispatcher** for a fleet of electric buses traveling a highway between **Bengaluru and Kochi**. Along the highway, there are four charging stations: **A, B, C, and D**. Each station has exactly **1 charger plug** (a single charger slot).

Your buses have a physical battery limit: they can drive a maximum of **240 kilometers** on a full charge. Because the entire highway is **540 kilometers**, a bus **cannot** complete the trip without stopping to charge at least twice.

As the Dispatcher, you have two jobs:
1. **The Route Plan:** Decide exactly which stations each bus will stop at to charge (for example: stop at A and C, or stop at B and D).
2. **The Queue Rules:** When two or more buses arrive at the same station at the same time, decide **who gets to plug in first** and who has to wait.

Our software acts as your **Digital Assistant**. It runs a real-time, minute-by-minute simulation of all buses moving along the highway and automatically chooses the best schedule.

---

## 2. The 3-Step Flow (How the scheduler calculates the results)

The scheduler goes through three simple steps to find the perfect plan:

```
┌─────────────────────────────────┐
│     STEP 1: LOAD CONFIG         │  <-- Reads the stations, distances, speed,
│ (The Map and Departure Times)   │      and bus departure times from a JSON file.
└────────────────┬────────────────┘
                 │
                 ▼
┌─────────────────────────────────┐
│     STEP 2: ROUTE CHECK         │  <-- Finds all "legal" charging patterns
│  (The Valid Charging Plans)     │      for each bus (preserves the 240km limit).
└────────────────┬────────────────┘
                 │
                 ▼
┌─────────────────────────────────┐
│     STEP 3: SIMULATOR LOOP      │  <-- Simulates the buses moving minute-by-minute.
│ (Greedy Insertion & Queue Scors)│      Assigns plans to minimize delays based on
└─────────────────────────────────┘      live optimization weights.
```

### Step 1: Load the Scenario Configuration
The software reads a text file (in JSON format) containing the details of the world:
- The highway map (distances between stations A, B, C, D).
- The vehicle physical limits (60 km/h speed, 25-minute charge duration, 240 km battery range).
- The scheduled bus departures (which bus departs from which end, at what time, owned by which operator).
- The optimization weights (how important are individual wait times, operator delays, or overall network speeds).

### Step 2: Find all "Legal" Charging Plans for each Bus
Before any bus departs, the system calculates all possible charging schedules that will physically prevent the bus from running out of battery.
For buses traveling **Bengaluru → Kochi**:
- **Plan 1:** Charge at `{A, C}` (Drive 100km to A &rarr; charge &rarr; drive 220km to C &rarr; charge &rarr; drive 220km to Kochi). *All segments are under 240km, so this is legal!*
- **Plan 2:** Charge at `{B, D}` (Drive 220km to B &rarr; charge &rarr; drive 220km to D &rarr; charge &rarr; drive 100km to Kochi). *Legal!*
- **Plan 3:** Charge at `{B, C}` (Drive 220km to B &rarr; charge &rarr; drive 100km to C &rarr; charge &rarr; drive 220km to Kochi). *Legal!*
- Other plans with 3 or 4 stops are also generated but are slower.
The system automatically calculates the equivalent reverse plans for buses traveling **Kochi → Bengaluru** (such as `{D, B}` or `{C, A}`).

### Step 3: Run the Chronological Simulation (Greedy Insertion)
The system schedules buses one-by-one in order of their departure times:
1. It takes the first bus and simulates the entire network. It tries Plan 1, Plan 2, and Plan 3 for this bus.
2. It calculates a "composite penalty score" for each plan.
3. It permanently assigns the plan that has the **lowest penalty score** (the least amount of waiting and delay).
4. It takes the next bus, simulates it alongside the already-scheduled buses, and finds its best plan.
5. It repeats this until all 20 buses have a finalized plan. This takes less than **0.005 seconds** in total!

---

## 3. How We Calculate Costs & Priorities (Simple Math)

When multiple buses are waiting at a station for a charger, we need to decide who goes first. We do this by calculating a **Priority Score** for each waiting bus:

$$\text{Priority Score} = (\text{Individual Weight} \times \text{Wait Time}) + (\text{Operator Weight} \times \text{Operator Average Wait}) + (\text{Overall Weight} \times \text{Elapsed Time})$$

The bus with the **highest Priority Score** gets the charger next. 

### What do these three parts mean in plain English?
1. **Individual Wait ($w_{\text{ind}}$):** How long this specific bus has been waiting in queue at this station. Multiplying by this weight prevents any single bus from being neglected and waiting forever.
2. **Operator Fleet Average Wait ($w_{\text{op}}$):** The average wait time experienced by all other buses owned by this bus's operator (e.g., KPN, Freshbus, or Flixbus). High weights here ensure that an operator's fleet is scheduled fairly and runs smoothly as a group.
3. **Overall Journey Time ($w_{\text{overall}}$):** The time elapsed since the bus departed its origin. High weights here prioritize older, early-departing buses so they reach their destination on time, keeping the overall network delays low.

---

### 🧮 A Concrete Numerical Example
Let's see what happens at a charger using basic numbers.

Suppose **Bus 1 (KPN)** and **Bus 2 (Freshbus)** are waiting at Station B at **21:00**:
- **Bus 1 (KPN):**
  - Has been waiting in queue for **10 minutes**.
  - Its operator (KPN) has had an average fleet wait of **4 minutes** so far.
  - Has been on the road for **120 minutes** since departure.
- **Bus 2 (Freshbus):**
  - Has been waiting in queue for **5 minutes**.
  - Its operator (Freshbus) has had an average fleet wait of **12 minutes** so far.
  - Has been on the road for **140 minutes** since departure.

#### Case A: You care most about Individual Wait times ($w_{\text{ind}} = 10$, $w_{\text{op}} = 1$, $w_{\text{overall}} = 1$)
- **Bus 1 Score:** $(10 \times 10) + (1 \times 4) + (1 \times 120) = 100 + 4 + 120 = \mathbf{224}$
- **Bus 2 Score:** $(10 \times 5) + (1 \times 12) + (1 \times 140) = 50 + 12 + 140 = \mathbf{202}$
- **Outcome:** Bus 1 has the higher score ($\mathbf{224} > \mathbf{202}$). **Bus 1 gets to charge first** because it has been waiting in line longer.

#### Case B: You care most about Operator Fleet Fairness ($w_{\text{ind}} = 1$, $w_{\text{op}} = 10$, $w_{\text{overall}} = 1$)
- **Bus 1 Score:** $(1 \times 10) + (10 \times 4) + (1 \times 120) = 10 + 40 + 120 = \mathbf{170}$
- **Bus 2 Score:** $(1 \times 5) + (10 \times 12) + (1 \times 140) = 5 + 120 + 140 = \mathbf{265}$
- **Outcome:** Bus 2 has the higher score ($\mathbf{265} > \mathbf{170}$). **Bus 2 gets to charge first** because its operator (Freshbus) has been suffering from much higher average delays across its fleet.

*This shows exactly how tuning sliders on your Streamlit sidebar immediately changes the priority logs at the stations in real-time!*

---

## 4. The Extensibility Matrix (Designing for the Future)

A key requirement of this assignment is that the system must scale easily as the real world grows. The table below shows how major future changes are handled **via data configuration in JSON alone**, requiring **zero code changes**:

| Future Change | Code Change Required? | How the Design Handles It |
| :--- | :---: | :--- |
| **Add Station E** | **No** | Simply add Station `"E"` and its distance segments to the JSON scenario file. The `Route` model automatically calculates the new segments, and the path generator dynamically discovers the new valid stopping patterns. |
| **Double Chargers at B (Capacity = 2)** | **No** | Change `"num_chargers": 2` in the station configuration in the JSON file. The simulator's occupancy checker automatically allows up to 2 concurrent charging slots at Station B. |
| **Add a New Operator (e.g., VRL)** | **No** | Set `"operator": "VRL"` on the bus config in the JSON scenario file. The priority queue resolves and tracks VRL fleet averages dynamically out of the box. |
| **Double Battery Capacity (480 km)** | **No** | Change `"battery_capacity_km": 480.0` in the JSON physical constants. The path generator automatically allows longer travel segments and selects paths with fewer (or zero) stops. |
| **Change Segment Distances** | **No** | Update segment distances in the JSON segments. The simulator automatically recalculates travel durations, and the path generator filters out paths that violate the battery range limit. |
| **Add VIP/Priority Buses** | **No (Data-Driven)** | Add a `"priority_weight": 3.0` field to the bus config in the JSON file. The queue priority scoring function dynamically multiplies the wait time of that bus by its priority weight, boosting it in queue contention. |
| **Time-of-day Electricity Pricing** | **Yes (Minimal)** | Add a small soft rule class/function that adds a penalty to the schedule score if a bus charges during peak hours. The sequential scheduler will automatically route buses to bypass stations during peak cost windows. |
| **Driver Shift Limits** | **Yes (Minimal)** | Add a hard rule checking that no bus timeline exceeds the driver shift duration (e.g., 9 hours). If a path causes wait times that violate the limit, the insertion scheduler automatically rejects that path option. |

---

## 5. Developer Code Examples (For the Interview)

### A. How to Change a Weight (JSON)
Weights are fully parameterized in the scenario JSON files:
```json
"weights": {
  "individual": 1.0,
  "operator": 2.0,
  "overall": 1.0
}
```

### B. How to Add a New Rule Live (Time-of-Day Pricing Code)
If the interviewer asks you to add a new soft rule (e.g., **Peak Hour Charging Costs**) live:

1. Insert a peak hour penalty calculation in the simulator's cost metric evaluation (inside `src/simulation.py`):
```python
# Inside DiscreteEventSimulator.run():
peak_pricing_penalty = 0.0
for b_id, timeline in bus_timelines.items():
    for event in timeline.charging_events:
        # Penalize charging between 18:00 and 22:00 (peak hours)
        # 18:00 = 1080 mins from midnight, 22:00 = 1320 mins
        if 1080 <= event.charge_start_time <= 1320:
            peak_pricing_penalty += 50.0  # cost penalty per peak hour charge

# Add this to the total_cost calculation:
total_cost += peak_pricing_penalty * self.scenario.weights.electricity_cost
```
2. Add `"electricity_cost"` to the JSON weights and Streamlit sidebar. The scheduler will dynamically calculate this and avoid charging during peak times!
