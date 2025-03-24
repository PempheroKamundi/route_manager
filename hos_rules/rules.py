"""
hos_rules.rules
~~~~~~~~~~~

This module defines different Hours of service rules for regulating
commercial driver working hours and rest periods.
"""

from enum import Enum
from typing import ClassVar, Dict, Set, Type


class BaseHOSRule(Enum):
    """Base class for Hours of Service Rules.

    This serves as a foundation for specific rule implementations
    and ensures all required rule constants are defined.
    """

    def __init__(self, value: str) -> None:
        """Initialize the enum value.

        Args:
            value: The string value of the enum member
        """
        self._value_ = value

    @classmethod
    def __init_subclass__(cls, **kwargs) -> None:
        """Validate that subclass implements all required rules.

        Raises:
            TypeError: If the subclass doesn't implement all required rules
        """
        super().__init_subclass__(**kwargs)

        required_rules: Set[str] = {
            "MAX_DRIVING_HOURS",
            "MAX_DUTY_HOURS",
            "DAILY_REST_PERIOD_HOURS",
            "SHORT_BREAK_PERIOD_MINUTES",
            "MAX_CYCLE_HOURS",
            "REFUEL_DISTANCE",
            "PICKUP_DROP_OFF_TIME",
        }

        # Check if all required rules are implemented in the subclass
        missing_rules: Set[str] = required_rules - set(cls.__members__.keys())
        if missing_rules:
            raise TypeError(
                f"{cls.__name__} must implement the following rules: {', '.join(missing_rules)}"
            )


class HOSInterstateRule(BaseHOSRule):
    """Interstate hours of service Rule.

    Defines specific hour limitations and operational parameters
    for commercial drivers operating across state lines in the US.
    """

    MAX_DRIVING_HOURS = 11.0  # Maximum driving hours per day
    MAX_DUTY_HOURS = 14.0  # Maximum on-duty hours per day
    DAILY_REST_PERIOD_HOURS = 10.0  # Required daily rest period
    SHORT_BREAK_PERIOD_MINUTES = 0.5  # 30 minutes break requirement
    MAX_CYCLE_HOURS = 70.0  # Maximum hours in 8-day cycle
    REFUEL_DISTANCE = 1000.0  # Miles between refueling stops
    PICKUP_DROP_OFF_TIME = 1.0  # Hour for pickup/drop-off operations


class RuleType(Enum):
    """Enumeration of available HOS rule types.

    This enum provides identifiers for different rule sets that can be
    selected through the factory.
    """

    INTERSTATE = "interstate"


class HOSRulesFactory:
    """Factory for creating and accessing HOS rule implementations.

    Provides a centralized way to access different rule implementations
    based on the requested rule type.
    """

    _rules_map: ClassVar[Dict[RuleType, Type[HOSInterstateRule]]] = {
        RuleType.INTERSTATE: HOSInterstateRule,
    }

    @classmethod
    def get_rule(cls, rule_type: RuleType) -> Type[HOSInterstateRule]:
        """Get the appropriate HOS rule class for the specified rule type.

        Args:
            rule_type: The type of HOS rule to retrieve

        Returns:
            The HOS rule class corresponding to the requested type

        Raises:
            KeyError: If the requested rule type isn't registered in the factory
        """
        return cls._rules_map[rule_type]
