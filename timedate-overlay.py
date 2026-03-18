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
    except Exception as e:
        print("Failed to query sway outputs:", e)
        return []


def match_output_to_monitor(monitor, sway_outputs):
    geo = monitor.get_geometry()
    mx, my = geo.x, geo.y

    for output in sway_outputs:
        rect = output.get("rect", {})
        if rect.get("x") == mx and rect.get("y") == my:
            return output.get("name")

    return None


def match_monitor_config(output_name, configs):
    if not output_name:
        output_name = ""

    # Exact match
    for conf in configs:
        if conf.get("name") == output_name:
            return conf

    # Default fallback
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

        self.set_decorated(False)
        self.set_app_paintable(True)

        # Transparency
        visual = self.get_screen().get_rgba_visual()
        if visual:
            self.set_visual(visual)

        # Layer shell
        GtkLayerShell.init_for_window(self)
        GtkLayerShell.set_layer(self, GtkLayerShell.Layer.TOP)
        GtkLayerShell.set_monitor(self, monitor)

        self.apply_position()

        if config.get("click_through", False):
            self.set_pass_through()

        # Label
        self.label = Gtk.Label()
        self.label.set_name("clock-label")
        self.add(self.label)

        # Apply CSS
        Gtk.StyleContext.add_provider_for_screen(
            self.get_screen(),
            css_provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

        # Apply scaling
        self.apply_scale()

        GLib.timeout_add_seconds(1, self.update_time)
        self.update_time()

        self.show_all()

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

        # Apply scaling via CSS override
        css = f"""
        #clock-label {{
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

    def set_pass_through(self):
        self.set_accept_focus(False)
        self.set_sensitive(False)

        surface = self.get_window()
        if surface:
            region = Gdk.Region()
            surface.input_shape_combine_region(region, 0, 0)

    def update_time(self):
        fmt = self.config.get("format", "%H:%M:%S")
        self.label.set_text(datetime.now().strftime(fmt))
        return True


# ---------------------------
# CSS
# ---------------------------
def load_css(path):
    provider = Gtk.CssProvider()

    if os.path.exists(path):
        with open(path, "rb") as f:
            provider.load_from_data(f.read())
    else:
        provider.load_from_data(b"")

    return provider


# ---------------------------
# MAIN
# ---------------------------
def main():
    config = load_config()
    css_provider = load_css(config.get("css_path", "style.css"))

    sway_outputs = get_sway_outputs()

    display = Gdk.Display.get_default()
    n_monitors = display.get_n_monitors()

    windows = []

    for i in range(n_monitors):
        monitor = display.get_monitor(i)

        output_name = match_output_to_monitor(monitor, sway_outputs)

        monitor_conf = match_monitor_config(
            output_name,
            config.get("monitors", [])
        )

        print(f"Monitor {i} → {output_name}")

        win = ClockWindow(monitor, monitor_conf, css_provider)
        windows.append(win)

    Gtk.main()


if __name__ == "__main__":
    main()