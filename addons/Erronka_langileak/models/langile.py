# -*- coding: utf-8 -*-

import json
import hashlib
import os

from odoo import _, api, fields, models
from odoo.exceptions import UserError


class ErronkaLangile(models.Model):
    _name = "erronka.langile"
    _description = "Langilea"
    _rec_name = "name"

    name = fields.Char(string="Nombre", compute="_compute_name", store=True, index=True)
    izena = fields.Char(string="Izena", required=True, index=True)
    abizena = fields.Char(string="Abizena", required=True, index=True)
    nan = fields.Char(string="NAN", required=True, index=True)
    erabiltzaile_izena = fields.Char(string="Erabiltzaile izena", required=True, index=True)
    langile_kodea = fields.Integer(string="Langile kodea", required=True, index=True)
    password_hash = fields.Char(string="Pasahitza (hash)", groups="base.group_system")
    password_reset_pending = fields.Boolean(string="Reset pendiente", default=False)
    password_new = fields.Char(string="Nueva contraseña", store=False, copy=False, groups="base.group_system")
    password_new_confirm = fields.Char(string="Confirmar contraseña", store=False, copy=False, groups="base.group_system")
    helbidea = fields.Char(string="Helbidea", required=True)
    lanpostu_id = fields.Many2one("erronka.lanpostu", string="Lanpostua", required=True, ondelete="restrict")
    odoo_user_id = fields.Many2one("res.users", string="Usuario Odoo", copy=False, index=True, ondelete="set null")

    external_id = fields.Integer(string="ID externo", index=True)
    sync_enabled = fields.Boolean(string="Sincronizar desde API", default=True)
    active = fields.Boolean(default=True)

    _sql_constraints = [
        ("external_id_unique", "unique(external_id)", "El ID externo debe ser único."),
        ("nan_unique", "unique(nan)", "El NAN debe ser único."),
        ("erabiltzaile_izena_unique", "unique(erabiltzaile_izena)", "El nombre de usuario debe ser único."),
        ("langile_kodea_unique", "unique(langile_kodea)", "El código de trabajador debe ser único."),
    ]

    @api.depends("izena", "abizena")
    def _compute_name(self):
        # Odoo-n erakutsiko den izena kalkulatzen du (izena + abizena)
        for record in self:
            record.name = " ".join([part for part in [record.izena, record.abizena] if part])

    @api.model
    def _fetch_langileak_from_api(self):
        # MySQL-etik langileen zerrenda ekartzen du (kanpoko BBDD -> Odoo sinkronizazioa)
        data = self._api_request("GET", "/api/Langileak")
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

    @api.model
    def _hash_password(self, password):
        return hashlib.sha256(password.encode("utf-8")).hexdigest()

    def _is_management_role(self):
        self.ensure_one()
        role = (self.lanpostu_id.name or "").strip().lower()
        return role in {"jefe", "gerente", "gerentea", "jefea"}

    def _sync_odoo_user(self, password_plain=None):
        if self.env.context.get("skip_user_sync"):
            return

        if password_plain is None:
            password_plain = self.env.context.get("api_password_plain")

        Users = self.env["res.users"].sudo()
        group_user = self.env.ref("base.group_user").sudo()

        for record in self:
            if not record.erabiltzaile_izena:
                continue

            if not record._is_management_role() or not record.active:
                if record.odoo_user_id:
                    record.odoo_user_id.sudo().write({"active": False})
                continue

            user = record.odoo_user_id.sudo() if record.odoo_user_id else Users.search([("login", "=", record.erabiltzaile_izena)], limit=1)
            if user:
                other = record.search([("odoo_user_id", "=", user.id), ("id", "!=", record.id)], limit=1)
                if other:
                    raise UserError(_("Ya existe un usuario de Odoo con el login '%(login)s' enlazado a otro trabajador.") % {"login": record.erabiltzaile_izena})

            if not user:
                user_vals = {
                    "name": record.name or record.erabiltzaile_izena,
                    "login": record.erabiltzaile_izena,
                    "active": True,
                    "groups_id": [(6, 0, [group_user.id])],
                }
                user = Users.create(user_vals)
            else:
                update_vals = {}
                if user.login != record.erabiltzaile_izena:
                    update_vals["login"] = record.erabiltzaile_izena
                if record.name and user.name != record.name:
                    update_vals["name"] = record.name
                if not user.active:
                    update_vals["active"] = True
                if group_user.id not in user.groups_id.ids:
                    update_vals.setdefault("groups_id", []).append((4, group_user.id))
                if update_vals:
                    user.write(update_vals)

            if not record.odoo_user_id or record.odoo_user_id.id != user.id:
                record.with_context(skip_user_sync=True, skip_api_push=True, skip_mysql_push=True).write({"odoo_user_id": user.id})

            if password_plain:
                user.write({"password": password_plain})

    def set_password_from_plain(self, password_plain, password_confirm):
        self.ensure_one()
        if not password_plain or not password_confirm:
            raise UserError(_("Las contraseñas no pueden estar vacías."))
        if password_plain != password_confirm:
            raise UserError(_("Las contraseñas no coinciden."))
        password_hash = self._hash_password(password_plain)
        self.with_context(api_password_plain=password_plain).write({"password_hash": password_hash, "password_reset_pending": False})
        self._sync_odoo_user(password_plain=password_plain)
        return True

    def action_open_password_wizard(self):
        self.ensure_one()
        action = self.env.ref("Erronka_langileak.action_erronka_langile_password_wizard").read()[0]
        action_context = dict(self.env.context)
        action_context.update({"default_langile_id": self.id})
        action["context"] = action_context
        return action

    def action_reset_password(self):
        self.with_context(skip_api_push=True).write({"password_hash": False, "password_reset_pending": True})
        return True

    def _push_langileak_to_api(self):
        # Odoo-n egindako aldaketak MySQL-era bidaltzen ditu (INSERT/UPDATE/DELETE)
        if self.env.context.get("skip_mysql_push") or self.env.context.get("skip_api_push"):
            # MySQL-etik inportatzean ez dugu berriro kanpora idatzi nahi (begizta saihesteko)
            return

        to_sync = self.filtered(lambda r: r.sync_enabled)
        if not to_sync:
            return

        for record in to_sync:
            if not record.lanpostu_id:
                raise UserError(_("Falta 'Lanpostua' para sincronizar el trabajador %(name)s.") % {"name": record.display_name})

            if record.external_id:
                external_id = int(record.external_id)
            else:
                external_id = None

            if not record.active:
                if external_id:
                    self._api_request("DELETE", f"/api/odoo/langileak/{external_id}")
                continue

            if not record.lanpostu_id.external_id:
                record.lanpostu_id._push_lanpostuak_to_api()

            lanpostu_ext_id = record.lanpostu_id.external_id
            if not lanpostu_ext_id:
                raise UserError(_("No se pudo obtener el ID externo de 'Lanpostua' para %(name)s.") % {"name": record.display_name})

            if not record.izena or not record.abizena or not record.nan or not record.erabiltzaile_izena or not record.helbidea:
                raise UserError(_("Faltan campos obligatorios para sincronizar %(name)s.") % {"name": record.display_name})

            if record.langile_kodea is None:
                raise UserError(_("Falta 'Langile kodea' para sincronizar %(name)s.") % {"name": record.display_name})

            payload = {
                "izena": record.izena,
                "abizena": record.abizena,
                "nan": record.nan,
                "erabiltzaile_izena": record.erabiltzaile_izena,
                "langile_kodea": int(record.langile_kodea),
                "helbidea": record.helbidea,
                "lanpostuaId": int(lanpostu_ext_id),
            }

            password_plain = self.env.context.get("api_password_plain")
            if password_plain:
                payload["pasahitza"] = password_plain

            if external_id:
                self._api_request("PUT", f"/api/odoo/langileak/{external_id}", payload=payload)
            else:
                data = self._api_request("POST", "/api/odoo/langileak", payload=payload) or {}
                returned_id = data.get("id")
                if returned_id:
                    record.with_context(skip_mysql_push=True).write({"external_id": int(returned_id)})

    @api.model
    def _sync_langileak_from_mysql(self):
        # Kanpoko MySQL-etik datozen langileak Odoo-n sortu/eguneratzen ditu
        created = 0
        updated = 0

        lanpostu_model = self.env["erronka.lanpostu"].sudo()

        for row in self._fetch_langileak_from_api():
            ext_id = row.get("id")
            if ext_id is None:
                continue

            lanpostu = row.get("lanpostua") if isinstance(row, dict) else None
            lanpostu_ext_id = lanpostu.get("id") if isinstance(lanpostu, dict) else None
            if lanpostu_ext_id in (None, 0):
                raise UserError(_("Registro inválido (langileak): falta 'lanpostuak_id' para id=%(id)s.") % {"id": ext_id})

            lanpostu_ext_id = int(lanpostu_ext_id)
            lanpostu = lanpostu_model.search([("external_id", "=", lanpostu_ext_id)], limit=1)
            if not lanpostu:
                lanpostu = lanpostu_model.with_context(skip_mysql_push=True).create(
                    {"name": str(lanpostu_ext_id), "external_id": lanpostu_ext_id, "active": True}
                )

            izena = row.get("izena")
            abizena = row.get("abizena")
            nan = row.get("nan") or row.get("NAN")
            erabiltzaile_izena = row.get("erabiltzaile_izena")
            helbidea = row.get("helbidea")
            langile_kodea = row.get("langile_kodea")
            if not izena or not abizena or not nan or not erabiltzaile_izena or not helbidea or langile_kodea is None:
                raise UserError(
                    _(
                        "Registro inválido (langileak): faltan campos obligatorios para id=%(id)s."
                    )
                    % {"id": ext_id}
                )

            vals = {
                "external_id": int(ext_id),
                "izena": izena,
                "abizena": abizena,
                "nan": nan,
                "erabiltzaile_izena": erabiltzaile_izena,
                "langile_kodea": int(langile_kodea),
                "helbidea": helbidea,
                "active": True,
            }
            pwd = row.get("pasahitza") or row.get("Pasahitza")
            if pwd is not None:
                vals["password_hash"] = pwd
            vals["lanpostu_id"] = lanpostu.id

            record = self.search([("external_id", "=", int(ext_id))], limit=1)
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
        password_list = []
        cleaned_vals_list = []
        for vals in vals_list:
            vals = dict(vals)
            password_plain = vals.pop("password_new", None)
            password_confirm = vals.pop("password_new_confirm", None)
            if password_plain or password_confirm:
                if password_plain != password_confirm:
                    raise UserError(_("Las contraseñas no coinciden."))
                vals["password_hash"] = self._hash_password(password_plain or "")
                vals["password_reset_pending"] = False
            password_list.append(password_plain)
            cleaned_vals_list.append(vals)

        records = super().create(cleaned_vals_list)
        for record, password_plain in zip(records, password_list):
            if password_plain:
                record.with_context(api_password_plain=password_plain)._push_langileak_to_api()
            else:
                record._push_langileak_to_api()
            record._sync_odoo_user(password_plain=password_plain)
        return records

    def write(self, vals):
        vals = dict(vals)
        password_plain = vals.pop("password_new", None)
        password_confirm = vals.pop("password_new_confirm", None)
        if password_plain or password_confirm:
            if password_plain != password_confirm:
                raise UserError(_("Las contraseñas no coinciden."))
            vals["password_hash"] = self._hash_password(password_plain or "")
            vals["password_reset_pending"] = False

        result = super().write(vals)
        if password_plain:
            self.with_context(api_password_plain=password_plain)._push_langileak_to_api()
        else:
            self._push_langileak_to_api()
        self._sync_odoo_user(password_plain=password_plain)
        return result

    def unlink(self):
        # Odoo-n ezabatzean, MySQL-n ere ezabatzen du (external_id bidez)
        external_ids = [int(x) for x in self.filtered(lambda r: r.sync_enabled and r.external_id).mapped("external_id")]
        users_to_disable = self.mapped("odoo_user_id").sudo()
        result = super().unlink()

        if not self.env.context.get("skip_mysql_push") and not self.env.context.get("skip_api_push") and external_ids:
            for ext_id in external_ids:
                self._api_request("DELETE", f"/api/odoo/langileak/{int(ext_id)}")

        if users_to_disable:
            users_to_disable.write({"active": False})

        return result

    def sync_langileak_desde_api(self):
        # UI-tik sinkronizazioa exekutatu eta amaieran pantaila birkargatzen du
        counts = self.sudo()._sync_langileak_from_mysql()
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Sincronización completada"),
                "message": _("Trabajadores: %(tc)s creados, %(ta)s actualizados.")
                % {"tc": counts.get("created", 0), "ta": counts.get("updated", 0)},
                "type": "success",
                "sticky": False,
                "next": {"type": "ir.actions.client", "tag": "reload"},
            },
        }


class ErronkaLangilePasswordWizard(models.TransientModel):
    _name = "erronka.langile.password.wizard"
    _description = "Langile password wizard"

    langile_id = fields.Many2one("erronka.langile", string="Langilea", required=True, ondelete="cascade")
    password_new = fields.Char(string="Nueva contraseña", required=True)
    password_new_confirm = fields.Char(string="Confirmar contraseña", required=True)

    def action_apply(self):
        self.ensure_one()
        self.langile_id.set_password_from_plain(self.password_new, self.password_new_confirm)
        return {"type": "ir.actions.act_window_close"}
