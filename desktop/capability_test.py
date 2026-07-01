"""Capability test for TE71/TE73 access levels.

This script only performs safe reads and a safe relay reconnect action. It does
not change tariffs, passwords, or disconnect the load.
"""
from dlms.connection import DLMSConnection
from dlms.parser import parse_dlms_data, format_value, parse_scaler_unit
from dlms.obis import REGISTERS, RELAY_CLASS, RELAY_OBIS


PORT = "COM18"


TEST_GETS = [
    ("serial", "serial", 2),
    ("device_name", "device_name", 2),
    ("firmware", "firmware", 2),
    ("datetime", "datetime", 2),
    ("voltage_l1", "voltage_l1", 2),
    ("voltage_l1_scaler", "voltage_l1", 3),
    ("current_l1", "current_l1", 2),
    ("power_active_plus", "power_active_plus", 2),
    ("energy_total", "energy_total", 2),
    ("energy_t1", "energy_t1", 2),
    ("relay_output_state", "relay_state", 2),
    ("relay_control_state", "relay_control", 3),
    ("relay_control_mode", "relay_mode", 4),
    ("association_object_list", "assoc_ln_1", 2),
]


def connect(conn, mode):
    if mode == "reader_hls5":
        return conn.connect_reader()
    if mode == "manager_low_00000000":
        return conn.connect_manager("00000000")
    if mode == "public":
        return conn.connect_public()
    raise ValueError(mode)


def parse_result(raw, attr):
    if raw is None:
        return "DENIED/NO_RESPONSE", ""
    if attr == 3 and raw.startswith(b"\x02\x02"):
        scaler, unit = parse_scaler_unit(raw)
        return "OK", f"scaler={scaler}, unit={unit}"
    val, _tag, _ = parse_dlms_data(raw)
    text = format_value(val)
    if isinstance(text, str) and len(text) > 80:
        text = text[:77] + "..."
    return "OK", text


def test_mode(mode):
    print()
    print("=" * 72)
    print(mode)
    print("=" * 72)

    conn = DLMSConnection(PORT, 9600)
    try:
        conn.open()
        ok = connect(conn, mode)
        print("CONNECT:", "OK" if ok else "FAILED")
        if not ok:
            return

        for label, key, attr in TEST_GETS:
            reg = REGISTERS[key]
            raw = conn.get_attribute(reg.class_id, reg.obis, attr)
            status, value = parse_result(raw, attr)
            print(f"GET {label:<24} {status:<18} {value}")

        # Safe action: reconnect only. It does not disconnect an already-on load.
        success, code = conn.action(RELAY_CLASS, RELAY_OBIS, 2)
        print(f"ACTION relay_reconnect      {'OK' if success else 'DENIED'} code={code}")

    except Exception as exc:
        print("ERROR:", repr(exc))
    finally:
        try:
            conn.close()
        except Exception:
            pass


def main():
    for mode in ("reader_hls5", "manager_low_00000000", "public"):
        test_mode(mode)


if __name__ == "__main__":
    main()
