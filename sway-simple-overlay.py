#!/bin/python3

import gi
import yaml
import os
import json
import subprocess
import signal
import argparse
import logging
from datetime import datetime
from pathlib import Path

gi.require_version("Gtk", "3.0")
gi.require_version("GtkLayerShell", "0.1")

from gi.repository import Gtk, Gdk, GLib, GtkLayerShell, Gio

# ---------------------------
# CONSTANTS
# ---------------------------
APP_NAME = "sway-simple-overlay"
CONFIG_FILENAME = "config.yaml"
CSS_FILENAME = "style.css"


# ---------------------------
# CLI
# ---------------------------
parser = argparse.ArgumentParser(description="Simple Sway Overlay")
parser.add_argument("--config", help="Path to config.yaml")
parser.add_argument("--css", help="Path to style.css")
parser.add_argument("--no-reload", action="store_true", help="Disable live reload")
parser.add_argument("--debug", action="store_true", help="Enable debug logs")
args = parser.parse_args()


# ---------------------------
# LOGGING
# ---------------------------
logging.basicConfig(
    level=logging.DEBUG if args.debug else logging.INFO,
    format="[%(levelname)s] %(message)s"
)

log = logging.getLogger("overlay")


# ---------------------------
# PATHS (XDG)
# ---------------------------
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
XDG_CONFIG_HOME = os.getenv("XDG_CONFIG_HOME") or os.path.join(Path.home(), ".config")
APP_DIR = os.path.join(XDG_CONFIG_HOME, APP_NAME)


# ---------------------------
# FILE LOOKUP
# ---------------------------
def find_first_file(filename, paths):
    for path in paths:
        if not path:
            continue
        candidate = os.path.join(path, filename)
        if os.path.exists(candidate):
            log.debug(f"Found {filename} at {candidate}")
            return candidate
    log.debug(f"{filename} not found in paths: {paths}")
    return None


# ---------------------------
# CONFIG
# ---------------------------
def resolve_config_path():
    if args.config:
        log.debug(f"Using config from CLI: {args.config}")
        return args.config

    return find_first_file(CONFIG_FILENAME, [
        SCRIPT_DIR,
        APP_DIR,
    ])


def load_config(config_path):
    if not config_path or not os.path.exists(config_path):
        log.warning("Config not found, using defaults")
        return {}
    with open(config_path, "r") as f:
        return yaml.safe_load(f) or {}


# ---------------------------
# CSS
# ---------------------------
def resolve_css_path(config):
    if args.css:
        log.debug(f"Using CSS from CLI: {args.css}")
        return args.css

    custom_path = config.get("css_path")
    if custom_path and os.path.exists(custom_path):
        log.debug(f"Using CSS from config: {custom_path}")
        return custom_path

    return find_first_file(CSS_FILENAME, [
        SCRIPT_DIR,
        APP_DIR,
    ])


def load_css(path):
    provider = Gtk.CssProvider()
    if path and os.path.exists(path):
        with open(path, "rb") as f:
            provider.load_from_data(f.read())
        log.debug(f"Loaded CSS from {path}")
    else:
        log.debug("No CSS file found, using empty style")
    return provider


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
        log.warning(f"Failed to get sway outputs: {e}")
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
    return configs[0] if configs else {}


# ---------------------------
# ASYNC COMMAND
# ---------------------------
class AsyncCommand:
    def __init__(self, command, callback):
        self.command = command
        self.callback = callback

    def run(self):
        try:
            self.proc = Gio.Subprocess.new(
                ["/bin/sh", "-c", self.command],
                Gio.SubprocessFlags.STDOUT_PIPE | Gio.SubprocessFlags.STDERR_PIPE
            )

            self.proc.communicate_utf8_async(
                None,
                None,
                self._on_done
            )

        except Exception:
            self.callback("[error]")

    def _on_done(self, proc, result):
        try:
            success, stdout, stderr = proc.communicate_utf8_finish(result)

            if success and stdout:
                self.callback(stdout.strip())
            else:
                self.callback("[error]")

        except Exception:
            self.callback("[error]")


# ---------------------------
# WINDOW
# ---------------------------
class ClockWindow(Gtk.Window):
    def __init__(self, monitor, config, css_provider):
        super().__init__()

        self.config = config
        self.labels = []
        self.timer_id = None
        self.running_commands = {}

        self.set_decorated(False)
        self.set_app_paintable(True)

        visual = self.get_screen().get_rgba_visual()
        if visual:
            self.set_visual(visual)

        GtkLayerShell.init_for_window(self)
        GtkLayerShell.set_layer(self, GtkLayerShell.Layer.TOP)
        GtkLayerShell.set_monitor(self, monitor)

        self.apply_position()

        self.box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        self.box.set_name("clock-box")
        self.add(self.box)

        parts = self.config.get("parts", []) or [{"name": "time", "format": "%H:%M:%S"}]

        for part in parts:
            lbl = Gtk.Label()
            lbl.set_xalign(0.5)
            lbl.get_style_context().add_class(part.get("name", "part"))
            self.box.pack_start(lbl, False, False, 0)
            self.labels.append((lbl, part))

        Gtk.StyleContext.add_provider_for_screen(
            self.get_screen(),
            css_provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

        self.apply_scale()
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

        for i, (lbl, part) in enumerate(self.labels):
            if "format" in part:
                lbl.set_text(now.strftime(part["format"]))

            elif "command" in part:
                cmd = part["command"]

                # prevent overlap
                if i in self.running_commands:
                    continue

                def make_callback(label, idx):
                    def callback(output):
                        label.set_text(output)
                        self.running_commands.pop(idx, None)
                    return callback

                async_cmd = AsyncCommand(cmd, make_callback(lbl, i))
                self.running_commands[i] = async_cmd
                async_cmd.run()

        return True


# ---------------------------
# APP
# ---------------------------
class ClockApp:
    def __init__(self):
        self.windows = []
        self.last_mtime = 0
        self.config_path = resolve_config_path()
        self.css_path = None

        config = load_config(self.config_path)
        live_reload = config.get("live_reload", True) and not args.no_reload
        log.debug(f"Live reload is {'enabled' if live_reload else 'disabled'}")
        
        if live_reload:
            GLib.timeout_add(1000, self.check_reload)
        
        self.reload()

    def clear_windows(self):
        for w in self.windows:
            w.destroy()
        self.windows.clear()

    def reload(self):
        self.config_path = resolve_config_path()
        config = load_config(self.config_path)

        self.css_path = resolve_css_path(config)
        self.live_reload = config.get("live_reload", True) and not args.no_reload

        css_provider = load_css(self.css_path)
        sway_outputs = get_sway_outputs()
        display = Gdk.Display.get_default()

        self.clear_windows()

        for i in range(display.get_n_monitors()):
            monitor = display.get_monitor(i)
            output_name = match_output_to_monitor(monitor, sway_outputs)
            monitor_conf = match_monitor_config(output_name, config.get("monitors", []))
            self.windows.append(ClockWindow(monitor, monitor_conf, css_provider))

        log.info("Overlay reloaded")

    def check_reload(self):
        if not self.live_reload:
            return True

        try:
            config_mtime = os.path.getmtime(self.config_path) if self.config_path else 0
            css_mtime = os.path.getmtime(self.css_path) if self.css_path else 0
            mtime = max(config_mtime, css_mtime)
        except Exception:
            return True

        if mtime != self.last_mtime:
            self.last_mtime = mtime
            self.reload()

        return True


# ---------------------------
# MAIN
# ---------------------------
def main():
    def handle_sigint(signum, frame):
        log.info("Exiting...")
        Gtk.main_quit()

    signal.signal(signal.SIGINT, handle_sigint)

    ClockApp()
    Gtk.main()


if __name__ == "__main__":
    main()