import json
import logging
import os
from typing import Any

import google.generativeai as genai
import httpx
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from core.config import settings
from core.security import current_token_payload
from core.time import now_ts
from models.schemas import ChatProvider, ChatRequest
from services import analytics, monitoring
from services import devices as device_service
from services import buildings as building_service
from services.alerts import get_alerts, clear_all_alerts, list_alert_rules
from services import audit as audit_service
from services.commands import create_relay_command, reboot_device, list_commands

router = APIRouter(prefix="/api", tags=["chat"])
logger = logging.getLogger(__name__)

ADMIN_TOOL_NAMES = {"reboot_tool", "relay_control_tool", "clear_alerts_tool"}

SENSITIVE_PROMPT_MARKERS = {
    "select ",
    "insert ",
    "update ",
    "delete ",
    "drop ",
    "alter ",
    "pragma",
    "sqlite_master",
    "information_schema",
    "password_hash",
    "api_token_hash",
    "secret_key",
    "device_api_token",
    "access_token",
    "refresh_token",
}


def _json(data: Any, max_chars: int = 12000) -> str:
    text = json.dumps(data, default=str, ensure_ascii=False)
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + "... [truncated]"


def _int(value: Any, default: int, min_value: int | None = None, max_value: int | None = None) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = default
    if min_value is not None:
        parsed = max(parsed, min_value)
    if max_value is not None:
        parsed = min(parsed, max_value)
    return parsed


def _granularity(value: Any) -> str:
    return "hour" if value == "hour" else "day"


def _safe_tool_args(args: dict[str, Any]) -> dict[str, Any]:
    safe: dict[str, Any] = {}
    for key, value in args.items():
        lowered = key.lower()
        if any(marker in lowered for marker in ("token", "password", "secret", "key")):
            safe[key] = "***"
        else:
            safe[key] = value
    return safe


def _looks_sensitive_prompt(message: str) -> bool:
    lowered = message.lower()
    return any(marker in lowered for marker in SENSITIVE_PROMPT_MARKERS)


async def _audit_chat_event(user: dict, action: str, detail: dict[str, Any] | None = None) -> None:
    try:
        await audit_service.record(user, action, "chat", None, detail)
    except Exception as exc:
        logger.warning("chat audit failed: %s", exc)


# ─── Tool implementations ─────────────────────────────────────────────────────

async def system_summary_tool() -> str:
    return _json(await monitoring.summary())


async def active_alerts_tool(limit: int = 20) -> str:
    result = await get_alerts(device_id=None, kind=None, cleared=False, limit=_int(limit, 20, 1, 100))
    return _json(result.get("alerts", []))


async def energy_by_building_tool(
    from_ts: int = 0,
    to_ts: int = 0,
    building_id: int = 0,
    granularity: str = "day",
) -> str:
    raw_end_ts = _int(to_ts, 0, 0)
    end_ts = raw_end_ts or now_ts()
    raw_start_ts = _int(from_ts, 0, 0)
    start_ts = raw_start_ts or end_ts - 30 * 86400
    return _json(
        await analytics.energy_by_building(
            from_ts=start_ts,
            to_ts=end_ts,
            building_id=_int(building_id, 0, 0) or None,
            granularity=_granularity(granularity),
        )
    )


async def buildings_energy_summary_tool() -> str:
    return _json(await analytics.buildings_energy_summary())


async def device_stats_tool(device_id: str, hours: int = 24) -> str:
    if not device_id:
        return "Xato: device_id kerak."
    return _json(await analytics.reading_stats(device_id=device_id, hours=_int(hours, 24, 1, 720)))


async def building_analytics_tool(building_id: int, hours: int = 24) -> str:
    parsed_building_id = _int(building_id, 0, 0)
    if not parsed_building_id:
        return "Xato: building_id kerak."
    return _json(await analytics.building_analytics(parsed_building_id, _int(hours, 24, 1, 720)))


async def list_devices_tool(utility_type: str = "", online_only: bool = False) -> str:
    """Barcha qurilmalar ro'yxati: holati, tur, bino, oxirgi ko'rsatkich vaqti."""
    result = await device_service.list_devices(
        online=True if online_only else None,
        utility_type=utility_type.strip() or None,
    )
    devices = result.get("devices", [])
    # Faqat kerakli maydonlarni qaytaramiz (token_hash va shunga o'xshashlarni olib tashlaymiz)
    safe_fields = [
        "device_id", "label", "meter_type", "utility_type", "firmware_mode",
        "building_id", "building_text", "floor_text", "group_name",
        "online", "last_seen", "fw_version", "meter_serial",
    ]
    safe_devices = [{k: d[k] for k in safe_fields if k in d} for d in devices]
    return _json({"devices": safe_devices, "total": len(safe_devices)})


async def list_buildings_tool() -> str:
    """Barcha binolar ro'yxati: nomi, manzili, kommunal turlari."""
    result = await building_service.list_buildings()
    return _json(result)


async def get_device_details_tool(device_id: str) -> str:
    """Bitta qurilma to'liq ma'lumoti: holati, so'nggi o'qish, statistika."""
    if not device_id:
        return "Xato: device_id kerak."
    try:
        device = await device_service.get_device(device_id)
        safe_fields = [
            "device_id", "label", "meter_type", "utility_type", "firmware_mode",
            "building_id", "building_text", "floor_text", "group_name",
            "online", "last_seen", "fw_version", "meter_serial", "is_active",
        ]
        safe_device = {k: device[k] for k in safe_fields if k in device}
        stats = await analytics.reading_stats(device_id=device_id, hours=24)
        return _json({"device": safe_device, "stats_24h": stats})
    except Exception as exc:
        return f"Xato: {exc}"


async def list_commands_tool(device_id: str = "", status: str = "", limit: int = 20) -> str:
    """Qurilmaga yuborilgan buyruqlar tarixi (reboot, relay va boshqalar)."""
    result = await list_commands(
        device_id=device_id.strip() or None,
        status=status.strip() or None,
        limit=_int(limit, 20, 1, 100),
        offset=0,
    )
    return _json(result)


async def alert_rules_tool(utility_type: str = "") -> str:
    """Ogohlantirish qoidalari (elektr, suv, gaz bo'yicha chegaralar)."""
    result = await list_alert_rules(
        utility_type=utility_type.strip() or None,
        enabled=None,
        limit=100,
    )
    return _json(result)


async def reboot_tool(device_id: str, user: dict) -> str:
    if user.get("role") != "admin":
        return "Xato: device reboot faqat admin uchun ruxsat etilgan."
    if not device_id:
        return "Xato: device_id kerak."
    result = await reboot_device(device_id)
    return _json({"ok": True, "device_id": device_id, "cmd_id": result.get("cmd_id")})


async def relay_control_tool(device_id: str, action: str, user: dict) -> str:
    if user.get("role") != "admin":
        return "Xato: relay boshqarish faqat admin uchun ruxsat etilgan."
    if action not in {"on", "off"}:
        return "Xato: action faqat 'on' yoki 'off' bo'lishi mumkin."
    if not device_id:
        return "Xato: device_id kerak."
    result = await create_relay_command(device_id, action)
    return _json({"ok": True, "device_id": device_id, "action": action, "cmd_id": result.get("cmd_id")})


async def clear_alerts_tool(device_id: str, user: dict) -> str:
    """Admin: qurilma yoki barcha qurilmalar ogohlantirishlarini tozalash."""
    if user.get("role") != "admin":
        return "Xato: ogohlantirishlarni tozalash faqat admin uchun ruxsat etilgan."
    result = await clear_all_alerts(device_id.strip() or None)
    target = f"'{device_id}' qurilmasi" if device_id.strip() else "barcha qurilmalar"
    return _json({"ok": True, "message": f"{target} ogohlantirishlari tozalandi."})


async def execute_tool(name: str, args: dict[str, Any], user: dict) -> str:
    await _audit_chat_event(
        user,
        "chat.admin_tool" if name in ADMIN_TOOL_NAMES else "chat.tool",
        {
            "tool": name,
            "args": _safe_tool_args(args),
            "role": user.get("role"),
            "allowed": name not in ADMIN_TOOL_NAMES or user.get("role") == "admin",
        },
    )
    try:
        match name:
            case "system_summary_tool":
                return await system_summary_tool()
            case "active_alerts_tool":
                return await active_alerts_tool(args.get("limit", 20))
            case "energy_by_building_tool":
                return await energy_by_building_tool(
                    args.get("from_ts", 0),
                    args.get("to_ts", 0),
                    args.get("building_id", 0),
                    args.get("granularity", "day"),
                )
            case "buildings_energy_summary_tool":
                return await buildings_energy_summary_tool()
            case "device_stats_tool":
                return await device_stats_tool(args.get("device_id", ""), args.get("hours", 24))
            case "building_analytics_tool":
                return await building_analytics_tool(args.get("building_id", 0), args.get("hours", 24))
            case "list_devices_tool":
                return await list_devices_tool(args.get("utility_type", ""), args.get("online_only", False))
            case "list_buildings_tool":
                return await list_buildings_tool()
            case "get_device_details_tool":
                return await get_device_details_tool(args.get("device_id", ""))
            case "list_commands_tool":
                return await list_commands_tool(
                    args.get("device_id", ""),
                    args.get("status", ""),
                    args.get("limit", 20),
                )
            case "alert_rules_tool":
                return await alert_rules_tool(args.get("utility_type", ""))
            case "reboot_tool":
                return await reboot_tool(args.get("device_id", ""), user)
            case "relay_control_tool":
                return await relay_control_tool(args.get("device_id", ""), args.get("action", ""), user)
            case "clear_alerts_tool":
                return await clear_alerts_tool(args.get("device_id", ""), user)
            case _:
                return f"Xato: Noma'lum funksiya '{name}'"
    except Exception as exc:
        logger.exception("chat tool failed: %s", name)
        return f"Xato: {exc}"


# ─── Tool schemas (DeepSeek / OpenAI format) ──────────────────────────────────

DEEPSEEK_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "system_summary_tool",
            "description": (
                "Tizim umumiy holati: qurilmalar soni (online/offline), aktiv ogohlantirishlar, "
                "oxirgi soatdagi o'qishlar, umumiy energiya, binolar va o'lchov nuqtalari soni."
            ),
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_devices_tool",
            "description": (
                "Qurilmalar ro'yxati: ID, nomi, turi (elektr/suv/gaz), bino, online holati, "
                "firmware versiyasi, hisoblagich seriya raqami. "
                "utility_type bo'yicha filter: 'electricity', 'water', 'gas'."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "utility_type": {
                        "type": "string",
                        "enum": ["", "electricity", "water", "gas"],
                        "description": "Bo'sh = hammasi",
                    },
                    "online_only": {"type": "boolean", "description": "True = faqat onlayn qurilmalar"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_buildings_tool",
            "description": "Barcha binolar ro'yxati: nomi, manzili, kommunal turlari (elektr/suv/gaz).",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_device_details_tool",
            "description": (
                "Bitta qurilma to'liq ma'lumoti: holati, so'nggi 24 soat statistikasi "
                "(kuchlanish, tok, quvvat — elektr; bosim — suv/gaz)."
            ),
            "parameters": {
                "type": "object",
                "properties": {"device_id": {"type": "string"}},
                "required": ["device_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "active_alerts_tool",
            "description": "Aktiv (tozalanmagan) ogohlantirishlar ro'yxati — barcha kommunal turlar uchun.",
            "parameters": {
                "type": "object",
                "properties": {"limit": {"type": "integer", "minimum": 1, "maximum": 100}},
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "alert_rules_tool",
            "description": (
                "Ogohlantirish qoidalari: kommunal tur, chegara qiymatlari (min/max), "
                "og'irlik darajasi, yoqilgan/o'chirilgan holati."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "utility_type": {
                        "type": "string",
                        "enum": ["", "electricity", "water", "gas"],
                        "description": "Bo'sh = barcha turlar",
                    }
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "energy_by_building_tool",
            "description": "Elektr iste'moli binolar bo'yicha vaqt oralig'ida (soat yoki kun granulatsiyada).",
            "parameters": {
                "type": "object",
                "properties": {
                    "from_ts": {"type": "integer", "description": "Boshlanish Unix timestamp (0 = 30 kun oldin)"},
                    "to_ts": {"type": "integer", "description": "Tugash Unix timestamp (0 = hozir)"},
                    "building_id": {"type": "integer", "description": "0 = barcha binolar"},
                    "granularity": {"type": "string", "enum": ["hour", "day"]},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "buildings_energy_summary_tool",
            "description": "30 kunlik elektr iste'moli xulosasi — barcha binolar bo'yicha.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "device_stats_tool",
            "description": (
                "Bitta qurilma so'nggi N soatdagi o'rtacha/min/max ko'rsatkichlari: "
                "elektr (V, A, W, kWh) yoki suv/gaz (bar bosim, flow rate)."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "device_id": {"type": "string"},
                    "hours": {"type": "integer", "minimum": 1, "maximum": 720},
                },
                "required": ["device_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "building_analytics_tool",
            "description": "Bitta bino uchun elektr, suv, gaz va ogohlantirishlar tahlili.",
            "parameters": {
                "type": "object",
                "properties": {
                    "building_id": {"type": "integer"},
                    "hours": {"type": "integer", "minimum": 1, "maximum": 720},
                },
                "required": ["building_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_commands_tool",
            "description": "Qurilmalarga yuborilgan buyruqlar tarixi (reboot, relay yoqish/o'chirish va boshqalar).",
            "parameters": {
                "type": "object",
                "properties": {
                    "device_id": {"type": "string", "description": "Bo'sh = barcha qurilmalar"},
                    "status": {
                        "type": "string",
                        "enum": ["", "pending", "sent", "done", "failed", "expired"],
                        "description": "Bo'sh = barcha holatlar",
                    },
                    "limit": {"type": "integer", "minimum": 1, "maximum": 100},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "reboot_tool",
            "description": "FAQAT ADMIN: qurilmani qayta ishga tushirish buyrug'i yuborish.",
            "parameters": {
                "type": "object",
                "properties": {"device_id": {"type": "string"}},
                "required": ["device_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "relay_control_tool",
            "description": "FAQAT ADMIN: elektr hisoblagich relay yoqish ('on') yoki o'chirish ('off') buyrug'i.",
            "parameters": {
                "type": "object",
                "properties": {
                    "device_id": {"type": "string"},
                    "action": {"type": "string", "enum": ["on", "off"]},
                },
                "required": ["device_id", "action"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "clear_alerts_tool",
            "description": "FAQAT ADMIN: qurilma yoki barcha qurilmalar ogohlantirishlarini tozalash.",
            "parameters": {
                "type": "object",
                "properties": {
                    "device_id": {"type": "string", "description": "Bo'sh = barcha qurilmalar ogohlantirishlari tozalanadi"}
                },
            },
        },
    },
]


def _build_system_prompt(user: dict) -> str:
    role = user.get("role", "viewer")
    username = user.get("username", "foydalanuvchi")

    capabilities_by_role = (
        "Siz ADMIN sifatida kirgan holda quyidagi amallarni bajara olasiz:\n"
        "- Barcha ma'lumotlarni ko'rish (qurilmalar, binolar, o'qishlar, ogohlantirishlar)\n"
        "- Qurilmani qayta ishga tushirish (reboot_tool)\n"
        "- Elektr relay yoqish/o'chirish (relay_control_tool)\n"
        "- Ogohlantirishlarni tozalash (clear_alerts_tool)\n"
        "- Buyruqlar tarixini ko'rish (list_commands_tool)"
        if role == "admin"
        else
        "Siz FOYDALANUVCHI sifatida kirgan holda quyidagi amallarni bajara olasiz:\n"
        "- Barcha ma'lumotlarni ko'rish (qurilmalar, binolar, o'qishlar, ogohlantirishlar)\n"
        "- Statistika va tahlil ma'lumotlarini olish\n"
        "Relay boshqarish, reboot va ogohlantirishlarni tozalash — faqat admin uchun."
    )

    return (
        f"Siz kommunal monitoring tizimining AI yordamchisisiz.\n"
        f"Tizim elektr (kWh, W, V, A, Hz, power factor), suv (bar bosim, flow rate) va "
        f"gaz (bar bosim) hisoblagichlarini real vaqtda kuzatadi.\n\n"
        f"Joriy foydalanuvchi: {username} ({role})\n"
        f"{capabilities_by_role}\n\n"
        "Qoidalar:\n"
        "- Javoblar faqat o'zbek tilida, aniq va qisqa bo'lsin.\n"
        "- Ma'lumot kerak bo'lsa avval tegishli tool orqali so'rang.\n"
        "- Qurilma ID ni bilmasang avval list_devices_tool yoki system_summary_tool dan foydalaning.\n"
        "- SQL, jadval nomlari, parol/token/API kalit so'rasa rad eting.\n"
        "- Admin amallari (relay, reboot, clear) ni bajarishdan oldin foydalanuvchidan tasdiqlashni so'rang.\n"
        f"Hozirgi server vaqti (Unix): {now_ts()}."
    )


# ─── Gemini flow ──────────────────────────────────────────────────────────────

async def execute_gemini_flow(body: ChatRequest, user: dict):
    api_key = settings.gemini_api_key or os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise Exception("GEMINI_API_KEY sozlanmagan. AI Chatdan foydalanish uchun kalit kerak!")

    genai.configure(api_key=api_key)

    # Stub funksiyalar — Gemini tool discovery uchun (haqiqiy bajariluv execute_tool orqali)
    def system_summary_tool() -> str:
        """Tizim umumiy holati: qurilmalar, ogohlantirishlar, o'qishlar, energiya."""

    def list_devices_tool(utility_type: str = "", online_only: bool = False) -> str:
        """Qurilmalar ro'yxati. utility_type: 'electricity', 'water', 'gas' yoki bo'sh."""

    def list_buildings_tool() -> str:
        """Barcha binolar ro'yxati."""

    def get_device_details_tool(device_id: str) -> str:
        """Bitta qurilma to'liq ma'lumoti va 24 soat statistikasi."""

    def active_alerts_tool(limit: int = 20) -> str:
        """Aktiv ogohlantirishlar ro'yxati."""

    def alert_rules_tool(utility_type: str = "") -> str:
        """Ogohlantirish qoidalari (chegara qiymatlari)."""

    def energy_by_building_tool(from_ts: int = 0, to_ts: int = 0, building_id: int = 0, granularity: str = "day") -> str:
        """Elektr iste'moli binolar bo'yicha."""

    def buildings_energy_summary_tool() -> str:
        """30 kunlik elektr xulosasi barcha binolar bo'yicha."""

    def device_stats_tool(device_id: str, hours: int = 24) -> str:
        """Qurilma so'nggi N soat statistikasi."""

    def building_analytics_tool(building_id: int, hours: int = 24) -> str:
        """Bino elektr/suv/gaz tahlili."""

    def list_commands_tool(device_id: str = "", status: str = "", limit: int = 20) -> str:
        """Buyruqlar tarixi."""

    def reboot_tool(device_id: str) -> str:
        """FAQAT ADMIN: qurilmani reboot qilish."""

    def relay_control_tool(device_id: str, action: str) -> str:
        """FAQAT ADMIN: relay yoqish ('on') yoki o'chirish ('off')."""

    def clear_alerts_tool(device_id: str = "") -> str:
        """FAQAT ADMIN: ogohlantirishlarni tozalash."""

    model = genai.GenerativeModel(
        model_name="gemini-2.5-flash",
        system_instruction=_build_system_prompt(user),
        tools=[
            system_summary_tool,
            list_devices_tool,
            list_buildings_tool,
            get_device_details_tool,
            active_alerts_tool,
            alert_rules_tool,
            energy_by_building_tool,
            buildings_energy_summary_tool,
            device_stats_tool,
            building_analytics_tool,
            list_commands_tool,
            reboot_tool,
            relay_control_tool,
            clear_alerts_tool,
        ],
    )

    history = []
    for item in body.history[-20:]:
        role = "user" if item.role == "user" else "model"
        history.append({"role": role, "parts": [item.content]})

    chat = model.start_chat(history=history)
    response = chat.send_message(body.message)

    max_iterations = 8
    iteration = 0
    while iteration < max_iterations and response.candidates and response.candidates[0].content.parts:
        calls = [
            part.function_call
            for part in response.candidates[0].content.parts
            if getattr(part, "function_call", None)
        ]
        if not calls:
            break
        iteration += 1
        for call in calls:
            args = dict(call.args)
            yield f"data: {_json({'type': 'THOUGHT', 'content': f'🔍 {call.name} chaqirilmoqda...'})}\n\n"
            result = await execute_tool(call.name, args, user)
            yield f"data: {_json({'type': 'THOUGHT', 'content': f'✓ Natija: {result[:300]}...' if len(result) > 300 else f'✓ Natija: {result}'})}\n\n"
            response = chat.send_message(
                genai.types.Part.from_function_response(name=call.name, response={"result": result})
            )

    if getattr(response, "text", None):
        yield f"data: {_json({'type': 'FINAL_RESPONSE', 'content': response.text})}\n\n"
    yield "data: [DONE]\n\n"


# ─── DeepSeek flow ────────────────────────────────────────────────────────────

async def call_deepseek_completions(messages: list, tools: list | None = None) -> dict:
    api_key = settings.deepseek_api_key or os.getenv("DEEPSEEK_API_KEY")
    if not api_key:
        raise Exception("DEEPSEEK_API_KEY sozlanmagan!")
    payload = {"model": "deepseek-chat", "messages": messages, "temperature": 0.2}
    if tools:
        payload["tools"] = tools
    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(
            "https://api.deepseek.com/chat/completions",
            json=payload,
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"},
        )
    if response.status_code == 402:
        raise Exception("DeepSeek hisobingizda mablag' yetarli emas (402 Payment Required)!")
    if response.status_code != 200:
        raise Exception(f"DeepSeek API xatosi: {response.status_code} - {response.text}")
    return response.json()


async def execute_deepseek_flow(body: ChatRequest, user: dict):
    system_prompt = _build_system_prompt(user)
    messages = [{"role": "system", "content": system_prompt}]
    for item in body.history[-20:]:
        role = "user" if item.role == "user" else "assistant"
        messages.append({"role": role, "content": item.content})
    messages.append({"role": "user", "content": body.message})

    max_iterations = 8
    iteration = 0
    response = await call_deepseek_completions(messages, DEEPSEEK_TOOLS)

    while (
        iteration < max_iterations
        and response.get("choices")
        and response["choices"][0]["message"].get("tool_calls")
    ):
        iteration += 1
        message = response["choices"][0]["message"]
        messages.append(message)
        for tool_call in message["tool_calls"]:
            name = tool_call["function"]["name"]
            args = json.loads(tool_call["function"].get("arguments") or "{}")
            yield f"data: {_json({'type': 'THOUGHT', 'content': f'🔍 {name} chaqirilmoqda...'})}\n\n"
            result = await execute_tool(name, args, user)
            yield f"data: {_json({'type': 'THOUGHT', 'content': f'✓ Natija: {result[:300]}...' if len(result) > 300 else f'✓ Natija: {result}'})}\n\n"
            messages.append({
                "role": "tool",
                "tool_call_id": tool_call["id"],
                "name": name,
                "content": result,
            })
        response = await call_deepseek_completions(messages, DEEPSEEK_TOOLS)

    content = response.get("choices", [{}])[0].get("message", {}).get("content")
    if content:
        yield f"data: {_json({'type': 'FINAL_RESPONSE', 'content': content})}\n\n"
    yield "data: [DONE]\n\n"


# ─── Router ───────────────────────────────────────────────────────────────────

CHAT_STREAM_RESPONSE = {
    200: {
        "description": "Server-Sent Events oqimi. Har qator `data: {...}` yoki `data: [DONE]`.",
        "content": {
            "text/event-stream": {
                "schema": {
                    "type": "string",
                    "example": 'data: {"type":"FINAL_RESPONSE","content":"Tizim normal ishlayapti."}\n\ndata: [DONE]\n\n',
                }
            }
        },
    }
}


@router.post("/chat", response_class=StreamingResponse, responses=CHAT_STREAM_RESPONSE)
async def chat_endpoint(body: ChatRequest, user: dict = Depends(current_token_payload)):
    provider = str(body.provider).strip().lower()
    await _audit_chat_event(
        user,
        "chat.request",
        {
            "provider": provider,
            "role": user.get("role"),
            "message_len": len(body.message),
            "history_len": len(body.history),
        },
    )

    if _looks_sensitive_prompt(body.message):
        await _audit_chat_event(user, "chat.blocked", {"provider": provider, "reason": "sensitive_or_sql_prompt"})

        async def blocked_generator():
            yield f"data: {_json({'type': 'FINAL_RESPONSE', 'content': 'Bu so'rov xavfsizlik sababli rad etildi. SQL, token, parol yoki yashirin jadval ma'lumotlarini chat orqali olish mumkin emas.'})}\n\n"
            yield "data: [DONE]\n\n"

        return StreamingResponse(blocked_generator(), media_type="text/event-stream")

    # Provider fallback
    has_gemini = bool(settings.gemini_api_key or os.getenv("GEMINI_API_KEY"))
    has_deepseek = bool(settings.deepseek_api_key or os.getenv("DEEPSEEK_API_KEY"))

    if provider == ChatProvider.deepseek and not has_deepseek:
        if not has_gemini:
            raise HTTPException(400, "DEEPSEEK_API_KEY yoki GEMINI_API_KEY sozlanmagan")
        provider = ChatProvider.gemini
    elif provider != ChatProvider.deepseek and not has_gemini:
        if not has_deepseek:
            raise HTTPException(400, "GEMINI_API_KEY yoki DEEPSEEK_API_KEY sozlanmagan")
        provider = ChatProvider.deepseek

    async def event_generator():
        try:
            if provider == ChatProvider.deepseek:
                async for chunk in execute_deepseek_flow(body, user):
                    yield chunk
            else:
                async for chunk in execute_gemini_flow(body, user):
                    yield chunk
        except Exception as exc:
            logger.exception("chat failed")
            detail = str(exc)
            is_balance_error = any(
                word in detail.lower()
                for word in ("balance", "insufficient", "payment", "402", "quota", "limit", "billing")
            )
            fallback_provider = "deepseek" if provider != "deepseek" else "gemini"
            fallback_key = settings.deepseek_api_key if fallback_provider == "deepseek" else settings.gemini_api_key
            if is_balance_error and fallback_key:
                yield f"data: {_json({'type': 'THOUGHT', 'content': f'{provider} limit/billing xatosi. {fallback_provider} ga o'tilmoqda...'})}\n\n"
                try:
                    if fallback_provider == "deepseek":
                        async for chunk in execute_deepseek_flow(body, user):
                            yield chunk
                    else:
                        async for chunk in execute_gemini_flow(body, user):
                            yield chunk
                    return
                except Exception as fallback_exc:
                    detail = f"{detail} | fallback: {fallback_exc}"
            yield f"data: {_json({'type': 'FINAL_RESPONSE', 'content': f'AI xatoligi: {detail}'})}\n\n"
            yield "data: [DONE]\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")
