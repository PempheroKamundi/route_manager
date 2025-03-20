from enum import Enum
from typing import Dict, Type


class BaseHOSRule(Enum):
    """Base class for Hours of Service Rules."""

    def __init__(self, value):
        self._value_ = value

    @classmethod
    def __init_subclass__(cls, **kwargs):
        """Validate that subclass implements all required rules."""
        super().__init_subclass__(**kwargs)

        required_rules = {
            "MAX_DRIVING_HOURS",
            "MAX_DUTY_HOURS",
            "DAILY_REST_PERIOD_HOURS",
            "SHORT_BREAK_PERIOD_MINUTES",
            "MAX_CYCLE_HOURS",
            "AVERAGE_TRUCK_SPEED",
            "REFUEL_DISTANCE",
            "PICKUP_DROP_OFF_TIME",
        }

        # Check if all required rules are implemented in the subclass
        missing_rules = required_rules - set(cls.__members__.keys())
        if missing_rules:
            raise TypeError(
                f"{cls.__name__} must implement the following rules: {', '.join(missing_rules)}"
            )


class HOSInterstateRule(BaseHOSRule):
    """Interstate hours of service Rule."""

    MAX_DRIVING_HOURS = 11.0  # Maximum driving hours per day
    MAX_DUTY_HOURS = 14.0  # Maximum on-duty hours per day
    DAILY_REST_PERIOD_HOURS = 10.0
    SHORT_BREAK_PERIOD_MINUTES = 0.5  # 30 minutes
    MAX_CYCLE_HOURS = 70.0  # Maximum hours in 8-day cycle
    AVERAGE_TRUCK_SPEED = 55.0  # Average truck speed in MPH
    REFUEL_DISTANCE = 1000.0  # Miles between refueling stops
    PICKUP_DROP_OFF_TIME = 1.0  # Hour for pickup/drop_off


class RuleType(Enum):
    INTERSTATE = "interstate"


class HOSRulesFactory:
    _rules_map: Dict[RuleType, Type[HOSInterstateRule]] = {
        RuleType.INTERSTATE: HOSInterstateRule,
    }

    @classmethod
    def get_rule(cls, rule_type: RuleType) -> Type[HOSInterstateRule]:
        return cls._rules_map[rule_type]
