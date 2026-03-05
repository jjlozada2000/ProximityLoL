import threading
import time
import pystray
from PIL import Image, ImageDraw
from app import ProximityApp
from ui import ProximityUI

def create_icon_image(color):
    """Draw a simple circle icon in the given color."""
    size = 64
    img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.ellipse([4, 4, size - 4, size - 4], fill=color)
    return img

COLORS = {
    "idle":       (120, 120, 120, 255),
    "connecting": (255, 200, 0,   255),
    "connected":  (0,   200, 80,  255),
    "in_game":    (0,   200, 80,  255),
    "error":      (220, 50,  50,  255),
}

STATUS_LABELS = {
    "idle":       "ProximityLoL — Waiting for League...",
    "connecting": "ProximityLoL — Connecting to voice...",
    "connected":  "ProximityLoL — Voice connected!",
    "in_game":    "ProximityLoL — In game",
    "error":      "ProximityLoL — Connection error",
}


class TrayApp:
    def __init__(self):
        self.app = ProximityApp()
        self.ui = ProximityUI(self.app)
        self.icon = None

    def build_menu(self):
        return pystray.Menu(
            pystray.MenuItem(
                lambda text: STATUS_LABELS.get(self.app.status, "ProximityLoL"),
                None,
                enabled=False
            ),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Show Window", self._show_window),
            pystray.MenuItem("Quit", self.quit)
        )

    def quit(self, icon=None, item=None):
        self.app.stop()
        self.ui._running = False
        if self.icon:
            self.icon.stop()

    def _show_window(self, icon=None, item=None):
        """Bring the UI window back if it was minimized."""
        if self.ui.root:
            self.ui.root.deiconify()
            self.ui.root.lift()

    def update_icon_loop(self):
        """Continuously update tray icon color based on app status."""
        last_status = None
        while self.icon:
            status = self.app.status
            if status != last_status:
                color = COLORS.get(status, COLORS["idle"])
                self.icon.icon = create_icon_image(color)
                self.icon.title = STATUS_LABELS.get(status, "ProximityLoL")
                last_status = status
            time.sleep(0.5)

    def run(self):
        self.app.start()

        self.icon = pystray.Icon(
            name="ProximityLoL",
            icon=create_icon_image(COLORS["idle"]),
            title="ProximityLoL — Waiting for League...",
            menu=self.build_menu()
        )

        # Run tray icon in background thread
        threading.Thread(target=self.icon.run, daemon=True).start()
        # Run icon color updater in background thread
        threading.Thread(target=self.update_icon_loop, daemon=True).start()

        print("ProximityLoL running. Close the window to minimize to tray.")
        # UI runs on main thread (required by tkinter)
        self.ui.start()

        # When UI window is closed, clean up
        self.quit()


if __name__ == '__main__':
    TrayApp().run()