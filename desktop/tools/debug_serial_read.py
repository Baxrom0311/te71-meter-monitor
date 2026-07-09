"""Temporary helper: read possible serial/info registers from the meter."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dlms.connection import DLMSConnection
from dlms.parser import parse_dlms_data, format_value


PORT = "COM18"


def main():
    conn = DLMSConnection(PORT, 9600)
    conn.open()
    print("connect_reader:", conn.connect_reader())

    variants = [
        ("serial_current", 1, (0, 0, 96, 1, 0, 255), 2),
        ("manufacturer", 1, (0, 0, 96, 1, 1, 255), 2),
        ("device_name", 1, (0, 0, 42, 0, 0, 255), 2),
        ("firmware", 1, (1, 0, 0, 2, 0, 255), 2),
        ("equipment_identifier", 1, (0, 0, 96, 1, 255, 255), 2),
        ("serial_data_class", 3, (0, 0, 96, 1, 0, 255), 2),
        ("serial_attr_1", 1, (0, 0, 96, 1, 0, 255), 1),
    ]

    for name, class_id, obis, attr in variants:
        print()
        print(name, "class", class_id, "obis", ".".join(map(str, obis)), "attr", attr)
        try:
            raw = conn.get_attribute(class_id, obis, attr)
            print("raw:", raw.hex(" ").upper() if raw else raw)
            if raw:
                val, tag, _ = parse_dlms_data(raw)
                print("tag:", hex(tag), "value:", repr(val), "formatted:", format_value(val))
        except Exception as exc:
            print("ERROR:", exc)

    conn.close()


if __name__ == "__main__":
    main()
