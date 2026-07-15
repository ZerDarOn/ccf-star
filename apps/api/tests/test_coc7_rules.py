import pytest

from coc_star_api.coc7_rules import CharacterImportError, damage_bonus_and_build, derive_stats, parse_st, resolve_check


def test_parse_st_supports_chinese_english_and_aliases() -> None:
    result = parse_st("力量70str70敏捷60dex60理智55san值55克苏鲁10cm10信用20信用评级20侦查25")

    assert result.attributes == {"str": 70, "dex": 60}
    assert result.resources == {"san": 55}
    assert result.skills == {"cthulhu_mythos": 10, "credit_rating": 20, "spot_hidden": 25}
    assert not result.warnings


def test_parse_st_reports_conflicting_alias_values() -> None:
    result = parse_st("力量70str60")

    assert result.attributes["str"] == 60
    assert len(result.warnings) == 1


def test_parse_st_rejects_a_field_without_value() -> None:
    with pytest.raises(CharacterImportError):
        parse_st("力量")


def test_coc7_derived_stats_and_damage_bonus() -> None:
    derived = derive_stats({"con": 55, "siz": 65, "pow": 60, "str": 70})

    assert derived.hp_max == 12
    assert derived.mp_max == 12
    assert derived.san_max == 60
    assert derived.damage_bonus == "+1D4"
    assert derived.build == 1
    assert damage_bonus_and_build(205) == ("+2D6", 3)


@pytest.mark.parametrize(
    ("target", "roll", "level"),
    [(70, 1, "critical"), (70, 14, "extreme"), (70, 35, "hard"), (70, 70, "regular"), (70, 71, "failure"), (40, 96, "fumble"), (70, 100, "fumble")],
)
def test_resolve_coc7_check_levels(target: int, roll: int, level: str) -> None:
    assert resolve_check(target, roll).level == level


def test_check_target_accepts_common_synonyms() -> None:
    from coc_star_api.coc7_rules import canonical_check_target

    assert canonical_check_target("\u4fa6\u5bdf") == ("skill", "spot_hidden")
    assert canonical_check_target("\u89c2\u5bdf\u529b") == ("skill", "spot_hidden")


def test_check_target_accepts_common_synonyms_and_spacing() -> None:
    from coc_star_api.coc7_rules import canonical_check_target

    assert canonical_check_target("侦察") == ("skill", "spot_hidden")
    assert canonical_check_target("观察力") == ("skill", "spot_hidden")
    assert canonical_check_target("  侦 查  ") == ("skill", "spot_hidden")
