import os
import re
import base64
import psutil
import requests
import urllib3

# League's LCU uses a self-signed cert, suppress the warning
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def find_lockfile():
    """Find the League lockfile by locating the running process."""
    for proc in psutil.process_iter(['name', 'exe']):
        try:
            if proc.info['name'] == 'LeagueClientUx.exe':
                # Lockfile sits in the same directory as the executable
                league_dir = os.path.dirname(proc.info['exe'])
                lockfile_path = os.path.join(league_dir, 'lockfile')
                if os.path.exists(lockfile_path):
                    return lockfile_path
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return None

def parse_lockfile(lockfile_path):
    """Parse the lockfile to get port and password for LCU API."""
    with open(lockfile_path, 'r') as f:
        content = f.read()
    # Format: name:pid:port:password:protocol
    parts = content.split(':')
    return {
        'port': parts[2],
        'password': parts[3],
        'protocol': parts[4].strip()
    }

def get_lcu_session():
    """
    Returns summoner name and current match ID if in a game.
    Returns None if League isn't running or not in a game.
    """
    lockfile_path = find_lockfile()
    if not lockfile_path:
        return None

    try:
        lock = parse_lockfile(lockfile_path)
        port = lock['port']
        password = lock['password']

        # LCU uses basic auth with username 'riot'
        auth = base64.b64encode(f"riot:{password}".encode()).decode()
        headers = {'Authorization': f'Basic {auth}'}
        base_url = f"https://127.0.0.1:{port}"

        # Get current summoner name
        summoner_resp = requests.get(
            f"{base_url}/lol-summoner/v1/current-summoner",
            headers=headers,
            verify=False
        )
        summoner_resp.raise_for_status()
        summoner_name = f"{summoner_resp.json().get('gameName', '')}#{summoner_resp.json().get('tagLine', '')}"

        # Check if currently in a game
        gameflow_resp = requests.get(
            f"{base_url}/lol-gameflow/v1/session",
            headers=headers,
            verify=False
        )

        if gameflow_resp.status_code != 200:
            # Not in a game
            return {'summoner_name': summoner_name, 'match_id': None, 'in_game': False}

        gameflow = gameflow_resp.json()
        phase = gameflow.get('phase', '')
        in_game = phase == 'InProgress'

        match_id = None
        if in_game:
            match_id = str(gameflow.get('gameData', {}).get('gameId', ''))

        return {
            'summoner_name': summoner_name,
            'match_id': match_id,
            'in_game': in_game
        }

    except Exception as e:
        print(f"LCU error: {e}")
        return None


if __name__ == '__main__':
    # Quick test
    print("Looking for League client...")
    session = get_lcu_session()
    if session:
        print(f"Summoner: {session['summoner_name']}")
        print(f"In game: {session['in_game']}")
        print(f"Match ID: {session['match_id']}")
    else:
        print("League client not found or not running.")