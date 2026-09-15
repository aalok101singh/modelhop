from typing import Dict

TIER_COLORS: Dict[str, str] = {"free": "green", "mid": "yellow", "premium": "red"}
TIER_EMOJI: Dict[str, str] = {"free": ":free:", "mid": ":warning:", "premium": ":crown:"}
TIER_LABEL_EMOJI: Dict[str, str] = {"free": "FREE", "mid": "MID", "premium": "PREMIUM"}


def tier_color(tier_value: str) -> str:
    return TIER_COLORS.get(tier_value, "white")


def tier_emoji(tier_value: str) -> str:
    return TIER_EMOJI.get(tier_value, "")


def tier_label(tier_value: str) -> str:
    return TIER_LABEL_EMOJI.get(tier_value, tier_value.upper())
