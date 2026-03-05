import asyncio
import threading
import time
import os
import psutil
from lcu import get_lcu_session
from game_state import get_game_data, get_teammate_positions, calculate_distance, distance_to_volume
from voice import ProximityVoice

SERVER_URL = os.environ.get("PROXIMITY_SERVER", "http://localhost:3000")
POLL_INTERVAL = 0.5  # seconds between position updates

class ProximityApp:
    def __init__(self):
        self.voice = ProximityVoice(SERVER_URL)
        self.running = False
        self.in_game = False
        self.summoner_name = None
        self.match_id = None
        self.loop = None
        self.status = "idle"  # idle | connecting | connected | in_game | error

    def is_league_running(self):
        for proc in psutil.process_iter(['name']):
            try:
                if proc.info['name'] == 'LeagueClientUx.exe':
                    return True
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        return False

    def start(self):
        """Start the app — runs the main loop in a background thread."""
        self.running = True
        self.loop = asyncio.new_event_loop()

        thread = threading.Thread(target=self._run, daemon=True)
        thread.start()
        print("ProximityLoL started. Waiting for League...")

    def _run(self):
        asyncio.set_event_loop(self.loop)
        self.loop.run_until_complete(self._main_loop())

    async def _main_loop(self):
        while self.running:
            try:
                await self._tick()
            except Exception as e:
                print(f"Error in main loop: {e}")
            await asyncio.sleep(POLL_INTERVAL)

    async def _tick(self):
        # Step 1: Check if League is running
        if not self.is_league_running():
            if self.in_game:
                await self._on_game_end()
            self.status = "idle"
            return

        # Step 2: Get LCU session (summoner name + match state)
        session = get_lcu_session()
        if not session:
            self.status = "idle"
            return

        self.summoner_name = session['summoner_name']

        # Step 3: Check if we just entered a game
        if session['in_game'] and not self.in_game:
            self.match_id = session['match_id']
            await self._on_game_start()

        # Step 4: Check if we just left a game
        elif not session['in_game'] and self.in_game:
            await self._on_game_end()

        # Step 5: If in game, update proximity volumes
        if self.in_game and self.voice.running:
            await self._update_proximity()

    async def _on_game_start(self):
        print(f"Game started! Match ID: {self.match_id}")
        print(f"Connecting to voice as {self.summoner_name}...")
        self.status = "connecting"
        self.in_game = True
        self.voice._loop = self.loop

        try:
            await self.voice.connect(self.match_id, self.summoner_name)
            self.status = "connected"
            print("Voice connected!")
        except Exception as e:
            print(f"Voice connection failed: {e}")
            self.status = "error"

    async def _on_game_end(self):
        print("Game ended. Disconnecting voice...")
        self.in_game = False
        self.match_id = None
        self.status = "idle"
        await self.voice.disconnect()
        # Reset voice instance for next game
        self.voice = ProximityVoice(SERVER_URL)

    async def _update_proximity(self):
        """Poll game positions and update teammate volumes."""
        game_data = get_game_data()
        if not game_data:
            return

        my_pos = None
        # Find local player position
        for player in game_data.get('allPlayers', []):
            game_name = self.summoner_name.split('#')[0].lower()
            if player.get('riotId', '').split('#')[0].lower() == game_name:
                pos = player.get('position', {})
                my_pos = (pos.get('x', 0), pos.get('y', 0), pos.get('z', 0))
                break

        if not my_pos:
            return

        teammate_positions = get_teammate_positions(game_data, self.summoner_name)

        for riot_id, pos in teammate_positions.items():
            distance = calculate_distance(my_pos, pos)
            volume = distance_to_volume(distance)
            self.voice.set_participant_volume(riot_id, volume)

    def stop(self):
        """Stop the app cleanly."""
        print("Stopping ProximityLoL...")
        self.running = False
        if self.voice.running:
            asyncio.run_coroutine_threadsafe(
                self.voice.disconnect(), self.loop
            )


if __name__ == '__main__':
    app = ProximityApp()
    app.start()

    print("Running. Press Ctrl+C to stop.")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        app.stop()
        print("Stopped.")