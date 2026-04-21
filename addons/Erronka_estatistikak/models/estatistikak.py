# -*- coding: utf-8 -*-

import json
import os
from datetime import datetime

from odoo import _, api, fields, models
from odoo.exceptions import UserError


class ErronkaApiMixin(models.AbstractModel):
    _name = "erronka.api.mixin"
    _description = "Erronka API utilitateak"

    # API helbidea ingurune-aldagai bidez konfiguratzen da, Docker/host egoeretara egokitzeko
    @api.model
    def _api_base_url(self):
        return os.environ.get("ERRONKA_API_BASE_URL", "http://192.168.10.5:5000")

    # HTTP deia egin eta JSON erantzuna bueltatzen du; erroreak UserError moduan erakusten ditu
    @api.model
    def _api_request(self, method, path, payload=None, params=None):
        try:
            import requests
        except Exception as exc:
            raise UserError(_("Odoo ingurunean 'requests' falta da.")) from exc

        url = self._api_base_url().rstrip("/") + path
        headers = {"Content-Type": "application/json"}

        try:
            resp = requests.request(
                method=method,
                url=url,
                params=params,
                data=json.dumps(payload) if payload is not None else None,
                headers=headers,
                timeout=30,
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
                    _("API deian errorea: %(error)s\nErantzuna: %(details)s")
                    % {"error": str(exc), "details": details[:2000]}
                ) from exc
            raise UserError(_("API deian errorea: %(error)s") % {"error": str(exc)}) from exc

        if resp.status_code == 204 or not resp.content:
            return None

        try:
            return resp.json()
        except Exception as exc:
            raise UserError(_("API erantzuna ez da JSON baliozkoa.")) from exc

    # APIko datetime testu bat Python datetime bihurtzeko laguntzailea (formato ezberdinak jasateko)
    @api.model
    def _parse_api_datetime(self, value):
        if not value:
            return None
        if isinstance(value, datetime):
            return value
        if isinstance(value, str):
            v = value.strip()
            try:
                return datetime.fromisoformat(v.replace("Z", "+00:00"))
            except Exception:
                try:
                    return fields.Datetime.from_string(v)
                except Exception:
                    return None
        return None


class ErronkaEstatistikaSalmenta(models.Model):
    _name = "erronka.estatistika.salmenta"
    _description = "Salmenten estatistikak"
    _inherit = "erronka.api.mixin"
    _rec_name = "eguna"

    eguna = fields.Date(string="Eguna", required=True, index=True)
    salmenta_totala = fields.Float(string="Salmenta totala", required=True)
    erreserba_kopurua = fields.Integer(string="Erreserba kopurua", required=True)
    ticket_batezbestekoa = fields.Float(string="Ticket batezbestekoa", required=True)

    eguna_key_day = fields.Char(string="Eguna (gakoa)", compute="_compute_eguna_keys", store=True, index=True)
    eguna_key_month = fields.Char(string="Hilabetea (gakoa)", compute="_compute_eguna_keys", store=True, index=True)
    eguna_key_quarter = fields.Char(string="Hiruhilekoa (gakoa)", compute="_compute_eguna_keys", store=True, index=True)
    eguna_key_year = fields.Char(string="Urtea (gakoa)", compute="_compute_eguna_keys", store=True, index=True)

    _sql_constraints = [
        ("eguna_unique", "unique(eguna)", "Egun bakoitzeko erregistro bakarra egon daiteke."),
    ]

    @api.depends("eguna")
    def _compute_eguna_keys(self):
        for record in self:
            if not record.eguna:
                record.eguna_key_day = False
                record.eguna_key_month = False
                record.eguna_key_quarter = False
                record.eguna_key_year = False
                continue

            d = record.eguna
            record.eguna_key_day = d.strftime("%Y-%m-%d")
            record.eguna_key_month = d.strftime("%Y-%m")
            quarter = ((d.month - 1) // 3) + 1
            record.eguna_key_quarter = f"{d.year}-Q{quarter}"
            record.eguna_key_year = str(d.year)

    # Salmentak API-tik berrikalkulatu eta Odoo-n gordetzen ditu (grafikoak egiteko)
    @api.model
    def _eguneratu_datuak(self):
        erreserbak = self._api_request("GET", "/api/Erreserbak") or []

        by_day = {}
        for r in erreserbak:
            if not isinstance(r, dict):
                continue
            if int(r.get("ordainduta") or 0) != 1:
                continue

            dt = self._parse_api_datetime(r.get("egunaOrdua"))
            if not dt:
                continue
            day = dt.date()

            amount = float(r.get("prezioTotala") or 0.0)
            agg = by_day.setdefault(day, {"amount": 0.0, "count": 0})
            agg["amount"] += amount
            agg["count"] += 1

        self.sudo().search([]).unlink()
        vals_list = []
        for day, agg in sorted(by_day.items(), key=lambda x: x[0]):
            count = int(agg["count"])
            amount = float(agg["amount"])
            avg = amount / count if count else 0.0
            vals_list.append(
                {
                    "eguna": day,
                    "salmenta_totala": amount,
                    "erreserba_kopurua": count,
                    "ticket_batezbestekoa": avg,
                }
            )
        if vals_list:
            self.sudo().create(vals_list)
        return True

    # UI-tik botoia sakatzean erabiltzen da: datuak eguneratu eta pantaila berriz kargatu
    @api.model
    def action_eguneratu(self):
        self._eguneratu_datuak()
        return {"type": "ir.actions.client", "tag": "reload"}


class ErronkaEstatistikaProduktua(models.Model):
    _name = "erronka.estatistika.produktua"
    _description = "Produktuen estatistikak"
    _inherit = "erronka.api.mixin"

    eguna = fields.Date(string="Eguna", required=True, index=True)
    produktua_id = fields.Integer(string="Produktua ID", required=True, index=True)
    produktua_izena = fields.Char(string="Produktua", required=True, index=True)
    ordainduta = fields.Boolean(string="Ordainduta", default=False, index=True)
    kantitatea = fields.Integer(string="Kantitatea", required=True)
    diru_totala = fields.Float(string="Diru totala", required=True)

    _sql_constraints = [
        ("day_product_unique", "unique(eguna, produktua_id, ordainduta)", "Egun/produktua/ordainduta konbinazioa bakarra izan behar da."),
    ]

    # Produktu arrakastatsuen estatistikak API-tik kalkulatu eta Odoo-n gordetzen ditu
    @api.model
    def _eguneratu_datuak(self):
        erreserbak = self._api_request("GET", "/api/Erreserbak") or []
        eskariak = self._api_request("GET", "/api/Eskariak") or []

        erreserba_index = {}
        for r in erreserbak:
            if not isinstance(r, dict):
                continue
            erreserba_id = r.get("id")
            if erreserba_id is None:
                continue
            dt = self._parse_api_datetime(r.get("egunaOrdua"))
            if not dt:
                continue
            erreserba_index[int(erreserba_id)] = {
                "day": dt.date(),
                "paid": int(r.get("ordainduta") or 0) == 1,
            }

        agg = {}
        for e in eskariak:
            if not isinstance(e, dict):
                continue
            erreserba_id = e.get("erreserbaId")
            if erreserba_id is None:
                continue
            info = erreserba_index.get(int(erreserba_id))
            if not info:
                continue

            day = info["day"]
            paid = bool(info["paid"])

            for p in e.get("produktuak") or []:
                if not isinstance(p, dict):
                    continue
                pid = p.get("produktuaId")
                pname = p.get("produktuaIzena") or ""
                qty = int(p.get("kantitatea") or 0)
                price = float(p.get("prezioa") or 0.0)
                if pid is None or qty <= 0:
                    continue

                key = (day, int(pid), pname, paid)
                a = agg.setdefault(key, {"qty": 0, "amount": 0.0})
                a["qty"] += qty
                a["amount"] += qty * price

        self.sudo().search([]).unlink()
        vals_list = []
        for (day, pid, pname, paid), a in sorted(agg.items(), key=lambda x: (x[0][0], x[0][2])):
            vals_list.append(
                {
                    "eguna": day,
                    "produktua_id": pid,
                    "produktua_izena": pname or str(pid),
                    "ordainduta": paid,
                    "kantitatea": int(a["qty"]),
                    "diru_totala": float(a["amount"]),
                }
            )
        if vals_list:
            self.sudo().create(vals_list)
        return True

    # UI-tik botoia sakatzean erabiltzen da: datuak eguneratu eta pantaila berriz kargatu
    @api.model
    def action_eguneratu(self):
        self._eguneratu_datuak()
        return {"type": "ir.actions.client", "tag": "reload"}


class ErronkaEstatistikaOsagaiaStock(models.Model):
    _name = "erronka.estatistika.osagaia_stock"
    _description = "Osagaien stock estatistikak"
    _inherit = "erronka.api.mixin"

    osagaia_id = fields.Integer(string="Osagaia ID", required=True, index=True)
    osagaia_izena = fields.Char(string="Osagaia", required=True, index=True)
    stock = fields.Integer(string="Stock", required=True)
    prezioa = fields.Float(string="Prezioa", required=True)
    azken_eguneraketa = fields.Datetime(string="Azken eguneraketa", required=True, default=lambda self: fields.Datetime.now())

    _sql_constraints = [
        ("osagaia_unique", "unique(osagaia_id)", "Osagai bakoitzeko erregistro bakarra egon daiteke."),
    ]

    # Osagaien stocka API-tik sinkronizatu eta Odoo-n gordetzen du
    @api.model
    def _eguneratu_datuak(self):
        osagaiak = self._api_request("GET", "/api/Osagaiak") or []

        self.sudo().search([]).unlink()
        vals_list = []
        now = fields.Datetime.now()
        for o in osagaiak:
            if not isinstance(o, dict):
                continue
            oid = o.get("id")
            if oid is None:
                continue
            vals_list.append(
                {
                    "osagaia_id": int(oid),
                    "osagaia_izena": o.get("izena") or str(oid),
                    "stock": int(o.get("stock") or 0),
                    "prezioa": float(o.get("prezioa") or 0.0),
                    "azken_eguneraketa": now,
                }
            )
        if vals_list:
            self.sudo().create(vals_list)
        return True

    # UI-tik botoia sakatzean erabiltzen da: datuak eguneratu eta pantaila berriz kargatu
    @api.model
    def action_eguneratu(self):
        self._eguneratu_datuak()
        return {"type": "ir.actions.client", "tag": "reload"}


class ErronkaEstatistikaDashboard(models.TransientModel):
    _name = "erronka.estatistika.dashboard"
    _description = "Estatistiken dashboard-a"

    salmenta_totala = fields.Float(string="Salmenta totala (hist.)", readonly=True)
    erreserba_kopurua = fields.Integer(string="Erreserba kopurua (hist.)", readonly=True)
    ticket_batezbestekoa = fields.Float(string="Ticket batezbestekoa (hist.)", readonly=True)

    top_produktua = fields.Char(string="Top produktua", readonly=True)
    top_kantitatea = fields.Integer(string="Top kantitatea", readonly=True)

    stock_gutxi_kopurua = fields.Integer(string="Stock gutxi (osagaiak)", readonly=True)

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)

        salmentak = self.env["erronka.estatistika.salmenta"].sudo().search([])
        total = sum(s.salmenta_totala for s in salmentak)
        count = sum(s.erreserba_kopurua for s in salmentak)
        avg = total / count if count else 0.0

        produktuak = self.env["erronka.estatistika.produktua"].sudo().search([("ordainduta", "=", True)])
        top = {}
        for p in produktuak:
            key = p.produktua_izena or str(p.produktua_id)
            top[key] = top.get(key, 0) + int(p.kantitatea)
        top_name, top_qty = ("", 0)
        if top:
            top_name, top_qty = max(top.items(), key=lambda x: x[1])

        stock_gutxi = self.env["erronka.estatistika.osagaia_stock"].sudo().search([("stock", "<", 10)])

        res.update(
            {
                "salmenta_totala": float(total),
                "erreserba_kopurua": int(count),
                "ticket_batezbestekoa": float(avg),
                "top_produktua": top_name,
                "top_kantitatea": int(top_qty),
                "stock_gutxi_kopurua": int(len(stock_gutxi)),
            }
        )
        return res


class ErronkaEstatistikaEguneratuWizard(models.TransientModel):
    _name = "erronka.estatistika.eguneratu.wizard"
    _description = "Estatistikak eguneratzeko wizard-a"

    # Wizard honek hiru taulak batera eguneratzeko botoia eskaintzen du
    def action_eguneratu_dena(self):
        self.env["erronka.estatistika.salmenta"]._eguneratu_datuak()
        self.env["erronka.estatistika.produktua"]._eguneratu_datuak()
        self.env["erronka.estatistika.osagaia_stock"]._eguneratu_datuak()
        return {"type": "ir.actions.act_window_close"}
