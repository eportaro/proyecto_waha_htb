import os, json, requests
from dotenv import load_dotenv

load_dotenv()

ITOP_URL       = os.getenv("ITOP_BASE_URL")
ITOP_USER      = os.getenv("ITOP_USER")
ITOP_PASS      = os.getenv("ITOP_PASS")
ITOP_ORG_ID    = os.getenv("ITOP_ORG_ID", "4")
ITOP_CALLER_ID = os.getenv("ITOP_CALLER_ID", "4083")
ITOP_SERVICE_ID= os.getenv("ITOP_SERVICE_ID", "16")
ITOP_SUBCAT_ID = os.getenv("ITOP_SUBCAT_ID", "67")
ITOP_TEAM_ID   = os.getenv("ITOP_TEAM_ID", "")
ITOP_TEAM_NAME = os.getenv("ITOP_TEAM_NAME", "")
ITOP_AGENT_ID  = os.getenv("ITOP_AGENT_ID", "")

def build_payload(title: str, desc_html: str):
    """Construye el payload de creación de ticket en iTop."""
    fields = {
        "org_id": ITOP_ORG_ID,
        "caller_id": ITOP_CALLER_ID,
        "service_id": ITOP_SERVICE_ID,
        "servicesubcategory_id": ITOP_SUBCAT_ID,
        "title": title,
        "description": desc_html,
        "public_log": "<p>Creado por Chatbot TI</p>"
    }
    if ITOP_TEAM_ID:
        fields["team_id"] = ITOP_TEAM_ID
    if ITOP_AGENT_ID:
        fields["agent_id"] = ITOP_AGENT_ID

    return {
        "operation": "core/create",
        "class": "UserRequest",
        "comment": "Creado vía Chatbot TI",
        "fields": fields,
        "output_fields": "id,ref,friendlyname,status"
    }

def create_ticket(title: str, desc_html: str):
    """Crea un ticket en iTop y devuelve el resultado."""
    try:
        payload = build_payload(title, desc_html)
        data = {
            "auth_user": ITOP_USER,
            "auth_pwd": ITOP_PASS,
            "json_data": json.dumps(payload, ensure_ascii=False)
        }
        r = requests.post(ITOP_URL, data=data, timeout=60)
        r.raise_for_status()
        res = r.json()
        if res.get("code") == 0:
            obj = next(iter((res.get("objects") or {}).values()), {})
            fields = obj.get("fields", {})
            return {"ok": True, "ref": fields.get("ref"), "data": fields}
        else:
            return {"ok": False, "error": res.get("message", "Error lógico en iTop")}
    except Exception as e:
        return {"ok": False, "error": str(e)}

# === NUEVO: Consulta por ref ===
def get_userrequest_by_ref(ref: str):
    """
    Consulta un UserRequest por 'ref' (p.ej. R-058228).
    Retorna: {"ok": True, "fields": {...}} ó {"ok": False, "error": "..."}.
    """
    try:
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
            return {"ok": False, "error": res.get("message", "Error iTop")}
        objects = res.get("objects") or {}
        if not objects:
            return {"ok": False, "error": "Ticket no encontrado"}
        _k, obj = next(iter(objects.items()))
        return {"ok": True, "fields": obj.get("fields", {})}
    except Exception as e:
        return {"ok": False, "error": str(e)}
