"""Theme constants for the Meter Tool application.

Markaziy rang palitra va stil konstantalari. Barcha UI fayllari
inline rang qiymatlari o'rniga shu konstantalardan foydalanishi kerak.

styles.py dagi QSS tema bu konstantalarga asoslanadi.
"""


class Colors:
    """Asosiy rang palitra."""

    # ── Background ─────────────────────────────────────────────────
    BG_PRIMARY = "#070913"
    BG_SURFACE = "#0b0f19"
    BG_SIDEBAR = "#03050a"
    BG_INPUT = "#0f172a"
    BG_HOVER = "#1e293b"
    BG_CARD_HOVER = "#0f1626"

    # ── Text ───────────────────────────────────────────────────────
    TEXT_PRIMARY = "#e2e8f0"
    TEXT_WHITE = "#ffffff"
    TEXT_MUTED = "#94a3b8"
    TEXT_DIMMED = "#667085"
    TEXT_SUBTLE = "#64748b"

    # ── Accent ─────────────────────────────────────────────────────
    ACCENT_BLUE = "#38bdf8"
    ACCENT_BLUE_DARK = "#0284c7"
    ACCENT_CYAN = "#1663d8"

    # ── Status ─────────────────────────────────────────────────────
    STATUS_OK = "#86efac"
    STATUS_GREEN = "#10b981"
    STATUS_GREEN_LIGHT = "#a7f3d0"
    STATUS_ERROR = "#f87171"
    STATUS_ERROR_DARK = "#cf2e2e"
    STATUS_ERROR_LIGHT = "#fca5a5"
    STATUS_WARN = "#f59e0b"

    # ── Borders ────────────────────────────────────────────────────
    BORDER_DARK = "#161e2e"
    BORDER_MID = "#1e293b"
    BORDER_LIGHT = "#24364f"
    BORDER_BLUE = "#1e3a5f"


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
