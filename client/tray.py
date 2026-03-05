import threading
import time
import pystray
from PIL import Image, ImageDraw
from app import ProximityApp

def create_icon_image(color):
    """
    Draw a simple circle icon in the given color.
    Green = connected, Yellow = connecting, Gray = idle, Red = error.
    """
    size = 64
    img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.ellipse([4, 4, size - 4, size - 4], fill=color)
    return img

COLORS = {
    "idle":       (120, 120, 120, 255),  # Gray
    "connecting": (255, 200, 0,   255),  # Yellow
    "connected":  (0,   200, 80,  255),  # Green
    "in_game":    (0,   200, 80,  255),  # Green
    "error":      (220, 50,  50,  255),  # Red
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
        self.icon = None

    def build_menu(self):
        return pystray.Menu(
            pystray.MenuItem(
                lambda text: STATUS_LABELS.get(self.app.status, "ProximityLoL"),
                None,
                enabled=False
            ),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Quit", self.quit)
        )

    def quit(self, icon, item):
        self.app.stop()
        self.icon.stop()

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

        # Start icon updater thread
        threading.Thread(target=self.update_icon_loop, daemon=True).start()

        print("ProximityLoL tray app running. Right-click the tray icon to quit.")
        self.icon.run()


if __name__ == '__main__':
    TrayApp().run()