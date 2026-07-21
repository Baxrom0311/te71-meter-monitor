from fastapi import APIRouter
from services import analytics as analytics_service

router = APIRouter(prefix="/api/public")


@router.get("/display")
async def public_display():
    """Ko'rgazma uchun ochiq endpoint — auth talab qilinmaydi."""
    electricity = await analytics_service.list_hourly_stats(utility_type="electricity", hours=24, limit=500)
    water = await analytics_service.list_hourly_stats(utility_type="water", hours=24, limit=500)
    gas = await analytics_service.list_hourly_stats(utility_type="gas", hours=24, limit=500)
    soil = await analytics_service.list_hourly_stats(utility_type="soil", hours=24, limit=500)
    return {
        "electricity": electricity["stats"],
        "water": water["stats"],
        "gas": gas["stats"],
        "soil": soil["stats"],
    }


@router.get("/display/kpi")
async def display_kpi():
    """ESP32 ekran qurilmasi uchun kompakt KPI — kichik JSON, auth yo'q.

    Har bir utility_type uchun oxirgi soatdagi eng so'nggi qiymatni qaytaradi.
    Javob hajmi ~300 bayt — ESP32 xotirasi uchun qulay.
    """
    def _latest(stats: list[dict]) -> dict:
        """Ro'yxatdan eng oxirgi bo'sh bo'lmagan qiymatlarni ajratib olish."""
        result: dict = {}
        for row in reversed(stats):
            for key, val in row.items():
                if key not in result and val is not None and key != "id":
                    result[key] = val
            if len(result) > 3:
                break
        return result

    elec  = await analytics_service.list_hourly_stats(utility_type="electricity", hours=2, limit=10)
    water = await analytics_service.list_hourly_stats(utility_type="water",       hours=2, limit=10)
    gas   = await analytics_service.list_hourly_stats(utility_type="gas",         hours=2, limit=10)
    soil  = await analytics_service.list_hourly_stats(utility_type="soil",        hours=2, limit=10)

    e = _latest(elec["stats"])
    w = _latest(water["stats"])
    g = _latest(gas["stats"])
    s = _latest(soil["stats"])

    return {
        "electricity": {
            "power_w":    e.get("avg_power_w"),
            "energy_kwh": e.get("max_energy_kwh"),
        },
        "water": {
            "pressure_bottom_bar": w.get("avg_pressure_bottom_bar"),
            "pressure_top_bar":    w.get("avg_pressure_top_bar"),
            "flow_rate":           w.get("avg_flow_rate"),
        },
        "gas": {
            "pressure_bar": g.get("avg_pressure_bar"),
            "flow_rate":    g.get("avg_flow_rate"),
        },
        "soil": {
            "humidity": s.get("avg_humidity"),
        },
    }
