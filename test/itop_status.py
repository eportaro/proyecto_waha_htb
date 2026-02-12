# itop_ticket_status.py
import os
import json
import argparse
import requests
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

ITOP_URL  = os.getenv("ITOP_BASE_URL")   # ej: https://tu-itop/webservices/rest.php?version=1.3
ITOP_USER = os.getenv("ITOP_USER")
ITOP_PASS = os.getenv("ITOP_PASS")

def itop_get_userrequest_by_ref(ref: str) -> dict:
    """
    Consulta un UserRequest por su 'ref' (p.ej. R-058228) y devuelve dict con campos útiles.
    """
    oql = f"SELECT UserRequest WHERE ref = '{ref}'"
    output_fields = ",".join([
        "ref","title","status","friendlyname",
        "service_id_friendlyname","servicesubcategory_id_friendlyname",
        "team_id_friendlyname","agent_id_friendlyname","caller_id_friendlyname",
        "priority","urgency","impact",
        "start_date","last_update","close_date",
        "resolution_code"
    ])

    payload = {
        "operation": "core/get",
        "class": "UserRequest",
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

    objects = res.get("objects") or {}
    if not objects:
        return {}

    # iTop devuelve un dict { 'UserRequest::<id>': { 'key': <id>, 'fields': {...} } }
    _k, obj = next(iter(objects.items()))
    return obj.get("fields", {})

def _fmt(dt_str: str | None) -> str:
    if not dt_str:
        return ""
    # iTop suele devolver 'YYYY-MM-DD HH:MM:SS'
    try:
        return datetime.strptime(dt_str, "%Y-%m-%d %H:%M:%S").strftime("%Y-%m-%d %H:%M")
    except Exception:
        return dt_str

def print_ticket_summary(fields: dict):
    if not fields:
        print("⚠️  No se encontró el ticket con ese ref o no tienes permisos.")
        return

    print("\n=== Resumen del Ticket ===")
    print(f"Ref:            {fields.get('ref','')}")
    print(f"Título:         {fields.get('title','')}")
    print(f"Estatus:        {fields.get('status','')}")
    print(f"Servicio:       {fields.get('service_id_friendlyname','')}")
    print(f"Subcategoría:   {fields.get('servicesubcategory_id_friendlyname','')}")
    print(f"Equipo:         {fields.get('team_id_friendlyname','')}")
    print(f"Agente:         {fields.get('agent_id_friendlyname','')}")
    print(f"Solicitante:    {fields.get('caller_id_friendlyname','')}")
    print(f"Prioridad:      {fields.get('priority','')}")
    print(f"Urgencia:       {fields.get('urgency','')}")
    print(f"Impacto:        {fields.get('impact','')}")
    print(f"Inicio:         {_fmt(fields.get('start_date'))}")
    print(f"Última act.:    {_fmt(fields.get('last_update'))}")
    print(f"Cierre:         {_fmt(fields.get('close_date'))}")
    print(f"Resolución:     {fields.get('resolution_code','')}")
    print()

def main():
    parser = argparse.ArgumentParser(description="Consulta el estatus de un ticket de iTop por ref (ej. R-058228).")
    parser.add_argument("--ref", required=True, help="Referencia del ticket (p.ej. R-058228)")
    args = parser.parse_args()

    try:
        fields = itop_get_userrequest_by_ref(args.ref)
        print_ticket_summary(fields)
    except requests.HTTPError as e:
        print(f"❌ Error HTTP consultando iTop: {e}")
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    main()
