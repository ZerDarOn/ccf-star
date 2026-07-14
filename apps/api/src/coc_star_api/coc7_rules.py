from dataclasses import dataclass, field
from math import floor
import re
from typing import Literal


class CharacterImportError(ValueError):
    pass


AttributeId = Literal["str", "con", "siz", "dex", "app", "int", "pow", "edu", "luck"]
ResourceId = Literal["hp", "mp", "san"]
CheckLevel = Literal["critical", "extreme", "hard", "regular", "failure", "fumble"]


ATTRIBUTE_ALIASES: dict[str, AttributeId] = {
    "力量": "str", "str": "str", "敏捷": "dex", "dex": "dex", "意志": "pow", "pow": "pow",
    "体质": "con", "con": "con", "外貌": "app", "app": "app", "教育": "edu", "edu": "edu",
    "体型": "siz", "siz": "siz", "智力": "int", "灵感": "int", "int": "int",
    "幸运": "luck", "运气": "luck", "luck": "luck",
}
RESOURCE_ALIASES: dict[str, ResourceId] = {
    "体力": "hp", "hp": "hp", "魔法": "mp", "mp": "mp", "理智": "san", "理智值": "san",
    "san值": "san", "san": "san",
}
SKILL_ALIASES: dict[str, str] = {
    "会计": "accounting", "人类学": "anthropology", "估价": "appraise", "考古学": "archaeology",
    "取悦": "charm", "魅惑": "charm", "攀爬": "climb", "计算机": "computer_use", "计算机使用": "computer_use", "电脑": "computer_use",
    "信用": "credit_rating", "信誉": "credit_rating", "信用评级": "credit_rating", "克苏鲁": "cthulhu_mythos", "克苏鲁神话": "cthulhu_mythos", "cm": "cthulhu_mythos",
    "乔装": "disguise", "闪避": "dodge", "汽车": "drive_auto", "驾驶": "drive_auto", "汽车驾驶": "drive_auto", "电气维修": "elec_repair", "电子学": "electronics",
    "话术": "fast_talk", "斗殴": "fighting", "手枪": "firearms_handgun", "急救": "first_aid", "历史": "history", "恐吓": "intimidate", "跳跃": "jump",
    "母语": "language_own", "法律": "law", "图书馆": "library_use", "图书馆使用": "library_use", "聆听": "listen", "开锁": "locksmith", "撬锁": "locksmith", "锁匠": "locksmith",
    "机械维修": "mech_repair", "医学": "medicine", "博物学": "natural_world", "自然学": "natural_world", "领航": "navigate", "导航": "navigate", "神秘学": "occult",
    "重型操作": "operate_heavy_machinery", "重型机械": "operate_heavy_machinery", "操作重型机械": "operate_heavy_machinery", "重型": "operate_heavy_machinery", "说服": "persuade",
    "精神分析": "psychoanalysis", "心理学": "psychology", "骑术": "ride", "妙手": "sleight_of_hand", "侦查": "spot_hidden", "潜行": "stealth", "生存": "survival",
    "游泳": "swim", "投掷": "throw", "追踪": "track", "驯兽": "animal_handling", "潜水": "diving", "爆破": "demolitions", "读唇": "lip_reading", "催眠": "hypnosis", "炮术": "artillery",
}
ALL_ALIASES = sorted({*ATTRIBUTE_ALIASES, *RESOURCE_ALIASES, *SKILL_ALIASES}, key=len, reverse=True)


def canonical_skill_id(name: str) -> str | None:
    return SKILL_ALIASES.get(name.strip())


def canonical_check_target(name: str) -> tuple[Literal["attribute", "skill"], str] | None:
    normalized = name.strip()
    if normalized in ATTRIBUTE_ALIASES:
        return "attribute", ATTRIBUTE_ALIASES[normalized]
    if normalized in SKILL_ALIASES:
        return "skill", SKILL_ALIASES[normalized]
    return None


@dataclass(frozen=True)
class DerivedStats:
    hp_max: int
    mp_max: int
    san_max: int
    build: int
    damage_bonus: str


@dataclass(frozen=True)
class CheckResult:
    target: int
    roll: int
    level: CheckLevel
    half_target: int
    fifth_target: int


@dataclass
class StImportResult:
    attributes: dict[AttributeId, int] = field(default_factory=dict)
    resources: dict[ResourceId, int] = field(default_factory=dict)
    skills: dict[str, int] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    unknown_text: str = ""


def parse_st(text: str) -> StImportResult:
    """Parse the compact field+number format emitted by common COC dice bots."""
    result = StImportResult()
    position = 0
    unknown: list[str] = []
    while position < len(text):
        if text[position].isspace() or text[position] in ",，;；|":
            position += 1
            continue
        alias = next((item for item in ALL_ALIASES if text.startswith(item, position)), None)
        if alias is None:
            unknown.append(text[position])
            position += 1
            continue
        position += len(alias)
        number_match = re.match(r"[+-]?\d+", text[position:])
        if number_match is None:
            raise CharacterImportError(f"字段 {alias} 后缺少数值")
        value = int(number_match.group(0))
        position += len(number_match.group(0))
        if alias in ATTRIBUTE_ALIASES:
            field_id = ATTRIBUTE_ALIASES[alias]
            target = result.attributes
        elif alias in RESOURCE_ALIASES:
            field_id = RESOURCE_ALIASES[alias]
            target = result.resources
        else:
            field_id = SKILL_ALIASES[alias]
            target = result.skills
        previous = target.get(field_id)
        if previous is not None and previous != value:
            result.warnings.append(f"{alias} 与同类字段数值冲突：{previous} -> {value}，采用后者")
        target[field_id] = value
    result.unknown_text = "".join(unknown)
    return result


def derive_stats(attributes: dict[str, int]) -> DerivedStats:
    con = attributes.get("con", 0)
    siz = attributes.get("siz", 0)
    pow_value = attributes.get("pow", 0)
    total = attributes.get("str", 0) + siz
    damage_bonus, build = damage_bonus_and_build(total)
    return DerivedStats(hp_max=floor((con + siz) / 10), mp_max=floor(pow_value / 5), san_max=pow_value, build=build, damage_bonus=damage_bonus)


def damage_bonus_and_build(total: int) -> tuple[str, int]:
    if total <= 64:
        return "-2", -2
    if total <= 84:
        return "-1", -1
    if total <= 124:
        return "0", 0
    if total <= 164:
        return "+1D4", 1
    if total <= 204:
        return "+1D6", 2
    extra = ((total - 205) // 80) + 2
    return f"+{extra}D6", extra + 1


def resolve_check(target: int, roll: int) -> CheckResult:
    if not 1 <= roll <= 100:
        raise ValueError("COC percentile roll must be between 1 and 100")
    target = max(0, target)
    half_target = floor(target / 2)
    fifth_target = floor(target / 5)
    if roll == 1:
        level: CheckLevel = "critical"
    elif roll == 100 or (target < 50 and roll >= 96):
        level = "fumble"
    elif roll <= fifth_target:
        level = "extreme"
    elif roll <= half_target:
        level = "hard"
    elif roll <= target:
        level = "regular"
    else:
        level = "failure"
    return CheckResult(target=target, roll=roll, level=level, half_target=half_target, fifth_target=fifth_target)
