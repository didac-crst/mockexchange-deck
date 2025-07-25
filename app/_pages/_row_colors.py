# _row_colors.py

import time
import pandas as pd

_BG0 = {
    "new":                 "#aa55ff",  # purple
    "partially_filled":    "#11AAFF",  # blue
    "filled":              "#00ff00",  # green
    "canceled":            "#ff5555",  # red
    "partially_canceled":  "#ff5555",
    "rejected":            "#ff5555",
    "expired":             "#ff5555",
}

def _color_interp(c0: str, t: float) -> str:
    """Interpolate hex color c0 toward black by fraction t (0–1)."""
    r0, g0, b0 = int(c0[1:3],16), int(c0[3:5],16), int(c0[5:7],16)
    r = round(r0 * (1-t))
    g = round(g0 * (1-t))
    b = round(b0 * (1-t))
    return f"#{r:02x}{g:02x}{b:02x}"

def contrast_text_color(bg_hex: str) -> str:
    """
    Given a background color in hex (“#RRGGBB”), return “#000000” or “#ffffff”
    for the text color that maximizes legibility.

    Uses the YIQ equation:
        yiq = (R*299 + G*587 + B*114) / 1000
    and picks black text if yiq ≥ 128, otherwise white.
    """
    # strip leading “#”, accept either 6- or 3-digit hex
    h = bg_hex.lstrip('#')
    if len(h) == 3:
        h = ''.join(ch*2 for ch in h)
    # parse channels
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    yiq = (r * 299 + g * 587 + b * 114) / 1000
    return "#000000" if yiq >= 128 else "#ffffff"

def _create_color_rows_degradation(levels: int = 3) -> tuple[dict, dict]:
    """
    Build a list of progressively darker background-/foreground palettes.
    `levels` ≥ 2  ⇒  palette[0] = original colours,
                      palette[-1] = solid black.
    """
    if levels < 2:
        raise ValueError("`N_VISUAL_DEGRADATIONS` must be at least 2")

    bg: dict[int, dict[str, str]] = {0: _BG0}
    # levels-1 intermediate fades, last one = black
    for j in range(1, levels):
        if j == levels - 1:
            # final step: everything black
            bg[j] = {k: "#000000" for k in _BG0}
        else:
            fade = j / (levels - 1)           # 0 < fade < 1
            bg[j] = {k: _color_interp(c, fade) for k, c in _BG0.items()}

    # derive a matching foreground (text) palette
    fg: dict[int, dict[str, str]] = {
        lvl: {k: contrast_text_color(c) for k, c in pal.items()}
        for lvl, pal in bg.items()
    }
    return bg, fg

def _row_style(
    row: pd.Series,
    *,
    levels: int = 3,
    fresh_window_s: float = 60,
) -> list[str]:
    """
    Apply one of N “faded‐out” color schemes depending on how long ago this
    row was updated.  bg_maps[0] is the freshest (no fade), bg_maps[1] a bit
    faded, … up to bg_maps[-1].  fg_maps (if provided) gives explicit text
    colors per bucket; otherwise we fall back to contrast_text_color().
    """
    bg_maps, fg_maps = _create_color_rows_degradation(levels)

    # Calculate “age” in seconds
    try:
        upd = row["Updated"]
        t_update = upd.timestamp() if isinstance(upd, pd.Timestamp) else pd.to_datetime(upd).timestamp()
    except Exception:
        return [""] * len(row)

    age = time.time() - t_update

    N = len(bg_maps)
    # which bucket?
    bucket = int(age // fresh_window_s)
    if bucket >= N:
        # too old → no style
        return [""] * len(row)

    # pick the right maps
    bg_map = bg_maps[bucket]
    fg_map = fg_maps[bucket] if fg_maps is not None else {}

    key = str(row["Status"]).lower().replace(" ", "_")
    bg = bg_map.get(key, "")
    if not bg:
        return [""] * len(row)

    # pick text color: explicit or contrast
    if key in fg_map:
        fg = fg_map[key]
    else:
        fg = contrast_text_color(bg)

    style = f"background-color:{bg};color:{fg}"
    return [style] * len(row)