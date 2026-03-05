import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

LIVE_CLIENT_URL = "https://127.0.0.1:2999"

def get_game_data():
    """
    Fetch all game data from the Live Client Data API.
    Returns None if not in game.
    """
    try:
        resp = requests.get(
            f"{LIVE_CLIENT_URL}/liveclientdata/allgamedata",
            verify=False,
            timeout=1
        )
        resp.raise_for_status()
        data = resp.json()
        if not isinstance(data, dict):
            return None
        return data
        return resp.json()
    except Exception:
        return None

def get_player_positions(game_data):
    """
    Extract all player positions from game data.
    Returns a dict of { summonerName: (x, y, z) }
    """
    if not game_data:
        return {}

    positions = {}
    for player in game_data.get('allPlayers', []):
        name = f"{player.get('riotId', '')}"
        pos = player.get('position', {})
        x = pos.get('x', 0)
        y = pos.get('y', 0)
        z = pos.get('z', 0)
        positions[name] = (x, y, z)

    return positions

def get_local_player_team(game_data):
    """Get the team of the local player (ORDER or CHAOS)."""
    if not game_data:
        return None
    local = game_data.get('activePlayer', {})
    local_name = local.get('riotId', '')

    for player in game_data.get('allPlayers', []):
        if player.get('riotId', '') == local_name:
            return player.get('team', None)
    return None

def get_teammate_positions(game_data, local_summoner_name):
    """
    Returns positions of teammates only (excluding self).
    { summonerName: (x, y, z) }
    """
    if not game_data:
        return {}

    # Find local player's team
    local_team = None
    for player in game_data.get('allPlayers', []):
        riot_id = player.get('riotId', '')
        # Match by gameName part only in case of formatting differences
        game_name = local_summoner_name.split('#')[0].lower()
        if riot_id.split('#')[0].lower() == game_name:
            local_team = player.get('team')
            break

    if not local_team:
        return {}

    teammates = {}
    for player in game_data.get('allPlayers', []):
        riot_id = player.get('riotId', '')
        game_name = local_summoner_name.split('#')[0].lower()
        # Skip self
        if riot_id.split('#')[0].lower() == game_name:
            continue
        # Same team only
        if player.get('team') == local_team:
            pos = player.get('position', {})
            teammates[riot_id] = (
                pos.get('x', 0),
                pos.get('y', 0),
                pos.get('z', 0)
            )

    return teammates

def calculate_distance(pos1, pos2):
    """Euclidean distance between two (x, y, z) positions."""
    return ((pos1[0]-pos2[0])**2 + (pos1[1]-pos2[1])**2 + (pos1[2]-pos2[2])**2) ** 0.5

def distance_to_volume(distance, max_distance=3000.0):
    """
    Convert distance to a volume multiplier between 0.0 and 1.0.
    At 0 distance: full volume (1.0)
    At max_distance or beyond: silent (0.0)
    """
    if distance >= max_distance:
        return 0.0
    return 1.0 - (distance / max_distance)


if __name__ == '__main__':
    print("Polling Live Client Data API...")
    data = get_game_data()
    if data:
        print("In game!")
        positions = get_player_positions(data)
        for name, pos in positions.items():
            print(f"  {name}: {pos}")
    else:
        print("Not in game (start a game to test this module).")