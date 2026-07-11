"""Theme constants for the Meter Tool application.

Markaziy rang palitra va stil konstantalari. Barcha UI fayllari
inline rang qiymatlari o'rniga shu konstantalardan foydalanishi kerak.

styles.py dagi QSS tema bu konstantalarga asoslanadi.
"""


class Colors:
    """Asosiy rang palitra."""

    # ── Background ─────────────────────────────────────────────────
    BG_PRIMARY = "#f4f7fb"
    BG_SURFACE = "#ffffff"
    BG_SIDEBAR = "#172033"
    BG_INPUT = "#f8fafc"
    BG_HOVER = "#eef4ff"
    BG_CARD_HOVER = "#f8fbff"

    # ── Text ───────────────────────────────────────────────────────
    TEXT_PRIMARY = "#172033"
    TEXT_WHITE = "#ffffff"
    TEXT_MUTED = "#4b5b73"
    TEXT_DIMMED = "#667085"
    TEXT_SUBTLE = "#7b8797"

    # ── Accent ─────────────────────────────────────────────────────
    ACCENT_BLUE = "#1769e0"
    ACCENT_BLUE_DARK = "#1455b8"
    ACCENT_CYAN = "#0f8bbf"

    # ── Status ─────────────────────────────────────────────────────
    STATUS_OK = "#0f8a4b"
    STATUS_GREEN = "#0f8a4b"
    STATUS_GREEN_LIGHT = "#1f9d5a"
    STATUS_ERROR = "#c03535"
    STATUS_ERROR_DARK = "#9f2626"
    STATUS_ERROR_LIGHT = "#d94b4b"
    STATUS_WARN = "#b7791f"

    # ── Borders ────────────────────────────────────────────────────
    BORDER_DARK = "#d9e2ef"
    BORDER_MID = "#cfd8e6"
    BORDER_LIGHT = "#e6edf6"
    BORDER_BLUE = "#bad1f5"


class Fonts:
    """Shrift o'lchamlari va vaznlari."""

    SIZE_SMALL = "11px"
    SIZE_BODY = "12px"
    SIZE_NORMAL = "13px"
    SIZE_MEDIUM = "14px"
    SIZE_TITLE = "16px"
    SIZE_HEADER = "18px"
    SIZE_LARGE = "24px"
    SIZE_METRIC = "26px"
    SIZE_RELAY = "30px"

    WEIGHT_NORMAL = "400"
    WEIGHT_SEMIBOLD = "600"
    WEIGHT_BOLD = "700"
    WEIGHT_EXTRA_BOLD = "800"


class Spacing:
    """Margin va padding qiymatlari."""

    XS = "4px"
    SM = "8px"
    MD = "12px"
    LG = "16px"
    XL = "20px"
    XXL = "24px"

    BORDER_RADIUS_SMALL = "6px"
    BORDER_RADIUS = "8px"
    BORDER_RADIUS_LARGE = "12px"


def inline_style(**props) -> str:
    """Python dict dan inline stylesheet string yaratadi.

    Usage:
        label.setStyleSheet(inline_style(
            font_size=Fonts.SIZE_BODY,
            color=Colors.TEXT_MUTED,
            font_weight=Fonts.WEIGHT_BOLD,
        ))
    """
    parts = []
    for key, value in props.items():
        css_key = key.replace("_", "-")
        parts.append(f"{css_key}: {value};")
    return " ".join(parts)
