import re
import secrets
from dataclasses import dataclass
from typing import Literal


class InvalidDiceExpression(ValueError):
    pass


@dataclass(frozen=True)
class DiceRollResult:
    expression: str
    rolls: tuple[int, ...]
    modifier: int

    @property
    def total(self) -> int:
        return sum(self.rolls) + self.modifier


@dataclass(frozen=True)
class CocPercentileRoll:
    mode: Literal["normal", "bonus", "penalty"]
    total: int
    tens_rolls: tuple[int, ...]
    units: int


_DICE_PATTERN = re.compile(r"^(?P<count>\d{1,3})d(?P<sides>\d{1,4})(?P<modifier>[+-]\d{1,5})?$")
_MAX_DICE_COUNT = 100
_MAX_SIDES = 1_000
_MAX_MODIFIER = 10_000


def roll_dice(expression: str) -> DiceRollResult:
    normalized = expression.strip().lower()
    match = _DICE_PATTERN.fullmatch(normalized)
    if match is None:
        raise InvalidDiceExpression("expected NdM or NdM+K")

    count = int(match.group("count"))
    sides = int(match.group("sides"))
    modifier = int(match.group("modifier") or 0)
    if not 1 <= count <= _MAX_DICE_COUNT:
        raise InvalidDiceExpression("dice count out of range")
    if not 2 <= sides <= _MAX_SIDES:
        raise InvalidDiceExpression("dice sides out of range")
    if abs(modifier) > _MAX_MODIFIER:
        raise InvalidDiceExpression("modifier out of range")

    rolls = tuple(secrets.randbelow(sides) + 1 for _ in range(count))
    return DiceRollResult(normalized, rolls, modifier)


def roll_coc_percentile(mode: Literal["normal", "bonus", "penalty"] = "normal") -> CocPercentileRoll:
    tens_count = 1 if mode == "normal" else 2
    tens_rolls = tuple(secrets.randbelow(10) * 10 for _ in range(tens_count))
    units = secrets.randbelow(10)
    candidates = tuple(100 if tens == 0 and units == 0 else tens + units for tens in tens_rolls)
    total = candidates[0] if mode == "normal" else (min(candidates) if mode == "bonus" else max(candidates))
    return CocPercentileRoll(mode=mode, total=total, tens_rolls=tens_rolls, units=units)
