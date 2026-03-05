import asyncio
import aiohttp
import os
from livekit import rtc
from livekit.rtc import AudioSource, LocalAudioTrack, AudioStream
import sounddevice as sd
import numpy as np
import threading

SAMPLE_RATE = 48000
NUM_CHANNELS = 1
CHUNK_DURATION_MS = 10
SAMPLES_PER_CHUNK = int(SAMPLE_RATE * CHUNK_DURATION_MS / 1000)


class ProximityVoice:
    def __init__(self, server_url):
        self.server_url = server_url
        self.room = None
        self.running = False
        self.self_muted = False
        self.participant_volumes = {}  # { identity: float 0.0-1.0 }
        self.audio_streams = {}        # { identity: AudioStream }
        self._loop = None

    async def get_token(self, match_id, summoner_name):
        """Request a LiveKit token from the signaling server."""
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.server_url}/token",
                json={"matchId": match_id, "summonerName": summoner_name}
            ) as resp:
                data = await resp.json()
                return data['token'], data['url']

    async def connect(self, match_id, summoner_name):
        """Connect to LiveKit room."""
        print(f"Requesting token for {summoner_name} in match {match_id}...")
        token, livekit_url = await self.get_token(match_id, summoner_name)

        self.room = rtc.Room()

        @self.room.on("participant_connected")
        def on_participant_connected(participant):
            print(f"Teammate connected: {participant.identity}")

        @self.room.on("participant_disconnected")
        def on_participant_disconnected(participant):
            print(f"Teammate disconnected: {participant.identity}")
            self.participant_volumes.pop(participant.identity, None)
            self.audio_streams.pop(participant.identity, None)

        @self.room.on("track_subscribed")
        def on_track_subscribed(track, publication, participant):
            if track.kind == rtc.TrackKind.KIND_AUDIO:
                print(f"Subscribed to audio from {participant.identity}")
                stream = AudioStream(track)
                self.audio_streams[participant.identity] = stream
                asyncio.ensure_future(
                    self._play_audio_stream(participant.identity, stream)
                )

        print(f"Connecting to LiveKit at {livekit_url}...")
        await self.room.connect(livekit_url, token)
        print(f"Connected to room: {self.room.name}")

        await self._publish_microphone()
        self.running = True

    async def _publish_microphone(self):
        """Capture mic input and publish to LiveKit."""
        source = AudioSource(SAMPLE_RATE, NUM_CHANNELS)
        track = LocalAudioTrack.create_audio_track("microphone", source)

        options = rtc.TrackPublishOptions()
        options.source = rtc.TrackSource.SOURCE_MICROPHONE
        await self.room.local_participant.publish_track(track, options)
        print("Microphone published.")

        threading.Thread(
            target=self._capture_mic,
            args=(source,),
            daemon=True
        ).start()

    def _capture_mic(self, source):
        """Capture microphone audio and push to LiveKit source."""
        def callback(indata, frames, time, status):
            if not self.running:
                raise sd.CallbackStop()

            if self.self_muted:
                # Send silence when muted
                frame = rtc.AudioFrame(
                    data=bytes(SAMPLES_PER_CHUNK * 2),
                    sample_rate=SAMPLE_RATE,
                    num_channels=NUM_CHANNELS,
                    samples_per_channel=SAMPLES_PER_CHUNK
                )
            else:
                audio_data = (indata[:, 0] * 32767).astype(np.int16)
                frame = rtc.AudioFrame(
                    data=audio_data.tobytes(),
                    sample_rate=SAMPLE_RATE,
                    num_channels=NUM_CHANNELS,
                    samples_per_channel=len(audio_data)
                )

            asyncio.run_coroutine_threadsafe(
                source.capture_frame(frame),
                self._loop
            )

        with sd.InputStream(
            samplerate=SAMPLE_RATE,
            channels=NUM_CHANNELS,
            dtype='float32',
            blocksize=SAMPLES_PER_CHUNK,
            callback=callback
        ):
            while self.running:
                sd.sleep(100)

    async def _play_audio_stream(self, identity, stream):
        """Play incoming audio from a participant, scaled by volume."""
        async for event in stream:
            if not self.running:
                break
            frame = event.frame
            volume = self.participant_volumes.get(identity, 1.0)

            audio_array = np.frombuffer(frame.data, dtype=np.int16).astype(np.float32)
            audio_array = audio_array * volume / 32767.0

            sd.play(audio_array, samplerate=SAMPLE_RATE, blocking=False)

    def set_participant_volume(self, identity, volume):
        """Set volume for a participant (0.0 = silent, 1.0 = full)."""
        self.participant_volumes[identity] = max(0.0, min(1.0, volume))

    async def disconnect(self):
        """Disconnect from the LiveKit room."""
        self.running = False
        if self.room:
            await self.room.disconnect()
            print("Disconnected from voice room.")

    def run(self, match_id, summoner_name, loop):
        """Entry point to start voice in an asyncio loop."""
        self._loop = loop
        loop.run_until_complete(self.connect(match_id, summoner_name))


if __name__ == '__main__':
    SERVER_URL = os.environ.get("PROXIMITY_SERVER", "http://localhost:3000")
    voice = ProximityVoice(SERVER_URL)

    loop = asyncio.new_event_loop()
    voice._loop = loop

    async def test():
        try:
            token, url = await voice.get_token("test123", "poob#0713")
            print(f"Token fetch OK")
            print(f"LiveKit URL: {url}")
        except Exception as e:
            print(f"Error: {e}")

    loop.run_until_complete(test())