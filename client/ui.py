import tkinter as tk
from tkinter import ttk
import threading
import time

BG_COLOR = "#1a1a2e"
CARD_COLOR = "#16213e"
ACCENT_COLOR = "#0f3460"
GREEN = "#00c853"
RED = "#d32f2f"
YELLOW = "#ffab00"
TEXT_COLOR = "#e0e0e0"
MUTED_COLOR = "#666666"
FONT = ("Segoe UI", 10)
FONT_BOLD = ("Segoe UI", 10, "bold")
FONT_SMALL = ("Segoe UI", 8)


class PlayerCard:
    def __init__(self, parent, identity, on_mute, on_volume_change):
        self.identity = identity
        self.muted = False
        self.speaking = False
        self.volume = 100

        self.frame = tk.Frame(parent, bg=CARD_COLOR, pady=6, padx=10)
        self.frame.pack(fill=tk.X, pady=3, padx=8)

        # Left side: speaking indicator + name
        left = tk.Frame(self.frame, bg=CARD_COLOR)
        left.pack(side=tk.LEFT, fill=tk.Y)

        self.indicator = tk.Canvas(left, width=12, height=12, bg=CARD_COLOR, highlightthickness=0)
        self.indicator.pack(side=tk.LEFT, padx=(0, 8), pady=2)
        self._draw_indicator(False)

        self.name_label = tk.Label(left, text=identity, bg=CARD_COLOR, fg=TEXT_COLOR, font=FONT_BOLD)
        self.name_label.pack(side=tk.LEFT)

        # Right side: volume slider + mute button
        right = tk.Frame(self.frame, bg=CARD_COLOR)
        right.pack(side=tk.RIGHT)

        self.vol_var = tk.IntVar(value=100)
        self.volume_slider = ttk.Scale(
            right, from_=0, to=100, orient=tk.HORIZONTAL,
            variable=self.vol_var, length=80,
            command=lambda v: on_volume_change(identity, float(v))
        )
        self.volume_slider.pack(side=tk.LEFT, padx=(0, 8))

        self.vol_label = tk.Label(right, text="100%", bg=CARD_COLOR, fg=TEXT_COLOR, font=FONT_SMALL, width=4)
        self.vol_label.pack(side=tk.LEFT, padx=(0, 6))

        self.mute_btn = tk.Button(
            right, text="Mute", bg=ACCENT_COLOR, fg=TEXT_COLOR,
            font=FONT_SMALL, relief=tk.FLAT, padx=6, pady=2,
            command=lambda: on_mute(identity)
        )
        self.mute_btn.pack(side=tk.LEFT)

    def _draw_indicator(self, speaking):
        self.indicator.delete("all")
        color = GREEN if speaking else MUTED_COLOR
        self.indicator.create_oval(1, 1, 11, 11, fill=color, outline="")

    def set_speaking(self, speaking):
        if speaking != self.speaking:
            self.speaking = speaking
            self._draw_indicator(speaking)

    def set_muted(self, muted):
        self.muted = muted
        if muted:
            self.mute_btn.config(text="Unmute", bg=RED)
            self.name_label.config(fg=MUTED_COLOR)
        else:
            self.mute_btn.config(text="Mute", bg=ACCENT_COLOR)
            self.name_label.config(fg=TEXT_COLOR)

    def update_volume_label(self, value):
        self.vol_label.config(text=f"{int(float(value))}%")

    def destroy(self):
        self.frame.destroy()


class ProximityUI:
    def __init__(self, app):
        self.app = app  # Reference to ProximityApp
        self.root = None
        self.player_cards = {}  # { identity: PlayerCard }
        self.self_muted = False
        self._running = False

    def start(self):
        """Start the UI in the main thread."""
        self.root = tk.Tk()
        self.root.title("ProximityLoL")
        self.root.geometry("340x480")
        self.root.configure(bg=BG_COLOR)
        self.root.resizable(False, True)
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

        # Try to keep it on top but still minimizable
        self.root.attributes("-topmost", False)

        self._build_ui()
        self._running = True

        # Start update loop
        self.root.after(500, self._update_loop)
        self.root.mainloop()

    def _build_ui(self):
        # Header
        header = tk.Frame(self.root, bg=ACCENT_COLOR, pady=10)
        header.pack(fill=tk.X)

        tk.Label(
            header, text="🎮 ProximityLoL",
            bg=ACCENT_COLOR, fg=TEXT_COLOR, font=("Segoe UI", 13, "bold")
        ).pack(side=tk.LEFT, padx=12)

        self.status_label = tk.Label(
            header, text="● Idle",
            bg=ACCENT_COLOR, fg=MUTED_COLOR, font=FONT
        )
        self.status_label.pack(side=tk.RIGHT, padx=12)

        # Players section
        players_header = tk.Frame(self.root, bg=BG_COLOR)
        players_header.pack(fill=tk.X, padx=8, pady=(10, 4))

        tk.Label(
            players_header, text="CONNECTED PLAYERS",
            bg=BG_COLOR, fg=MUTED_COLOR, font=FONT_SMALL
        ).pack(side=tk.LEFT)

        self.player_count = tk.Label(
            players_header, text="0",
            bg=BG_COLOR, fg=MUTED_COLOR, font=FONT_SMALL
        )
        self.player_count.pack(side=tk.RIGHT)

        # Scrollable player list
        self.players_frame = tk.Frame(self.root, bg=BG_COLOR)
        self.players_frame.pack(fill=tk.BOTH, expand=True, pady=4)

        self.empty_label = tk.Label(
            self.players_frame,
            text="Waiting for teammates\nto connect...",
            bg=BG_COLOR, fg=MUTED_COLOR, font=FONT
        )
        self.empty_label.pack(pady=40)

        # Divider
        tk.Frame(self.root, bg=ACCENT_COLOR, height=1).pack(fill=tk.X, padx=8)

        # Bottom controls
        controls = tk.Frame(self.root, bg=BG_COLOR, pady=10)
        controls.pack(fill=tk.X, padx=8)

        # Self mute button
        self.self_mute_btn = tk.Button(
            controls, text="🎤  Mute Myself", bg=ACCENT_COLOR, fg=TEXT_COLOR,
            font=FONT_BOLD, relief=tk.FLAT, padx=12, pady=6,
            command=self._toggle_self_mute
        )
        self.self_mute_btn.pack(side=tk.LEFT)

        # Master volume
        master_vol_frame = tk.Frame(controls, bg=BG_COLOR)
        master_vol_frame.pack(side=tk.RIGHT)

        tk.Label(master_vol_frame, text="Master", bg=BG_COLOR, fg=TEXT_COLOR, font=FONT_SMALL).pack(side=tk.LEFT)

        self.master_vol_var = tk.IntVar(value=100)
        ttk.Scale(
            master_vol_frame, from_=0, to=100, orient=tk.HORIZONTAL,
            variable=self.master_vol_var, length=80,
            command=self._on_master_volume
        ).pack(side=tk.LEFT, padx=6)

        self.master_vol_label = tk.Label(
            master_vol_frame, text="100%", bg=BG_COLOR, fg=TEXT_COLOR, font=FONT_SMALL, width=4
        )
        self.master_vol_label.pack(side=tk.LEFT)

    def _update_loop(self):
        if not self._running:
            return
        self._sync_players()
        self._update_status()
        self.root.after(500, self._update_loop)

    def _sync_players(self):
        """Sync player cards with currently connected participants."""
        if not self.app.voice or not self.app.voice.room:
            self._clear_players()
            return

        room = self.app.voice.room
        current_identities = set()

        for identity, participant in room.remote_participants.items():
            current_identities.add(identity)
            if identity not in self.player_cards:
                self._add_player(identity)

        # Remove disconnected players
        for identity in list(self.player_cards.keys()):
            if identity not in current_identities:
                self._remove_player(identity)

        # Update empty label
        if self.player_cards:
            self.empty_label.pack_forget()
        else:
            self.empty_label.pack(pady=40)

        self.player_count.config(text=str(len(self.player_cards)))

    def _add_player(self, identity):
        card = PlayerCard(
            self.players_frame,
            identity,
            on_mute=self._mute_player,
            on_volume_change=self._on_player_volume
        )
        self.player_cards[identity] = card

    def _remove_player(self, identity):
        if identity in self.player_cards:
            self.player_cards[identity].destroy()
            del self.player_cards[identity]

    def _clear_players(self):
        for identity in list(self.player_cards.keys()):
            self._remove_player(identity)

    def _mute_player(self, identity):
        if identity in self.player_cards:
            card = self.player_cards[identity]
            card.set_muted(not card.muted)
            if card.muted:
                self.app.voice.set_participant_volume(identity, 0.0)
            else:
                vol = card.vol_var.get() / 100.0
                self.app.voice.set_participant_volume(identity, vol)

    def _on_player_volume(self, identity, value):
        if identity in self.player_cards:
            card = self.player_cards[identity]
            card.update_volume_label(value)
            if not card.muted:
                master = self.master_vol_var.get() / 100.0
                self.app.voice.set_participant_volume(identity, (value / 100.0) * master)

    def _on_master_volume(self, value):
        self.master_vol_label.config(text=f"{int(float(value))}%")
        master = float(value) / 100.0
        for identity, card in self.player_cards.items():
            if not card.muted:
                vol = card.vol_var.get() / 100.0
                self.app.voice.set_participant_volume(identity, vol * master)

    def _toggle_self_mute(self):
        self.self_muted = not self.self_muted
        if self.self_muted:
            self.self_mute_btn.config(text="🔇  Unmute Myself", bg=RED)
            self.app.voice.self_muted = True
        else:
            self.self_mute_btn.config(text="🎤  Mute Myself", bg=ACCENT_COLOR)
            self.app.voice.self_muted = False

    def _update_status(self):
        status = self.app.status
        status_map = {
            "idle":       ("● Idle",       MUTED_COLOR),
            "connecting": ("● Connecting", YELLOW),
            "connected":  ("● Connected",  GREEN),
            "in_game":    ("● In Game",    GREEN),
            "error":      ("● Error",      RED),
        }
        text, color = status_map.get(status, ("● Idle", MUTED_COLOR))
        self.status_label.config(text=text, fg=color)

    def _on_close(self):
        self._running = False
        self.root.destroy()