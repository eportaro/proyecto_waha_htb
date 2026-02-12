# database.py
from __future__ import annotations

import os
import json
from datetime import datetime
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv

load_dotenv()

# Config Supabase (lazy)
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
SUPABASE_AVAILABLE = bool(SUPABASE_URL and SUPABASE_KEY)

try:
    from supabase import create_client, Client
except Exception:
    Client = None  # type: ignore


class Database:
    """Gestor de base de datos para postulantes (Supabase ↔ JSON local fallback)."""

    def __init__(self) -> None:
        self.use_supabase = False
        self.client: Optional[Client] = None

        if SUPABASE_AVAILABLE and Client is not None:
            try:
                self.client = create_client(SUPABASE_URL, SUPABASE_KEY)  # type: ignore
                # ping simple para validar acceso
                self.client.table("postulantes").select("phone_number").limit(1).execute()  # type: ignore
                self.use_supabase = True
                print("✅ Supabase conectado", flush=True)
            except Exception as e:
                print(f"⚠️ Error conectando Supabase (modo local): {e}", flush=True)
                self._init_local_storage()
        else:
            print("⚠️ Supabase no configurado - usando almacenamiento local", flush=True)
            self._init_local_storage()

    # ─────────────────────────────────────────────────────────────
    # Local JSON fallback
    # ─────────────────────────────────────────────────────────────
    def _init_local_storage(self) -> None:
        self.local_file = "data/postulantes.json"
        os.makedirs("data", exist_ok=True)
        if not os.path.exists(self.local_file):
            with open(self.local_file, "w", encoding="utf-8") as f:
                json.dump([], f, ensure_ascii=False)

    def _ensure_local_ready(self) -> None:
        if not hasattr(self, "local_file"):
            self._init_local_storage()
        if not os.path.exists(self.local_file):
            with open(self.local_file, "w", encoding="utf-8") as f:
                json.dump([], f, ensure_ascii=False)

    # ─────────────────────────────────────────────────────────────
    # Esquema de payload
    # ─────────────────────────────────────────────────────────────
    def _build_payload(self, phone_number: str, session_data: Dict[str, Any]) -> Dict[str, Any]:
        clean_phone = phone_number.replace("@c.us", "").replace("@s.whatsapp.net", "")

        data = session_data.get("data", {}) or {}
        raw_answers = session_data.get("raw_answers", {}) or {}

        payload = {
            "phone_number": clean_phone,
            # Campos existentes
            "puesto_id": data.get("puesto_id"),
            "puesto_name": data.get("puesto_name"),
            "edad": data.get("edad"),
            "origen": data.get("origen"),
            "destino": data.get("destino"),
            "secundaria_completa": data.get("secundaria"),
            "tiene_dni": data.get("dni"),
            "tiene_licencia": data.get("licencia"),
            "licencia_categoria": data.get("licencia_cat"),
            "disponibilidad_inmediata": data.get("disponibilidad"),
            
            # Nuevos campos del formulario
            "nombre_completo": data.get("nombre_completo"),
            "nombres": data.get("nombres"),
            "apellidos": data.get("apellidos"),
            "genero": data.get("genero"),
            "tipo_documento": data.get("tipo_documento"),
            "numero_documento": data.get("numero_documento"),
            "correo_electronico": data.get("correo_electronico"),
            "ha_trabajado_en_hermes": data.get("ha_trabajado_en_hermes"),
            "modalidad_trabajo": data.get("modalidad_trabajo"),
            "distrito_residencia": data.get("distrito_residencia"),
            "ciudad_residencia": data.get("ciudad_residencia"),
            "medio_captacion": data.get("medio_captacion"),
            "medio_captacion_otro": data.get("medio_captacion_otro"),
            "puesto_otros_detalle": data.get("puesto_otros_detalle"),
            "horario_entrevista": data.get("horario_entrevista"),
            "autorizacion_datos": data.get("autorizacion_datos"),

            # Metadatos y calculados
            "es_apto": self._evaluate_apto(data),
            "respuestas_raw": json.dumps(raw_answers, ensure_ascii=False),
            "fecha_postulacion": (session_data.get("completion_time") or datetime.now()).isoformat(),
            # created_at lo pone la DB (DEFAULT now())
        }
        return payload

    # ─────────────────────────────────────────────────────────────
    # Reglas de aptitud
    # ─────────────────────────────────────────────────────────────
    def _evaluate_apto(self, data: Dict[str, Any]) -> bool:
        edad = data.get("edad")
        if not isinstance(edad, int) or edad < 18 or edad > 50:
            return False
        # Nota: 'origen' y 'destino' se mantienen por compatibilidad, 
        # pero la lógica de negocio podría refinar esto con ciudad_residencia
        origen = data.get("origen")
        destino = data.get("destino")
        
        # Si el destino es "ambos", es apto sin importar el origen
        if destino != "ambos" and origen != destino:
            return False
            
        if data.get("secundaria") is not True:
            return False
        if data.get("dni") is not True:
            return False
        if data.get("puesto_id") in (8, 9) and data.get("licencia") is not True:
            return False
        if data.get("disponibilidad") is not True:
            return False
        return True

    # ─────────────────────────────────────────────────────────────
    # Escritura
    # ─────────────────────────────────────────────────────────────
    def save_postulante(self, phone_number: str, session_data: Dict[str, Any]) -> bool:
        try:
            payload = self._build_payload(phone_number, session_data)

            if self.use_supabase and self.client is not None:
                try:
                    self.client.table("postulantes").insert(payload).execute()  # type: ignore
                    print(f"✅ Postulante guardado en Supabase: {payload['phone_number']}", flush=True)
                    return True
                except Exception as e:
                    print(f"❌ Error en Supabase INSERT (fallback local): {e}", flush=True)

            # Fallback local
            self._ensure_local_ready()
            return self._save_to_local(payload)

        except Exception as e:
            print(f"❌ Error guardando postulante: {e}", flush=True)
            return False

    def _save_to_local(self, postulante: Dict[str, Any]) -> bool:
        try:
            with open(self.local_file, "r", encoding="utf-8") as f:
                rows = json.load(f)
            rows.append(postulante)
            with open(self.local_file, "w", encoding="utf-8") as f:
                json.dump(rows, f, indent=2, ensure_ascii=False)
            print(f"✅ Postulante guardado localmente: {postulante['phone_number']}", flush=True)
            return True
        except Exception as e:
            print(f"❌ Error guardando local: {e}", flush=True)
            return False

    # ─────────────────────────────────────────────────────────────
    # Lectura
    # ─────────────────────────────────────────────────────────────
    def get_postulante(self, phone_number: str) -> Optional[Dict[str, Any]]:
        clean_phone = phone_number.replace("@c.us", "").replace("@s.whatsapp.net", "")
        try:
            if self.use_supabase and self.client is not None:
                # Preferir orden por id (robusto)
                try:
                    res = (
                        self.client.table("postulantes")
                        .select("*")
                        .eq("phone_number", clean_phone)
                        .order("id", desc=True)  # type: ignore
                        .limit(1)
                        .execute()
                    )
                except Exception:
                    res = (
                        self.client.table("postulantes")
                        .select("*")
                        .eq("phone_number", clean_phone)
                        .order("created_at", desc=True)  # type: ignore
                        .limit(1)
                        .execute()
                    )
                data = getattr(res, "data", None) or []
                return data[0] if data else None

            # Local
            self._ensure_local_ready()
            with open(self.local_file, "r", encoding="utf-8") as f:
                rows: List[Dict[str, Any]] = json.load(f)
            for p in reversed(rows):
                if p.get("phone_number") == clean_phone:
                    return p
            return None

        except Exception as e:
            print(f"❌ Error obteniendo postulante: {e}", flush=True)
            return None

    def get_all_postulantes(self, limit: int = 100, es_apto: Optional[bool] = None) -> List[Dict[str, Any]]:
        try:
            if self.use_supabase and self.client is not None:
                q = self.client.table("postulantes").select("*")  # type: ignore
                if es_apto is not None:
                    q = q.eq("es_apto", es_apto)  # type: ignore
                try:
                    res = q.order("id", desc=True).limit(limit).execute()  # type: ignore
                except Exception:
                    res = q.order("created_at", desc=True).limit(limit).execute()  # type: ignore
                return getattr(res, "data", None) or []

            # Local
            self._ensure_local_ready()
            with open(self.local_file, "r", encoding="utf-8") as f:
                rows: List[Dict[str, Any]] = json.load(f)
            if es_apto is not None:
                rows = [r for r in rows if r.get("es_apto") == es_apto]
            rows.sort(key=lambda r: r.get("created_at") or r.get("fecha_postulacion") or "", reverse=True)
            return rows[:limit]

        except Exception as e:
            print(f"❌ Error obteniendo postulantes: {e}", flush=True)
            return []

    def get_stats(self) -> Dict[str, Any]:
        try:
            rows = self.get_all_postulantes(limit=1000)
            total = len(rows)
            aptos = sum(1 for r in rows if r.get("es_apto") is True)
            no_aptos = total - aptos

            by_puesto: Dict[str, int] = {}
            for r in rows:
                name = r.get("puesto_name") or "Desconocido"
                by_puesto[name] = by_puesto.get(name, 0) + 1

            tasa = round(aptos * 100.0 / total, 2) if total else 0.0
            return {
                "total_postulantes": total,
                "aptos": aptos,
                "no_aptos": no_aptos,
                "tasa_aprobacion": tasa,
                "por_puesto": by_puesto,
            }
        except Exception as e:
            print(f"❌ Error obteniendo stats: {e}", flush=True)
            return {
                "total_postulantes": 0,
                "aptos": 0,
                "no_aptos": 0,
                "tasa_aprobacion": 0.0,
                "por_puesto": {},
            }


# ─────────────────────────────────────────────────────────────
# SQL SUGERIDO PARA SUPABASE (opcional, ejecutar una sola vez)
# ─────────────────────────────────────────────────────────────
SUPABASE_SQL = r"""
create table if not exists public.postulantes (
  id bigserial primary key,
  phone_number varchar(20) not null,
  puesto_id integer,
  puesto_name varchar(200),
  edad integer,
  origen varchar(50),
  destino varchar(50),
  secundaria_completa boolean,
  tiene_dni boolean,
  tiene_licencia boolean,
  licencia_categoria varchar(10),
  disponibilidad_inmediata boolean,
  es_apto boolean default false,
  respuestas_raw text,
  fecha_postulacion timestamptz,
  created_at timestamptz default now()
);

create index if not exists idx_postulantes_phone      on public.postulantes (phone_number);
create index if not exists idx_postulantes_es_apto    on public.postulantes (es_apto);
create index if not exists idx_postulantes_created_at on public.postulantes (created_at desc);
create index if not exists idx_postulantes_puesto     on public.postulantes (puesto_id);
"""
