# -*- coding: utf-8 -*-

import json
import os

from odoo import _, api, fields, models
from odoo.exceptions import UserError


class ErronkaLanpostu(models.Model):
    _name = "erronka.lanpostu"
    _description = "Lanpostua"

    name = fields.Char(string="Lanpostua", required=True, index=True)
    external_id = fields.Integer(string="ID externo", index=True)
    sync_enabled = fields.Boolean(string="Sincronizar desde API", default=True)
    active = fields.Boolean(default=True)

    _sql_constraints = [
        ("external_id_unique", "unique(external_id)", "El ID externo debe ser único."),
    ]

    @api.model
    def _fetch_lanpostuak_from_api(self):
        # API bidez lanpostuen zerrenda ekartzen du (kanpoko BBDD -> Odoo sinkronizazioa)
        data = self._api_request("GET", "/api/Lanpostuak")
        return data or []

    @api.model
    def _api_base_url(self):
        #return os.environ.get("ERRONKA_API_BASE_URL", "http://192.168.10.5:5000")
        return (
            os.environ.get("ERRONKA_API_BASE_URL")
            or os.environ.get("ERRONKA_API_URL")
            or "http://host.docker.internal:5101"
        )

    @api.model
    def _api_request(self, method, path, payload=None, params=None):
        # API HTTP deietarako utilitatea (GET/POST) eta JSON erantzuna normalizatzea
        try:
            import requests
        except Exception as exc:
            raise UserError(_("Falta la dependencia 'requests' en el entorno de Odoo.")) from exc

        url = self._api_base_url().rstrip("/") + path
        headers = {"Content-Type": "application/json"}

        try:
            resp = requests.request(
                method=method,
                url=url,
                params=params,
                data=json.dumps(payload) if payload is not None else None,
                headers=headers,
                timeout=20,
            )
            resp.raise_for_status()
        except Exception as exc:
            details = ""
            resp_obj = locals().get("resp")
            if resp_obj is not None:
                try:
                    details = resp_obj.text or ""
                except Exception:
                    details = ""
            if details:
                raise UserError(
                    _("Error llamando a la API: %(error)s\nRespuesta: %(details)s")
                    % {"error": str(exc), "details": details[:2000]}
                ) from exc
            raise UserError(_("Error llamando a la API: %(error)s") % {"error": str(exc)}) from exc

        if resp.status_code == 204 or not resp.content:
            return None

        try:
            return resp.json()
        except Exception as exc:
            raise UserError(_("Respuesta no válida (no JSON) desde la API.")) from exc

    def _push_lanpostuak_to_api(self):
        # Odoo-n egindako aldaketak API bidez bidaltzen ditu (INSERT/UPDATE/DELETE)
        if self.env.context.get("skip_mysql_push") or self.env.context.get("skip_api_push"):
            # Kanpotik inportatzean ez dugu berriro kanpora idatzi nahi (begizta saihesteko)
            return

        to_sync = self.filtered(lambda r: r.sync_enabled)
        if not to_sync:
            return

        for record in to_sync:
            if record.external_id:
                external_id = int(record.external_id)
            else:
                external_id = None

            if not record.active:
                if external_id:
                    self._api_request("DELETE", f"/api/odoo/lanpostuak/{external_id}")
                continue

            if not record.name:
                continue

            payload = {"lanpostu_izena": record.name}

            if external_id:
                self._api_request("PUT", f"/api/odoo/lanpostuak/{external_id}", payload=payload)
            else:
                data = self._api_request("POST", "/api/odoo/lanpostuak", payload=payload) or {}
                returned_id = data.get("id")
                if returned_id:
                    record.with_context(skip_mysql_push=True).write({"external_id": int(returned_id)})

    @api.model
    def _sync_lanpostuak_from_mysql(self):
        # Kanpoko MySQL-etik datozen lanpostuak Odoo-n sortu/eguneratzen ditu
        created = 0
        updated = 0

        for row in self._fetch_lanpostuak_from_api():
            ext_id = row.get("id") if isinstance(row, dict) else None
            name = (
                row.get("lanpostu_izena")
                or row.get("Lanpostu_izena")
                or row.get("lanpostua")
                or row.get("name")
            )
            if ext_id is None or not name:
                continue

            ext_id = int(ext_id)
            vals = {"external_id": ext_id, "name": name, "active": True}

            record = self.search([("external_id", "=", ext_id)], limit=1)
            if record:
                if record.sync_enabled:
                    # Inportazioan, skip_mysql_push aktibatzen da kanpora berriro ez idazteko
                    record.with_context(skip_mysql_push=True, skip_api_push=True).write(vals)
                    updated += 1
            else:
                self.with_context(skip_mysql_push=True, skip_api_push=True).create(vals)
                created += 1

        return {"created": created, "updated": updated}

    @api.model_create_multi
    def create(self, vals_list):
        # Odoo-n sortzean, automatikoki MySQL-era bidaltzen du
        records = super().create(vals_list)
        records._push_lanpostuak_to_api()
        return records

    def write(self, vals):
        # Odoo-n editatzean, automatikoki MySQL-era bidaltzen du
        result = super().write(vals)
        self._push_lanpostuak_to_api()
        return result

    def unlink(self):
        # Odoo-n ezabatzean, MySQL-n ere ezabatzen du (external_id bidez)
        external_ids = [int(x) for x in self.filtered(lambda r: r.sync_enabled and r.external_id).mapped("external_id")]
        result = super().unlink()

        if not self.env.context.get("skip_mysql_push") and not self.env.context.get("skip_api_push") and external_ids:
            for ext_id in external_ids:
                self._api_request("DELETE", f"/api/odoo/lanpostuak/{int(ext_id)}")

        return result

    def sync_lanpostuak_desde_api(self):
        # UI-tik sinkronizazioa exekutatu eta amaieran pantaila birkargatzen du
        counts = self.sudo()._sync_lanpostuak_from_mysql()
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Sincronización completada"),
                "message": _("Puestos: %(pc)s creados, %(pa)s actualizados.")
                % {"pc": counts.get("created", 0), "pa": counts.get("updated", 0)},
                "type": "success",
                "sticky": False,
                "next": {"type": "ir.actions.client", "tag": "reload"},
            },
        }
