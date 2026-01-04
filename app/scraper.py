import logging
from typing import List, Dict, Any, Optional

import requests
from bs4 import BeautifulSoup

LISTINGS_URL = "https://xivpf.com/listings"
REQUEST_HEADERS = {
    "User-Agent": "BetterPF/1.0 (+https://example.local)",
    "Accept": "text/html,application/xhtml+xml",
}

logger = logging.getLogger(__name__)

CATEGORY_MAP = {
    "DutyRoulette": "Duty Roulette",
    "Dungeons": "Dungeons",
    "Guildhests": "Guildhests",
    "Trials": "Trials",
    "Raids": "Raids",
    "HighEndDuty": "High-end Duty",
    "Pvp": "PvP",
    "GoldSaucer": "Gold Saucer",
    "Fates": "FATEs",
    "TreasureHunt": "Treasure Hunt",
    "TheHunt": "The Hunt",
    "GatheringForays": "Gathering Forays",
    "DeepDungeons": "Deep Dungeons",
    "AdventuringForays": "Field Operations",
    "V&C Dungeon Finder": "V&C Dungeon Finder",
    "None": "Other",
}

WORLD_TO_DC = {
    "Adamantoise": "Aether",
    "Cactuar": "Aether",
    "Faerie": "Aether",
    "Gilgamesh": "Aether",
    "Jenova": "Aether",
    "Midgardsormr": "Aether",
    "Sargatanas": "Aether",
    "Siren": "Aether",
    "Balmung": "Crystal",
    "Brynhildr": "Crystal",
    "Coeurl": "Crystal",
    "Diabolos": "Crystal",
    "Goblin": "Crystal",
    "Malboro": "Crystal",
    "Mateus": "Crystal",
    "Zalera": "Crystal",
    "Behemoth": "Primal",
    "Excalibur": "Primal",
    "Exodus": "Primal",
    "Famfrit": "Primal",
    "Hyperion": "Primal",
    "Lamia": "Primal",
    "Leviathan": "Primal",
    "Ultros": "Primal",
    "Halicarnassus": "Dynamis",
    "Maduin": "Dynamis",
    "Marilith": "Dynamis",
    "Seraph": "Dynamis",
    "Cuchulainn": "Dynamis",
    "Golem": "Dynamis",
    "Kraken": "Dynamis",
    "Rafflesia": "Dynamis",
    "Cerberus": "Chaos",
    "Louisoix": "Chaos",
    "Moogle": "Chaos",
    "Omega": "Chaos",
    "Phantom": "Chaos",
    "Ragnarok": "Chaos",
    "Sagittarius": "Chaos",
    "Spriggan": "Chaos",
    "Alpha": "Light",
    "Lich": "Light",
    "Odin": "Light",
    "Phoenix": "Light",
    "Raiden": "Light",
    "Shiva": "Light",
    "Twintania": "Light",
    "Zodiark": "Light",
    "Innocence": "Shadow",
    "Pixie": "Shadow",
    "Titania": "Shadow",
    "Tycoon": "Shadow",
    "Aegis": "Elemental",
    "Atomos": "Elemental",
    "Carbuncle": "Elemental",
    "Garuda": "Elemental",
    "Gungnir": "Elemental",
    "Kujata": "Elemental",
    "Tonberry": "Elemental",
    "Typhon": "Elemental",
    "Alexander": "Gaia",
    "Bahamut": "Gaia",
    "Durandal": "Gaia",
    "Fenrir": "Gaia",
    "Ifrit": "Gaia",
    "Ridill": "Gaia",
    "Tiamat": "Gaia",
    "Ultima": "Gaia",
    "Anima": "Mana",
    "Asura": "Mana",
    "Chocobo": "Mana",
    "Hades": "Mana",
    "Ixion": "Mana",
    "Masamune": "Mana",
    "Pandaemonium": "Mana",
    "Titan": "Mana",
    "Belias": "Meteor",
    "Mandragora": "Meteor",
    "Ramuh": "Meteor",
    "Shinryu": "Meteor",
    "Unicorn": "Meteor",
    "Valefor": "Meteor",
    "Yojimbo": "Meteor",
    "Zeromus": "Meteor",
    "Bismarck": "Materia",
    "Ravana": "Materia",
    "Sephirot": "Materia",
    "Sophia": "Materia",
    "Zurvan": "Materia",
}

JOB_MASKS = {
    "PLD": 256,
    "WAR": 1024,
    "DRK": 2097152,
    "GNB": 67108864,
    "WHM": 8192,
    "SCH": 131072,
    "AST": 4194304,
    "SGE": 536870912,
    "MNK": 512,
    "DRG": 2048,
    "NIN": 524288,
    "SAM": 8388608,
    "RPR": 268435456,
    "VPR": 1073741824,
    "BRD": 4096,
    "MCH": 1048576,
    "DNC": 134217728,
    "BLM": 16384,
    "SMN": 65536,
    "RDM": 16777216,
    "PCT": 2147483648,
    "BLU": 33554432,
}

TANK_MASK = JOB_MASKS["PLD"] | JOB_MASKS["WAR"] | JOB_MASKS["DRK"] | JOB_MASKS["GNB"]
HEALER_MASK = JOB_MASKS["WHM"] | JOB_MASKS["SCH"] | JOB_MASKS["AST"] | JOB_MASKS["SGE"]
DPS_MASK = (
    JOB_MASKS["MNK"]
    | JOB_MASKS["DRG"]
    | JOB_MASKS["NIN"]
    | JOB_MASKS["SAM"]
    | JOB_MASKS["RPR"]
    | JOB_MASKS["VPR"]
    | JOB_MASKS["BRD"]
    | JOB_MASKS["MCH"]
    | JOB_MASKS["DNC"]
    | JOB_MASKS["BLM"]
    | JOB_MASKS["SMN"]
    | JOB_MASKS["RDM"]
    | JOB_MASKS["PCT"]
    | JOB_MASKS["BLU"]
)


def _text_or_empty(node) -> str:
    if not node:
        return ""
    return node.get_text(strip=True)


def _parse_roles(raw: str) -> List[str]:
    if not raw:
        return []
    if raw.strip().isdigit():
        return _roles_from_mask(raw)
    return [role.strip() for role in raw.split(",") if role.strip()]


def _parse_num_parties(raw: str):
    if raw is None:
        return None
    try:
        return int(raw)
    except ValueError:
        return None


def _parse_party_composition(node) -> Dict[str, Dict[str, int]]:
    counts = {
        "tank": {"filled": 0, "total": 0},
        "healer": {"filled": 0, "total": 0},
        "dps": {"filled": 0, "total": 0},
        "flex": {"filled": 0, "total": 0},
    }
    slots = node.select(".party .slot")
    for slot in slots:
        classes = set(slot.get("class", []))
        if "total" in classes:
            continue
        role_classes = [role for role in ("tank", "healer", "dps") if role in classes]
        if not role_classes:
            continue
        role = role_classes[0] if len(role_classes) == 1 else "flex"
        counts[role]["total"] += 1
        if "filled" in classes:
            counts[role]["filled"] += 1
    return counts


def _parse_party_slots(node) -> List[Dict[str, Any]]:
    slots_data: List[Dict[str, Any]] = []
    slots = node.select(".party .slot")
    for slot in slots:
        classes = set(slot.get("class", []))
        if "total" in classes:
            continue
        role_classes = [role for role in ("tank", "healer", "dps") if role in classes]
        role = role_classes[0] if len(role_classes) == 1 else "flex"
        filled = "filled" in classes
        title = slot.get("title", "") or ""
        jobs = [job for job in title.split() if job.strip()]
        slots_data.append(
            {
                "role": role,
                "filled": filled,
                "jobs": jobs,
            }
        )
    return slots_data


def _normalize_category(raw: Optional[str]) -> str:
    if not raw:
        return ""
    return CATEGORY_MAP.get(raw, raw)


def _roles_from_mask(raw: str) -> List[str]:
    try:
        mask = int(raw)
    except ValueError:
        return []
    roles: List[str] = []
    if mask & TANK_MASK:
        roles.append("Tank")
    if mask & HEALER_MASK:
        roles.append("Healer")
    if mask & DPS_MASK:
        roles.append("DPS")
    return roles


def fetch_listings() -> List[Dict[str, Any]]:
    response = requests.get(LISTINGS_URL, headers=REQUEST_HEADERS, timeout=20)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")
    listing_nodes = soup.select("#listings > .listing")

    items: List[Dict[str, Any]] = []
    for node in listing_nodes:
        data_centre_raw = node.get("data-centre") or node.get("data-center")
        pf_category_raw = node.get("data-pf-category")
        joinable_raw = node.get("data-joinable-roles", "")
        world = _text_or_empty(node.select_one(".world .text") or node.select_one(".world"))
        data_centre = WORLD_TO_DC.get(world, data_centre_raw)
        party_comp = _parse_party_composition(node)
        party_slots = _parse_party_slots(node)
        items.append(
            {
                "data_centre": data_centre,
                "data_centre_raw": data_centre_raw,
                "pf_category": _normalize_category(pf_category_raw),
                "pf_category_raw": pf_category_raw,
                "num_parties": _parse_num_parties(node.get("data-num-parties")),
                "joinable_roles": _parse_roles(joinable_raw),
                "joinable_roles_raw": joinable_raw,
                "party_composition": party_comp,
                "party_slots": party_slots,
                "duty": _text_or_empty(node.select_one(".duty")),
                "creator": _text_or_empty(node.select_one(".creator")),
                "description": _text_or_empty(node.select_one(".description")),
                "world": world,
            }
        )

    logger.info("Fetched %d listings from xivpf.com", len(items))
    return items
