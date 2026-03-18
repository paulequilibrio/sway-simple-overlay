#!/bin/python3

import gi
import yaml
import os
import json
import subprocess
from datetime import datetime

gi.require_version("Gtk", "3.0")
gi.require_version("GtkLayerShell", "0.1")

from gi.repository import Gtk, Gdk, GLib, GtkLayerShell

CONFIG_PATH = "config.yaml"


# ---------------------------
# CONFIG
# ---------------------------
def load_config():
    with open(CONFIG_PATH, "r") as f:
        return yaml.safe_load(f)


# ---------------------------
# SWAY OUTPUTS
# ---------------------------
def get_sway_outputs():
    try:
        result = subprocess.run(
            ["swaymsg", "-t", "get_outputs", "-r"],
            capture_output=True,
            text=True,
            check=True
        )
        return json.loads(result.stdout)
    except Exception:
        return []


def match_output_to_monitor(monitor, sway_outputs):
    geo = monitor.get_geometry()

    for output in sway_outputs:
        rect = output.get("rect", {})
        if rect.get("x") == geo.x and rect.get("y") == geo.y:
            return output.get("name")

    return None


def match_monitor_config(output_name, configs):
    for conf in configs:
        if conf.get("name") == output_name:
            return conf

    for conf in configs:
        if conf.get("name") == "default":
            return conf

    return configs[0]


# ---------------------------
# WINDOW
# ---------------------------
class ClockWindow(Gtk.Window):
    def __init__(self, monitor, config, css_provider):
        super().__init__()

        self.config = config
        self.labels = []
        self.timer_id = None

        self.set_decorated(False)
        self.set_app_paintable(True)

        visual = self.get_screen().get_rgba_visual()
        if visual:
            self.set_visual(visual)

        GtkLayerShell.init_for_window(self)
        GtkLayerShell.set_layer(self, GtkLayerShell.Layer.TOP)
        GtkLayerShell.set_monitor(self, monitor)

        self.apply_position()

        # Root container
        self.box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        self.box.set_name("clock-box")
        self.add(self.box)

        # Parts system
        parts = self.config.get("parts", [])
        if not parts:
            parts = [{"name": "time", "format": self.config.get("format", "%H:%M:%S")}]

        for part in parts:
            lbl = Gtk.Label()
            lbl.set_xalign(0.5)
            lbl.get_style_context().add_class(part.get("name", "part"))

            self.box.pack_start(lbl, False, False, 0)
            self.labels.append((lbl, part.get("format", "%H:%M:%S")))

        # CSS
        Gtk.StyleContext.add_provider_for_screen(
            self.get_screen(),
            css_provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

        self.apply_scale()

        # Start timer
        self.start_timer()

        self.show_all()

    def start_timer(self):
        interval = float(self.config.get("refresh_interval", 1.0))
        interval_ms = int(interval * 1000)

        if self.timer_id:
            GLib.source_remove(self.timer_id)

        self.timer_id = GLib.timeout_add(interval_ms, self.update_time)
        self.update_time()

    def apply_position(self):
        anchors = self.config.get("anchor", ["top", "right"])
        margin = self.config.get("margin", [10, 10])

        edge_map = {
            "top": GtkLayerShell.Edge.TOP,
            "bottom": GtkLayerShell.Edge.BOTTOM,
            "left": GtkLayerShell.Edge.LEFT,
            "right": GtkLayerShell.Edge.RIGHT,
        }

        for edge in anchors:
            GtkLayerShell.set_anchor(self, edge_map[edge], True)

        if "top" in anchors:
            GtkLayerShell.set_margin(self, GtkLayerShell.Edge.TOP, margin[0])
        if "bottom" in anchors:
            GtkLayerShell.set_margin(self, GtkLayerShell.Edge.BOTTOM, margin[0])
        if "left" in anchors:
            GtkLayerShell.set_margin(self, GtkLayerShell.Edge.LEFT, margin[1])
        if "right" in anchors:
            GtkLayerShell.set_margin(self, GtkLayerShell.Edge.RIGHT, margin[1])

    def apply_scale(self):
        scale = self.config.get("scale", 1.0)

        css = f"""
        #clock-box {{
            font-size: {int(24 * scale)}px;
        }}
        """

        provider = Gtk.CssProvider()
        provider.load_from_data(css.encode())

        Gtk.StyleContext.add_provider_for_screen(
            self.get_screen(),
            provider,
            Gtk.STYLE_PROVIDER_PRIORITY_USER
        )

    def update_time(self):
        now = datetime.now()

        for lbl, fmt in self.labels:
            lbl.set_text(now.strftime(fmt))

        return True


# ---------------------------
# APP (LIVE RELOAD)
# ---------------------------
class ClockApp:
    def __init__(self):
        self.windows = []
        self.last_mtime = 0

        GLib.timeout_add(1000, self.check_reload)
        self.reload()

    def clear_windows(self):
        for w in self.windows:
            w.destroy()
        self.windows.clear()

    def reload(self):
        config = load_config()
        css_provider = load_css(config.get("css_path", "style.css"))
        sway_outputs = get_sway_outputs()

        display = Gdk.Display.get_default()

        self.clear_windows()

        for i in range(display.get_n_monitors()):
            monitor = display.get_monitor(i)

            output_name = match_output_to_monitor(monitor, sway_outputs)

            monitor_conf = match_monitor_config(
                output_name,
                config.get("monitors", [])
            )

            win = ClockWindow(monitor, monitor_conf, css_provider)
            self.windows.append(win)

    def check_reload(self):
        try:
            mtime = max(
                os.path.getmtime(CONFIG_PATH),
                os.path.getmtime("style.css")
            )
        except Exception:
            return True

        if mtime != self.last_mtime:
            self.last_mtime = mtime
            self.reload()

        return True


# ---------------------------
# CSS
# ---------------------------
def load_css(path):
    provider = Gtk.CssProvider()

    if os.path.exists(path):
        with open(path, "rb") as f:
            provider.load_from_data(f.read())

    return provider


# ---------------------------
# MAIN
# ---------------------------
def main():
    ClockApp()
    Gtk.main()


if __name__ == "__main__":
    main()