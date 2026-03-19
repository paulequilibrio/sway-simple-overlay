# Sway Simple Overlay

A lightweight, multi-monitor, live-updating overlay for Sway and wlroots-based Wayland compositors, built with Python and GTK3. Display the current time, date, or even the output of arbitrary shell commands on top of your windows — fully configurable, styleable, and efficient.

## Features

- Sway / wlroots overlay — pure Wayland, no XWayland needed
- Multi-monitor support — per-monitor configuration
- Live reload — auto-refresh on config or CSS changes
- Per-monitor scaling — adjust font size independently
- Multiple “parts” — display time, date, CPU usage, or any shell command
- Custom styling via CSS — control colors, fonts, and layout
- Configurable refresh interval — from sub-second to minutes
- Minimal and fast — written in Python, lightweight GTK3

## Requirements

- Python 3.8+
- GTK 3 (python3-gi, gir1.2-gtk-3.0)
- gtk-layer-shell (gir1.2-gtk-layer-shell-0.1)
- PyYAML
- Sway or any wlroots-based Wayland compositor

This project is specifically designed for Sway, although it may work on other wlroots compositors that implement the layer-shell protocol.

## Installation

- After install the dependencies in your system:

```shell
git clone https://github.com/paulequilibrio/sway-simple-overlay.git
cd sway-simple-overlay
chmod +x sway-simple-overlay.py
./sway-simple-overlay.py
```

## Configuration

### Configuration options

| Option             | Description                                                                                                  |
| ------------------ | ------------------------------------------------------------------------------------------------------------ |
| `name`             | Sway output name (e.g., `DP-1`) or `default`                                                                 |
| `anchor`           | List of edges: `"top"`, `"bottom"`, `"left"`, `"right"`                                                      |
| `margin`           | `[vertical, horizontal]` margin in pixels                                                                    |
| `scale`            | Font scaling factor                                                                                          |
| `refresh_interval` | Seconds between updates (can be fractional)                                                                  |
| `parts`            | List of items to display (time/date/shell command)                                                           |
| `format`           | `strftime` format string                                                                                     |
| `command`          | Shell command to run, stdout becomes label text                                                              |
| `css_path`         | Optional CSS path; if missing, searches in: 1) script directory 2) `~/.config/sway-simple-overlay/style.css` |
| `live_reload`      | `true` or `false` — enable/disable automatic reload on file changes                                          |



### Example config.yaml:

```yml
monitors:
  - name: "DP-1"
    anchor: ["top", "right"]
    margin: [20, 20]
    scale: 1.2
    refresh_interval: 1.0
    parts:
      - name: "time"
        format: "%H:%M:%S"
      - name: "date"
        format: "%Y-%m-%d"
      - name: "cpu"
        command: "grep 'cpu ' /proc/stat | awk '{usage=($2+$4)*100/($2+$4+$5)} END {print int(usage) \"%\"}'"
  - name: "default"
    anchor: ["top", "left"]
    margin: [10, 10]
    scale: 1.0
    refresh_interval: 5.0
    parts:
      - name: "time"
        format: "%H:%M"

css_path: "style.css"
live_reload: true
```

###  Styling (CSS)

The overlay uses GTK CSS.

- Each part corresponds to a CSS class (e.g., time, date, cpu).
- CSS can be placed anywhere in the paths defined above, or a custom path set with css_path.

Example style.css:

```css
#clock-box {
    background-color: rgba(0, 0, 0, 0.35);
    padding: 10px;
    border-radius: 10px;
}

.time {
    color: #00ffcc;
    font-size: 28px;
    font-weight: bold;
}

.date {
    color: #888;
    font-size: 16px;
}

.cpu {
    color: #ffcc00;
    font-size: 18px;
}
```

## Live Reload

Changes to `config.yaml` or `style.css` are applied automatically, no restart needed.
- Changes to config.yaml or the CSS file trigger automatic reload.
- Can be disabled by setting live_reload: false.
- CSS search order:
  - Path defined in css_path in the config
  - Same directory as the Python script (style.css)
  - Default XDG config path: ~/.config/sway-simple-overlay/style.css

## Notes

- Avoid slow shell commands — they block the overlay UI.
- Overlay is always on top, interactive click-through is not implemented.
- Works best on Sway, may partially work on other wlroots compositors.

## License

- MIT License

## Contributing

- Fork the repo
- Make your changes
- Open a pull request