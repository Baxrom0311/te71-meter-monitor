#!/usr/bin/env python3
"""TE71/TE73 Meter CLI Tool.

Command-line interface to interact with the meter using DLMS/COSEM protocol.
Leverages the decoupled MeterService. Requires no GUI or PyQt6.
"""
import sys
import os
import argparse
import json
from datetime import datetime

# Add parent directory to path so we can import dlms and services
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import serial.tools.list_ports
from dlms.connection import DLMSConnection
from services.meter_service import MeterService


def auto_detect_port() -> str | None:
    """Find first available USB-to-serial port."""
    ports = serial.tools.list_ports.comports()
    for p in ports:
        dev = p.device.lower()
        if "usb" in dev or "serial" in dev or "tty" in dev or "com" in dev:
            return p.device
    return ports[0].device if ports else None


def print_log(msg: str):
    """Callback for meter logging."""
    print(f"[*] {msg}", file=sys.stderr)


def main():
    parser = argparse.ArgumentParser(
        description="TE71/TE73 Meter Command Line Interface"
    )

    # Connection settings
    parser.add_argument(
        "--port",
        help="Serial port (e.g. COM18, /dev/cu.usbserial-110). If omitted, attempts auto-detection."
    )
    parser.add_argument(
        "--baud",
        type=int,
        default=9600,
        help="Baud rate (default: 9600)"
    )
    parser.add_argument(
        "--auth",
        choices=["public", "reader", "manager"],
        default="public",
        help="Authentication level (default: public)"
    )
    parser.add_argument(
        "--password",
        default="00000000",
        help="Password for manager level authentication (default: 00000000)"
    )
    parser.add_argument(
        "--parity",
        choices=["N", "E", "O"],
        default="N",
        help="Serial port parity: N (None), E (Even), O (Odd) (default: N)"
    )
    parser.add_argument(
        "--stopbits",
        type=float,
        choices=[1.0, 1.5, 2.0],
        default=1.0,
        help="Serial port stop bits: 1, 1.5, 2 (default: 1.0)"
    )

    # Actions
    parser.add_argument(
        "--info",
        action="store_true",
        help="Read and display meter identification and firmware info"
    )
    parser.add_argument(
        "--dashboard",
        action="store_true",
        help="Read current measurements and total energy registers"
    )
    parser.add_argument(
        "--get",
        help="Read a specific register by key name (e.g. energy_total, voltage_l1)"
    )
    parser.add_argument(
        "--relay",
        choices=["on", "off", "status"],
        help="Perform relay action: turn ON (on), turn OFF (off), or check status (status)"
    )
    parser.add_argument(
        "--sync-time",
        action="store_true",
        help="Synchronize meter time with system local time"
    )

    # Formatting
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output results in JSON format"
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Display low-level DLMS/HDLC logging"
    )

    args = parser.parse_args()

    # Determine port
    port = args.port or auto_detect_port()
    if not port:
        print("[!] Error: No serial port found. Connect USB converter or specify --port.", file=sys.stderr)
        sys.exit(1)

    if not args.json:
        print(f"[*] Port: {port} @ {args.baud} baud", file=sys.stderr)
        print(f"[*] Auth level: {args.auth.upper()}", file=sys.stderr)

    # Initialize connection
    conn = DLMSConnection(port, args.baud, parity=args.parity, stopbits=args.stopbits)
    if args.verbose:
        conn.set_callbacks(
            on_tx=lambda hex_data: print(f"[TX] {hex_data}", file=sys.stderr),
            on_rx=lambda hex_data: print(f"[RX] {hex_data}", file=sys.stderr),
            on_log=print_log
        )
    else:
        # Suppress low-level logging
        conn._on_log = None

    try:
        conn.open()
    except Exception as e:
        print(f"[!] Error opening port {port}: {str(e)}", file=sys.stderr)
        sys.exit(1)

    # Connect client association
    ok = False
    if args.auth == "reader":
        ok = conn.connect_reader()
    elif args.auth == "manager":
        ok = conn.connect_manager(args.password)
    else:
        ok = conn.connect_public()

    if not ok:
        print("[!] Error: DLMS association rejected. Check connection/credentials.", file=sys.stderr)
        conn.close()
        sys.exit(1)

    # Build service layer
    service = MeterService(conn)
    if args.verbose:
        service.set_log_callback(print_log)

    # Collect data to report
    report = {}

    try:
        # Read info if requested or needed
        if args.info or args.dashboard or args.get:
            info = service.read_info()
            service.read_scalers()
            report["info"] = {
                "serial": info.serial,
                "manufacturer": info.manufacturer,
                "device_name": info.device_name,
                "firmware": info.firmware,
                "meter_type": info.meter_type
            }

        # 1. Read dashboard measurements
        if args.dashboard:
            dashboard = service.read_dashboard()
            report["dashboard"] = {
                k: {"value": formatted, "raw": raw}
                for k, (formatted, raw) in dashboard.items()
            }

        # 2. Get specific register
        if args.get:
            formatted, raw, reg = service.read_register(args.get)
            if reg:
                report["register"] = {
                    "key": args.get,
                    "obis": reg.obis_str,
                    "class_id": reg.class_id,
                    "name": reg.name_uz or reg.name,
                    "value": formatted,
                    "raw": raw,
                    "unit": reg.unit
                }
            else:
                print(f"[!] Warning: Unknown register key '{args.get}'", file=sys.stderr)

        # 3. Relay management
        if args.relay:
            # If performing command (on/off), need Reader level access
            if args.relay in ("on", "off") and conn.client_addr != 1:
                # Re-associate as Reader (1)
                conn.disconnect()
                if not conn.connect_reader():
                    print("[!] Error: Failed to escalate to Reader level (Client 1) for relay control.", file=sys.stderr)
                    conn.close()
                    sys.exit(1)
                # Recreate service (since connection changed)
                service = MeterService(conn)

            if args.relay == "on":
                ok = service.relay_reconnect()
                report["relay_action"] = {"action": "on", "success": ok}
            elif args.relay == "off":
                ok = service.relay_disconnect()
                report["relay_action"] = {"action": "off", "success": ok}

            # Always fetch state
            status = service.read_relay_status()
            report["relay_status"] = {
                "output_state": status.output_state,
                "control_state": status.control_state,
                "control_mode": status.control_mode,
                "output_text": status.output_text,
                "control_text": status.control_text,
                "mode_text": status.mode_text
            }

        # 4. Sync time
        if args.sync_time:
            ok = service.set_datetime()
            dt = service.read_datetime()
            report["sync_time"] = {
                "success": ok,
                "datetime": dt.strftime("%Y-%m-%d %H:%M:%S") if dt else None
            }

    except Exception as e:
        print(f"[!] Action failure: {str(e)}", file=sys.stderr)
        conn.close()
        sys.exit(1)

    # Disconnect cleanly
    try:
        conn.close()
    except Exception:
        pass

    # Print results
    if args.json:
        print(json.dumps(report, indent=2, default=str))
    else:
        # Text formatting
        if "info" in report:
            inf = report["info"]
            print("\n=== Hisoblagich ma'lumotlari ===")
            print(f"Model:                {inf['meter_type']}")
            print(f"Seriya raqami:        {inf['serial']}")
            print(f"Ishlab chiqaruvchi:   {inf['manufacturer']}")
            print(f"Dasturiy ta'minot:    {inf['firmware']}")

        if "dashboard" in report:
            print("\n=== Asosiy ko'rsatkichlar ===")
            for k, val in report["dashboard"].items():
                print(f"{k.ljust(22)}: {val['value']}")

        if "register" in report:
            reg = report["register"]
            print(f"\n=== Registr: {reg['key']} ===")
            print(f"OBIS:                 {reg['obis']}")
            print(f"Nomi:                 {reg['name']}")
            print(f"Qiymat:               {reg['value']}")

        if "relay_status" in report:
            st = report["relay_status"]
            print("\n=== Rele holati ===")
            print(f"Relening holati:      {st['output_text']}")
            print(f"Boshqaruv holati:     {st['control_text']}")
            print(f"Boshqaruv rejimi:     {st['mode_text']}")

        if "sync_time" in report:
            st = report["sync_time"]
            status = "Muvaffaqiyatli" if st["success"] else "Xatolik"
            print(f"\nVaqt sinxronizatsiya: {status} (Hozirgi vaqt: {st['datetime']})")


if __name__ == "__main__":
    main()
