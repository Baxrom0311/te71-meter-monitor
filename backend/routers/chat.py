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
from services.alerts import get_alerts
from services import audit as audit_service
from services.commands import create_relay_command, reboot_device

router = APIRouter(prefix="/api", tags=["chat"])
logger = logging.getLogger(__name__)
ADMIN_TOOL_NAMES = {"reboot_tool", "relay_control_tool"}
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
        if name == "system_summary_tool":
            return await system_summary_tool()
        if name == "active_alerts_tool":
            return await active_alerts_tool(args.get("limit", 20))
        if name == "energy_by_building_tool":
            return await energy_by_building_tool(
                args.get("from_ts", 0),
                args.get("to_ts", 0),
                args.get("building_id", 0),
                args.get("granularity", "day"),
            )
        if name == "buildings_energy_summary_tool":
            return await buildings_energy_summary_tool()
        if name == "device_stats_tool":
            return await device_stats_tool(args.get("device_id", ""), args.get("hours", 24))
        if name == "building_analytics_tool":
            return await building_analytics_tool(args.get("building_id", 0), args.get("hours", 24))
        if name == "reboot_tool":
            return await reboot_tool(args.get("device_id", ""), user)
        if name == "relay_control_tool":
            return await relay_control_tool(args.get("device_id", ""), args.get("action", ""), user)
        return f"Xato: Noma'lum funksiya {name}"
    except Exception as exc:
        logger.exception("chat tool failed: %s", name)
        return f"Xato: {exc}"


DEEPSEEK_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "system_summary_tool",
            "description": "Returns dashboard summary: device counts, online/offline, active alerts, readings, total energy.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "active_alerts_tool",
            "description": "Returns active uncleared alerts with a safe limit.",
            "parameters": {
                "type": "object",
                "properties": {"limit": {"type": "integer", "minimum": 1, "maximum": 100}},
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "energy_by_building_tool",
            "description": "Returns electricity consumption buckets by building for a timestamp range.",
            "parameters": {
                "type": "object",
                "properties": {
                    "from_ts": {"type": "integer"},
                    "to_ts": {"type": "integer"},
                    "building_id": {"type": "integer", "description": "0 means all buildings."},
                    "granularity": {"type": "string", "enum": ["hour", "day"]},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "buildings_energy_summary_tool",
            "description": "Returns 30-day energy summary for all buildings.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "device_stats_tool",
            "description": "Returns recent aggregated readings for one device.",
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
            "description": "Returns electricity, water, gas and alert analytics for one building.",
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
            "name": "reboot_tool",
            "description": "Admin-only: queues a reboot command for a device.",
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
            "description": "Admin-only: queues relay on/off command for a device.",
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
]


SYSTEM_PROMPT = (
    "Siz TE71/TE73 Meter Monitor loyihasining AI yordamchisiz.\n"
    "Javoblar faqat o'zbek tilida, aniq va qisqa bo'lsin.\n"
    "Sizda SQL, jadval nomlari yoki raw database query huquqi yo'q. "
    "Foydalanuvchi SQL yozishni, yashirin jadvalni, parol/token/user ma'lumotlarini so'rasa rad eting.\n"
    "Ma'lumot kerak bo'lsa faqat berilgan safe function toollardan foydalaning: summary, active alerts, "
    "energy analytics, building analytics, device stats.\n"
    "Device reboot va relay commandlari faqat admin uchun; admin bo'lmagan userga bunday buyruq bajarilmasligini ayting.\n"
    f"Hozirgi server timestamp: {now_ts()}."
)


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


async def execute_gemini_flow(body: ChatRequest, user: dict):
    api_key = settings.gemini_api_key or os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise Exception("GEMINI_API_KEY sozlanmagan. AI Chatdan foydalanish uchun kalit kerak!")

    genai.configure(api_key=api_key)

    def system_summary_tool() -> str:
        """Returns dashboard summary."""

    def active_alerts_tool(limit: int = 20) -> str:
        """Returns active alerts."""

    def energy_by_building_tool(from_ts: int = 0, to_ts: int = 0, building_id: int = 0, granularity: str = "day") -> str:
        """Returns electricity consumption by building for a timestamp range."""

    def buildings_energy_summary_tool() -> str:
        """Returns 30-day energy summary for all buildings."""

    def device_stats_tool(device_id: str, hours: int = 24) -> str:
        """Returns recent stats for one device."""

    def building_analytics_tool(building_id: int, hours: int = 24) -> str:
        """Returns analytics for one building."""

    def reboot_tool(device_id: str) -> str:
        """Admin-only: queues a device reboot command."""

    def relay_control_tool(device_id: str, action: str) -> str:
        """Admin-only: queues relay on/off command."""

    model = genai.GenerativeModel(
        model_name="gemini-2.5-flash",
        system_instruction=SYSTEM_PROMPT,
        tools=[
            system_summary_tool,
            active_alerts_tool,
            energy_by_building_tool,
            buildings_energy_summary_tool,
            device_stats_tool,
            building_analytics_tool,
            reboot_tool,
            relay_control_tool,
        ],
    )

    history = []
    for item in body.history[-20:]:
        role = "user" if item.role == "user" else "model"
        history.append({"role": role, "parts": [item.content]})

    chat = model.start_chat(history=history)
    response = chat.send_message(body.message)

    while response.candidates and response.candidates[0].content.parts:
        calls = [part.function_call for part in response.candidates[0].content.parts if getattr(part, "function_call", None)]
        if not calls:
            break
        for call in calls:
            args = dict(call.args)
            yield f"data: {_json({'type': 'THOUGHT', 'content': f'AI safe funksiya chaqiryapti: {call.name}'})}\n\n"
            result = await execute_tool(call.name, args, user)
            yield f"data: {_json({'type': 'THOUGHT', 'content': f'Natija: {result[:200]}...'})}\n\n"
            response = chat.send_message(
                genai.types.Part.from_function_response(name=call.name, response={"result": result})
            )

    if getattr(response, "text", None):
        yield f"data: {_json({'type': 'FINAL_RESPONSE', 'content': response.text})}\n\n"
    yield "data: [DONE]\n\n"


async def execute_deepseek_flow(body: ChatRequest, user: dict):
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    for item in body.history[-20:]:
        role = "user" if item.role == "user" else "assistant"
        messages.append({"role": role, "content": item.content})
    messages.append({"role": "user", "content": body.message})

    response = await call_deepseek_completions(messages, DEEPSEEK_TOOLS)
    while response.get("choices") and response["choices"][0]["message"].get("tool_calls"):
        message = response["choices"][0]["message"]
        messages.append(message)
        for tool_call in message["tool_calls"]:
            name = tool_call["function"]["name"]
            args = json.loads(tool_call["function"].get("arguments") or "{}")
            yield f"data: {_json({'type': 'THOUGHT', 'content': f'AI safe funksiya chaqiryapti: {name}'})}\n\n"
            result = await execute_tool(name, args, user)
            yield f"data: {_json({'type': 'THOUGHT', 'content': f'Natija: {result[:200]}...'})}\n\n"
            messages.append({"role": "tool", "tool_call_id": tool_call["id"], "name": name, "content": result})
        response = await call_deepseek_completions(messages, DEEPSEEK_TOOLS)

    content = response.get("choices", [{}])[0].get("message", {}).get("content")
    if content:
        yield f"data: {_json({'type': 'FINAL_RESPONSE', 'content': content})}\n\n"
    yield "data: [DONE]\n\n"


CHAT_STREAM_RESPONSE = {
    200: {
        "description": "Server-Sent Events stream. Har bir qator `data: {...}` yoki `data: [DONE]` formatida keladi.",
        "content": {
            "text/event-stream": {
                "schema": {
                    "type": "string",
                    "example": 'data: {"type":"FINAL_RESPONSE","content":"Tizim normal ishlayapti."}\\n\\ndata: [DONE]\\n\\n',
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
            "message_len": len(body.message),
            "history_len": len(body.history),
        },
    )

    if _looks_sensitive_prompt(body.message):
        await _audit_chat_event(user, "chat.blocked", {"provider": provider, "reason": "sensitive_or_sql_prompt"})

        async def blocked_generator():
            yield f"data: {_json({'type': 'FINAL_RESPONSE', 'content': 'Bu so‘rov xavfsizlik sababli rad etildi. SQL, token, parol yoki yashirin jadval ma’lumotlarini chat orqali olish mumkin emas.'})}\n\n"
            yield "data: [DONE]\n\n"

        return StreamingResponse(blocked_generator(), media_type="text/event-stream")

    async def event_generator():
        try:
            if provider == "deepseek":
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
                yield f"data: {_json({'type': 'THOUGHT', 'content': f'{provider} limit/billing xatosi. {fallback_provider} ga o‘tilmoqda.'})}\n\n"
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

    if provider == ChatProvider.deepseek and not (settings.deepseek_api_key or os.getenv("DEEPSEEK_API_KEY")):
        if not (settings.gemini_api_key or os.getenv("GEMINI_API_KEY")):
            raise HTTPException(400, "DEEPSEEK_API_KEY yoki GEMINI_API_KEY sozlanmagan")
        provider = ChatProvider.gemini
    elif provider != ChatProvider.deepseek and not (settings.gemini_api_key or os.getenv("GEMINI_API_KEY")):
        if not (settings.deepseek_api_key or os.getenv("DEEPSEEK_API_KEY")):
            raise HTTPException(400, "GEMINI_API_KEY yoki DEEPSEEK_API_KEY sozlanmagan")
        provider = ChatProvider.deepseek

    return StreamingResponse(event_generator(), media_type="text/event-stream")
