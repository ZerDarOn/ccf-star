import pytest

from coc_star_api.dice_roller import InvalidDiceExpression, roll_dice


def test_roll_dice_returns_bounded_rolls_and_total() -> None:
    result = roll_dice("2d6+3")

    assert result.expression == "2d6+3"
    assert len(result.rolls) == 2
    assert all(1 <= value <= 6 for value in result.rolls)
    assert result.total == sum(result.rolls) + 3


@pytest.mark.parametrize("expression", ["d100", "0d6", "1d1", "101d6", "1d1001", "1d6+10001", "1d6; import os"])
def test_roll_dice_rejects_unsafe_or_out_of_range_expressions(expression: str) -> None:
    with pytest.raises(InvalidDiceExpression):
        roll_dice(expression)
