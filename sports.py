"""Dimensions and labels for supported tactile-sports modes."""

from dataclasses import dataclass


@dataclass(frozen=True)
class SportProfile:
    name: str
    length_meters: float
    width_meters: float
    unit_label: str = "m"


SOCCER = SportProfile("soccer", 105.0, 68.0)
# ITF doubles court: baseline-to-baseline x doubles-sideline-to-sideline.
TENNIS = SportProfile("tennis", 23.77, 10.97)
TENNIS_SINGLES = SportProfile("tennis-singles", 23.77, 8.23)

PROFILES = {profile.name: profile for profile in (SOCCER, TENNIS, TENNIS_SINGLES)}


def get_sport(name):
    try:
        return PROFILES[name]
    except KeyError as exc:
        raise ValueError(f"unsupported sport: {name}") from exc
