from abc import ABC, abstractmethod
from typing import Dict, Tuple
from src.models import Scenario, BusTimeline

class BaseRule(ABC):
    @abstractmethod
    def evaluate(self, timelines: Dict[str, BusTimeline], scenario: Scenario) -> Tuple[float, str, float]:
        """Evaluates simulated bus outcomes.
        
        Returns:
            A tuple of (weighted_penalty, metric_name, raw_unweighted_value).
        """
        pass

class MaxIndividualWaitRule(BaseRule):
    def evaluate(self, timelines: Dict[str, BusTimeline], scenario: Scenario) -> Tuple[float, str, float]:
        max_wait = 0.0
        for timeline in timelines.values():
            if timeline.total_wait_time > max_wait:
                max_wait = timeline.total_wait_time
        
        weighted_penalty = scenario.weights.individual * max_wait
        return weighted_penalty, "max_individual_wait", max_wait

class OperatorFleetAverageWaitRule(BaseRule):
    def evaluate(self, timelines: Dict[str, BusTimeline], scenario: Scenario) -> Tuple[float, str, float]:
        # Group total wait times by operator
        operator_waits: Dict[str, list] = {}
        for timeline in timelines.values():
            if timeline.operator not in operator_waits:
                operator_waits[timeline.operator] = []
            
            # Sum up wait durations for all charging events of this bus
            bus_wait = sum(evt.wait_time_min for evt in timeline.charging_events)
            operator_waits[timeline.operator].append(bus_wait)
            
        operator_avgs = []
        for waits in operator_waits.values():
            if waits:
                operator_avgs.append(sum(waits) / len(waits))
                
        avg_fleet_wait = sum(operator_avgs) / len(operator_avgs) if operator_avgs else 0.0
        weighted_penalty = scenario.weights.operator * avg_fleet_wait
        return weighted_penalty, "operator_fleet_avg_wait", avg_fleet_wait

class OverallAverageTripTimeRule(BaseRule):
    def evaluate(self, timelines: Dict[str, BusTimeline], scenario: Scenario) -> Tuple[float, str, float]:
        total_time = sum(t.total_trip_time for t in timelines.values())
        avg_trip_time = total_time / len(timelines) if timelines else 0.0
        
        weighted_penalty = scenario.weights.overall * avg_trip_time
        return weighted_penalty, "overall_avg_trip_time", avg_trip_time

class RangeViolationPenaltyRule(BaseRule):
    def evaluate(self, timelines: Dict[str, BusTimeline], scenario: Scenario) -> Tuple[float, str, float]:
        violations = 0
        for timeline in timelines.values():
            socs = [soc for _, soc in timeline.soc_timeline]
            if any(soc < 0.0 for soc in socs):
                violations += 1
                
        # Enormous penalty to filter out invalid paths
        weighted_penalty = violations * 100000.0
        return weighted_penalty, "range_violations", float(violations)
