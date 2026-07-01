"""Safe SET capability test: write the current meter datetime back unchanged."""
from dlms.connection import DLMSConnection
from dlms.obis import REGISTERS
from dlms.parser import parse_dlms_data, encode_datetime


PORT = "COM18"


def connect(conn, mode):
    if mode == "reader_hls5":
        return conn.connect_reader()
    if mode == "manager_low_00000000":
        return conn.connect_manager("00000000")
    if mode == "public":
        return conn.connect_public()
    raise ValueError(mode)


def test_mode(mode):
    print()
    print("=" * 72)
    print(mode, "SET datetime same value")
    print("=" * 72)

    reg = REGISTERS["datetime"]
    conn = DLMSConnection(PORT, 9600)
    try:
        conn.open()
        ok = connect(conn, mode)
        print("CONNECT:", "OK" if ok else "FAILED")
        if not ok:
            return
        raw = conn.get_attribute(reg.class_id, reg.obis, reg.attr)
        if not raw:
            print("READ datetime: FAILED")
            return
        dt, _tag, _ = parse_dlms_data(raw)
        print("READ datetime:", dt)
        if dt is None:
            print("SET datetime: SKIPPED")
            return
        encoded = bytes([0x09, 0x0C]) + encode_datetime(dt)
        print("SET datetime:", "OK" if conn.set_attribute(reg.class_id, reg.obis, reg.attr, encoded) else "DENIED")
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
