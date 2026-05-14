"""
sjt_data.py
-----------
Silver Jubilee Tower (SJT) indoor layout data.
Contains floor-wise room ranges, lift/stair positions, wing layout,
and navigation logic for finding classrooms inside the block.

SJT Room Numbering Convention:
  - Ground floor: G01, G02, ... G30
  - 1st floor:    101, 102, ... 130
  - 2nd floor:    201, 202, ... 230
  - ...up to 8th floor: 801-830

Wing Layout (per floor):
  - Left Wing  (rooms xx01 – xx15) — West side
  - Right Wing (rooms xx16 – xx30) — East side

Entrances:
  - Main entrance: Ground floor centre
  - Side entrance:  Ground floor west

Lifts:   2 lifts at the centre of each floor (between wings)
Stairs:  2 staircases — one at each wing end (West staircase, East staircase)
"""

# ── Floor metadata ────────────────────────────────────────────────────────────

FLOORS = {
    "G": {"name": "Ground Floor", "level": 0,
           "departments": ["Admin Office", "Security", "Reception", "Exam Cell"]},
    "1": {"name": "1st Floor", "level": 1,
           "departments": ["SCOPE (School of Computer Science & Engineering)"]},
    "2": {"name": "2nd Floor", "level": 2,
           "departments": ["SCOPE Labs", "Smart Classrooms"]},
    "3": {"name": "3rd Floor", "level": 3,
           "departments": ["SITE (School of Information Technology & Engineering)"]},
    "4": {"name": "4th Floor", "level": 4,
           "departments": ["SITE Labs", "Faculty Cabins"]},
    "5": {"name": "5th Floor", "level": 5,
           "departments": ["SENSE (School of Electronics Engineering)"]},
    "6": {"name": "6th Floor", "level": 6,
           "departments": ["SENSE Labs", "Research Labs"]},
    "7": {"name": "7th Floor", "level": 7,
           "departments": ["Faculty Offices", "Conference Rooms"]},
    "8": {"name": "8th Floor", "level": 8,
           "departments": ["Seminar Halls", "Special Labs"]},
}

# ── Room numbering per floor ──────────────────────────────────────────────────

def get_rooms_for_floor(floor_key: str) -> list[str]:
    """Generate room numbers for a given floor key ('G', '1'-'8')."""
    rooms = []
    if floor_key == "G":
        for i in range(1, 31):
            rooms.append(f"G{i:02d}")
    else:
        base = int(floor_key) * 100
        for i in range(1, 31):
            rooms.append(str(base + i))
    return rooms


# ── Wing classification ───────────────────────────────────────────────────────

def get_wing(room_number: str) -> str:
    """Determine which wing a room is in."""
    pos = room_position(room_number)
    if pos is not None:
        return "Right Wing (East)" if pos["x"] >= 0.5 else "Left Wing (West)"
    num = _room_suffix(room_number)
    if num is None:
        return "Unknown"
    if 1 <= num <= 15:
        return "Left Wing (West)"
    elif 16 <= num <= 30:
        return "Right Wing (East)"
    return "Unknown"


def _room_suffix(room_number: str) -> int | None:
    """Extract trailing room number, e.g. 'G07' -> 7, '315' -> 15."""
    clean = room_number.strip().upper()
    if clean.startswith("G"):
        try:
            return int(clean[1:])
        except ValueError:
            return None
    try:
        return int(clean) % 100
    except ValueError:
        return None


def get_floor_key(room_number: str) -> str | None:
    """Extract floor key from room number, e.g. 'G07' -> 'G', '315' -> '3'."""
    clean = room_number.strip().upper()
    if clean.startswith("G"):
        return "G"
    try:
        val = int(clean)
        floor = val // 100
        if 1 <= floor <= 8:
            return str(floor)
    except ValueError:
        pass
    return None


# ── Fixed positions (relative grid for visual rendering) ──────────────────────
# These are fractional (0–1) positions on a floor plan canvas.
# x=0 is West, x=1 is East.  y=0 is North (corridor top), y=1 is South.


LIFTS = [
    {"id": "lift_west", "name": "West Lift", "x": 0.08, "y": 0.62, "icon": "L"},
    {"id": "lift_core_top", "name": "Core Lift (Upper)", "x": 0.50, "y": 0.40, "icon": "L"},
    {"id": "lift_core_bottom", "name": "Core Lift (Lower)", "x": 0.50, "y": 0.56, "icon": "L"},
    {"id": "lift_east_1", "name": "East Lift 1", "x": 0.95, "y": 0.70, "icon": "L"},
    {"id": "lift_east_2", "name": "East Lift 2", "x": 0.95, "y": 0.82, "icon": "L"},
    {"id": "lift_east_3", "name": "East Lift 3", "x": 0.95, "y": 0.92, "icon": "L"},
]


STAIRS = [
    {"id": "stair_nw", "name": "North-West Stair", "x": 0.30, "y": 0.12, "icon": "S"},
    {"id": "stair_ne", "name": "North-East Stair", "x": 0.70, "y": 0.12, "icon": "S"},
    {"id": "stair_core_upper", "name": "Core Upper Stair", "x": 0.45, "y": 0.35, "icon": "S"},
    {"id": "stair_core_lower", "name": "Core Lower Stair", "x": 0.45, "y": 0.51, "icon": "S"},
    {"id": "stair_east_1", "name": "East Lift 1 Stair", "x": 0.90, "y": 0.65, "icon": "S"},
]

WASHROOMS = [
    {"id": "wc_west", "name": "Washroom (West)", "x": 0.12, "y": 0.50, "icon": "🚻"},
    {"id": "wc_east", "name": "Washroom (East)", "x": 0.88, "y": 0.50, "icon": "🚻"},
]

ENTRANCE = {"id": "entrance", "name": "Main Entrance", "x": 0.50, "y": 1.0, "icon": "🚪"}


GROUND_ROOM_LAYOUT: dict[int, tuple[float, float]] = {
    # Bottom row (right)
    1: (0.68, 0.84),
    2: (0.76, 0.84),
    3: (0.84, 0.84),
    # Mid-right
    4: (0.80, 0.56),
    5: (0.68, 0.56),
    # Top-right
    9: (0.93, 0.30),
    10: (0.93, 0.20),
    # Bottom center-left
    14: (0.45, 0.84),
    # Top-left (girls washroom block)
    15: (0.20, 0.20),
    16: (0.20, 0.30),
    # Mid-left
    17: (0.18, 0.44),
    18: (0.28, 0.44),
    19: (0.18, 0.56),
    20: (0.28, 0.56),
}

STANDARD_ROOM_LAYOUT: dict[int, tuple[float, float]] = {
    # Top-right
    10: (0.90, 0.22),
    9: (0.90, 0.34),
    # Mid-right
    4: (0.70, 0.58),
    5: (0.80, 0.58),
    # Bottom row (right to mid)
    1: (0.50, 0.84),
    2: (0.60, 0.84),
    3: (0.72, 0.84),
    # Bottom-left cluster
    24: (0.12, 0.86),
    25: (0.12, 0.74),
    26: (0.24, 0.86),
    27: (0.34, 0.86),
    # Left column
    16: (0.12, 0.30),
    17: (0.12, 0.42),
    18: (0.24, 0.42),
    19: (0.12, 0.56),
    20: (0.24, 0.56),
}


def _layout_position(floor_key: str, suffix: int) -> dict | None:
    if floor_key == "G":
        pos = GROUND_ROOM_LAYOUT.get(suffix)
    else:
        pos = STANDARD_ROOM_LAYOUT.get(suffix)
    if pos is None:
        return None
    return {"x": round(pos[0], 3), "y": round(pos[1], 3)}


def room_position(room_number: str) -> dict | None:
    """
    Return (x, y) position of a room on the floor plan canvas.
    Uses the provided ground floor blueprint and the 1st-floor blueprint
    for floors 2-8.
    """
    suffix = _room_suffix(room_number)
    if suffix is None or suffix < 1 or suffix > 30:
        return None

    floor_key = get_floor_key(room_number)
    if floor_key is None:
        return None

    return _layout_position(floor_key, suffix)


# ── Navigation instructions ──────────────────────────────────────────────────

def get_navigation_steps(room_number: str) -> dict | None:
    """
    Generate step-by-step navigation instructions from SJT main entrance
    to the given room number.
    Returns dict with: floor, wing, room, steps[], nearest_lift, nearest_stair
    """
    floor_key = get_floor_key(room_number)
    if floor_key is None:
        return None

    clean = room_number.strip().upper()
    suffix = _room_suffix(room_number)
    if suffix is None or suffix < 1 or suffix > 30:
        return None

    floor_info = FLOORS.get(floor_key)
    if floor_info is None:
        return None

    wing = get_wing(room_number)
    pos = room_position(room_number)
    level = floor_info["level"]

    steps = []

    # Step 1: Enter building
    steps.append({
        "step": 1,
        "instruction": "Enter SJT through the **Main Entrance** on the Ground Floor.",
        "icon": "🚪"
    })

    # Step 2: Go to correct floor
    if level == 0:
        steps.append({
            "step": 2,
            "instruction": "You are on the **Ground Floor** — no need to go up.",
            "icon": "✅"
        })
    else:
        steps.append({
            "step": 2,
            "instruction": f"Take the **Central Lift** or **Staircase** to reach **{floor_info['name']}** (Level {level}).",
            "icon": "🛗" if level > 3 else "🪜"
        })

    # Step 3: Choose wing direction (use layout position when available)
    turn_left = None
    if pos is not None:
        turn_left = pos["x"] < 0.5
    else:
        turn_left = suffix <= 15

    if turn_left:
        steps.append({
            "step": 3,
            "instruction": f"Turn **LEFT** towards the **{wing}**.",
            "icon": "⬅️"
        })
    else:
        steps.append({
            "step": 3,
            "instruction": f"Turn **RIGHT** towards the **{wing}**.",
            "icon": "➡️"
        })

    # Step 4: Walk along corridor
    if pos is not None:
        corridor_side = "left side" if pos["y"] < 0.5 else "right side"
    else:
        corridor_side = "left side" if suffix % 2 == 1 else "right side"
    steps.append({
        "step": 4,
        "instruction": f"Walk along the corridor. Room **{clean}** is on the **{corridor_side}** of the hallway.",
        "icon": "🚶"
    })

    # Step 5: Arrival
    steps.append({
        "step": 5,
        "instruction": f"You have arrived at **Room {clean}**!",
        "icon": "📍"
    })

    # Nearest facilities (by distance when layout position is known)
    if pos is not None:
        def _dist(a, b):
            return (a["x"] - b["x"]) ** 2 + (a["y"] - b["y"]) ** 2
        nearest_lift = min(LIFTS, key=lambda l: _dist(pos, l))
        nearest_stair = min(STAIRS, key=lambda s: _dist(pos, s))
        nearest_wc = min(WASHROOMS, key=lambda w: _dist(pos, w))
    else:
        nearest_lift = LIFTS[0]
        if suffix <= 15:
            nearest_stair = STAIRS[0]  # West
            nearest_wc = WASHROOMS[0]
        else:
            nearest_stair = STAIRS[1]  # East
            nearest_wc = WASHROOMS[1]

    return {
        "room": clean,
        "floor_key": floor_key,
        "floor_name": floor_info["name"],
        "floor_level": level,
        "wing": wing,
        "departments": floor_info["departments"],
        "position": pos,
        "steps": steps,
        "nearest_lift": nearest_lift,
        "nearest_stair": nearest_stair,
        "nearest_washroom": nearest_wc,
    }


def validate_room(room_number: str) -> tuple[bool, str]:
    """Validate a room number input. Returns (is_valid, message)."""
    clean = room_number.strip().upper()
    if not clean:
        return False, "Please enter a room number."

    floor_key = get_floor_key(clean)
    if floor_key is None:
        return False, f"Invalid room number '{clean}'. Use format: G01-G30 (Ground) or 101-830 (Floors 1-8)."

    suffix = _room_suffix(clean)
    if suffix is None or suffix < 1 or suffix > 30:
        return False, f"Room number '{clean}' is out of range. Valid rooms per floor: 01–30."

    return True, f"Room {clean} found on {FLOORS[floor_key]['name']}."
