# itop_estados_ur.py
import os, json, requests
from dotenv import load_dotenv

load_dotenv()

ITOP_URL  = os.getenv("ITOP_BASE_URL")
ITOP_USER = os.getenv("ITOP_USER")
ITOP_PASS = os.getenv("ITOP_PASS")
ITOP_ORG  = os.getenv("ITOP_ORG_ID")  # opcional, ej. "4"

# Opcional: acotar por fecha si tu instancia tiene MUCHOS tickets.
# Formato soportado por OQL: DATE('YYYY-MM-DD')
DATE_FROM = os.getenv("ITOP_DATE_FROM")  # ej. "2025-01-01"  -> filtra start_date >= esa fecha

def itop_call(payload: dict):
    data = {
        "auth_user": ITOP_USER,
        "auth_pwd": ITOP_PASS,
        "json_data": json.dumps(payload, ensure_ascii=False)
    }
    r = requests.post(ITOP_URL, data=data, timeout=120)
    r.raise_for_status()
    res = r.json()
    if res.get("code") != 0:
        raise RuntimeError(res.get("message"))
    return res.get("objects") or {}

def build_oql():
    where = []
    if ITOP_ORG:
        where.append(f"org_id = {ITOP_ORG}")
    if DATE_FROM:
        where.append(f"start_date >= DATE('{DATE_FROM}')")
    if where:
        return "SELECT UserRequest WHERE " + " AND ".join(where)
    return "SELECT UserRequest"

def main():
    try:
        oql = build_oql()
        payload = {
            "operation": "core/get",
            "class": "UserRequest",
            "key": oql,
            "output_fields": "status"
        }
        objs = itop_call(payload)

        estados = set()
        for _, obj in objs.items():
            st = (obj.get("fields") or {}).get("status")
            if st:
                estados.add(st)

        if not estados:
            print("⚠️ No se encontraron estados (revisa filtros o permisos).")
            return

        print("=== ESTADOS (encontrados en UserRequest) ===")
        for s in sorted(estados):
            print("-", s)

    except Exception as e:
        print(f"❌ Error consultando iTop: {e}")

if __name__ == "__main__":
    main()
