# itop_catalog_to_csv.py
import os, json, csv, requests
from dotenv import load_dotenv

load_dotenv()

ITOP_URL       = os.getenv("ITOP_BASE_URL")   # p.ej: https://.../webservices/rest.php?version=1.3
ITOP_USER      = os.getenv("ITOP_USER")
ITOP_PASS      = os.getenv("ITOP_PASS")
ITOP_ORG_ID    = os.getenv("ITOP_ORG_ID", "4")

# Opcionales para filtrar por produccion
ONLY_SERVICES_PRODUCTION   = os.getenv("ITOP_ONLY_SERVICES_PROD", "0") == "1"
ONLY_SUBCATS_PRODUCTION    = os.getenv("ITOP_ONLY_SUBCATS_PROD", "0") == "1"

def itop_get(class_name: str, oql: str, output_fields: str):
    payload = {
        "operation": "core/get",
        "class": class_name,
        "key": oql,
        "output_fields": output_fields
    }
    data = {
        "auth_user": ITOP_USER,
        "auth_pwd": ITOP_PASS,
        "json_data": json.dumps(payload, ensure_ascii=False)
    }
    r = requests.post(ITOP_URL, data=data, timeout=60)
    r.raise_for_status()
    res = r.json()
    if res.get("code") != 0:
        raise RuntimeError(f"iTop error: {res.get('message')}")
    out = []
    for _, obj in (res.get("objects") or {}).items():
        out.append({"id": obj["key"], **obj["fields"]})
    return out

def list_services(org_id: str):
    oql = f"SELECT Service WHERE org_id = {org_id}"
    if ONLY_SERVICES_PRODUCTION:
        oql += " AND status = 'production'"
    fields = "name,friendlyname,org_id,status"
    return itop_get("Service", oql, fields)

def list_subcategories_for_service(service_id: int | str):
    oql = f"SELECT ServiceSubcategory WHERE service_id = {service_id}"
    if ONLY_SUBCATS_PRODUCTION:
        oql += " AND status = 'production'"
    fields = "name,friendlyname,service_id,service_id_friendlyname,request_type,status"
    return itop_get("ServiceSubcategory", oql, fields)

def _excel_csv_writer(path: str, rows: list[dict], fieldnames: list[str]):
    # UTF-8 con BOM para que Excel en Windows abra bien los acentos
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for r in rows:
            w.writerow({k: ("" if r.get(k) is None else str(r.get(k))) for k in fieldnames})

def main():
    services = list_services(ITOP_ORG_ID)

    # 1) services.csv
    svc_rows = []
    for s in services:
        svc_rows.append({
            "service_id": s["id"],
            "service_name": s.get("name") or "",
            "service_friendlyname": s.get("friendlyname") or s.get("name") or "",
            "service_status": s.get("status") or "",
            "org_id": s.get("org_id") or ""
        })
    _excel_csv_writer(
        "services.csv",
        svc_rows,
        ["service_id","service_name","service_friendlyname","service_status","org_id"]
    )

    # 2) subcategories.csv y 3) service_subcategories.csv (join)
    sub_rows = []
    join_rows = []

    for s in services:
        sid   = s["id"]
        sname = s.get("friendlyname") or s.get("name") or ""
        sstat = s.get("status") or ""

        subcats = list_subcategories_for_service(sid)
        if not subcats:
            # Igual generamos una fila de join vacía si quieres trazar que no tiene subcats (opcional: coméntalo si no lo deseas)
            # join_rows.append({
            #     "service_id": sid, "service_name": sname, "service_status": sstat,
            #     "subcategory_id": "", "subcategory_name": "", "subcategory_status": "", "request_type": ""
            # })
            continue

        for sc in subcats:
            row_sub = {
                "subcategory_id": sc["id"],
                "subcategory_name": sc.get("name") or "",
                "subcategory_friendlyname": sc.get("friendlyname") or sc.get("name") or "",
                "request_type": sc.get("request_type") or "",
                "subcategory_status": sc.get("status") or "",
                "service_id": sc.get("service_id") or "",
                "service_friendlyname": sc.get("service_id_friendlyname") or ""
            }
            sub_rows.append(row_sub)

            join_rows.append({
                "service_id": sid,
                "service_name": sname,
                "service_status": sstat,
                "subcategory_id": sc["id"],
                "subcategory_name": sc.get("friendlyname") or sc.get("name") or "",
                "subcategory_status": sc.get("status") or "",
                "request_type": sc.get("request_type") or ""
            })

    _excel_csv_writer(
        "subcategories.csv",
        sub_rows,
        ["subcategory_id","subcategory_name","subcategory_friendlyname","request_type","subcategory_status","service_id","service_friendlyname"]
    )

    _excel_csv_writer(
        "service_subcategories.csv",
        join_rows,
        ["service_id","service_name","service_status","subcategory_id","subcategory_name","subcategory_status","request_type"]
    )

    print("✅ Generados: services.csv, subcategories.csv, service_subcategories.csv")

if __name__ == "__main__":
    main()
