#!/bin/python3

import gi
gi.require_version("Gtk", "3.0")
gi.require_version("GtkLayerShell", "0.1")

from gi.repository import Gtk, GLib, GtkLayerShell
from datetime import datetime

class ClockOverlay(Gtk.Window):
    def __init__(self):
        super().__init__()

        self.set_decorated(False)
        self.set_app_paintable(True)
        self.set_keep_above(True)

        # Transparent background
        visual = self.get_screen().get_rgba_visual()
        if visual:
            self.set_visual(visual)

        # Init layer shell
        GtkLayerShell.init_for_window(self)

        # Put on overlay layer
        GtkLayerShell.set_layer(self, GtkLayerShell.Layer.TOP)

        # Anchor position (change these)
        GtkLayerShell.set_anchor(self, GtkLayerShell.Edge.TOP, True)
        GtkLayerShell.set_anchor(self, GtkLayerShell.Edge.RIGHT, True)

        GtkLayerShell.set_margin(self, GtkLayerShell.Edge.TOP, 20)
        GtkLayerShell.set_margin(self, GtkLayerShell.Edge.RIGHT, 20)

        # Label
        self.label = Gtk.Label()
        self.label.set_name("clock-label")
        self.add(self.label)

        # Load CSS
        self.load_css()

        # Update every second
        GLib.timeout_add_seconds(1, self.update_time)
        self.update_time()

        self.show_all()

    def load_css(self):
        css = b"""
        #clock-label {
            font-size: 24px;
            color: white;
            background-color: rgba(0, 0, 0, 0.3);
            padding: 10px;
            border-radius: 10px;
        }
        """

        provider = Gtk.CssProvider()
        provider.load_from_data(css)

        Gtk.StyleContext.add_provider_for_screen(
            self.get_screen(),
            provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

    def update_time(self):
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.label.set_text(now)
        return True


if __name__ == "__main__":
    app = ClockOverlay()
    Gtk.main()