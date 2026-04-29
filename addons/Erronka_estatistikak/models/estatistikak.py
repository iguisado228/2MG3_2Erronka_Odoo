# -*- coding: utf-8 -*-

import json
import os
from datetime import datetime

from odoo import _, api, fields, models
from odoo.exceptions import UserError


class ErronkaApiMixin(models.AbstractModel):
    # Mixin modukoa: beste modeloek heredatzen dute, APIarekin egiteko “tresnak” hemen daude.
    # Ideia: Salmentak/Produktuak/Stocka modeloek ez dute API kodea errepikatzen.
    _name = "erronka.api.mixin"
    _description = "Erronka API utilitateak"

    # API helbidea: ingurune-aldagai bidez alda daiteke (docker/hosten arabera), kodea ukitu gabe.
    @api.model
    def _api_base_url(self):
        return os.environ.get("ERRONKA_API_BASE_URL", "http://192.168.10.5:5000")

    # APIari deia: method + path → JSON bueltatzen du.
    # Huts egiten badu, UserError botatzen du (Odoo-n popup moduan agertzeko).
    @api.model
    def _api_request(self, method, path, payload=None, params=None):
        try:
            import requests
        except Exception as exc:
            raise UserError(_("Odoo ingurunean 'requests' falta da.")) from exc

        url = self._api_base_url().rstrip("/") + path
        headers = {"Content-Type": "application/json"}

        try:
            # Hemen egiten da benetako HTTP request-a
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
            # Errorea dagoenean, ahal bada APIko erantzunaren testua jasotzen saiatzen da (laguntzeko).
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
            # 204 = edukirik ez. Horrelakoetan None itzultzen dugu.
            return None

        try:
            return resp.json()
        except Exception as exc:
            # API-k ez badu JSON ondo ematen, Odoo-n errore ulergarri bat erakutsi
            raise UserError(_("API erantzuna ez da JSON baliozkoa.")) from exc

    # APIko data/ordu testuak batzuetan formatu ezberdinetan datoz; hau “normalizatzeko” da.
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

    @api.model
    def _replace_all(self, vals_list):
        # Sinkronizazio estiloa: aurreko erregistroak ezabatu, eta berriak sortu.
        # Hau ondo dago “source of truth” APIa denean.
        self.sudo().search([]).unlink()
        if vals_list:
            self.sudo().create(vals_list)
        return True

    @api.model
    def action_eguneratu(self):
        # UIko botoiak (XML-eko button type="object") metodo hau deitzen du normalean.
        # Lehenengo datuak eguneratu eta gero pantaila reload.
        self._eguneratu_datuak()
        return {"type": "ir.actions.client", "tag": "reload"}


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
        # Egun bakoitzeko lerro bakarra: bestela grafikoan datuak bikoiztuta aterako lirateke.
        ("eguna_unique", "unique(eguna)", "Egun bakoitzeko erregistro bakarra egon daiteke."),
    ]

    @api.depends("eguna")
    def _compute_eguna_keys(self):
        # Hauek “group by” egiteko giltzak dira (egun/mes/hiruhileko/urte).
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

    # Salmentak API-tik hartu, egunaren arabera batu, eta Odoo-n gordetzen du (grafikoetarako).
    @api.model
    def _eguneratu_datuak(self):
        # API-tik erreserbak ekarri
        erreserbak = self._api_request("GET", "/api/Erreserbak") or []

        # Egun bakoitzerako totalak eta kopuruak kalkulatzeko map-a
        by_day = {}
        for r in erreserbak:
            if not isinstance(r, dict):
                continue
            # Ordainduta ez badago, ez dugu kontuan hartzen
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

        # Odoo-n sortuko ditugun erregistroen lista prestatzen
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
        # DB-a “garbi” uzten du: dena ordezkatzen du azken kalkuluarekin
        return self._replace_all(vals_list)


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
        # Egun + produktu + ordainduta konbinazioa bakarra: datuak ez bikoizteko.
        ("day_product_unique", "unique(eguna, produktua_id, ordainduta)", "Egun/produktua/ordainduta konbinazioa bakarra izan behar da."),
    ]

    # Produktuen estatistikak: erreserbak + eskariak lotu, eta produktu bakoitzeko agregatu.
    @api.model
    def _eguneratu_datuak(self):
        # Bi endpoint: erreserbak (data + ordainduta) eta eskariak (produktuak)
        erreserbak = self._api_request("GET", "/api/Erreserbak") or []
        eskariak = self._api_request("GET", "/api/Eskariak") or []

        # Erreserba bakoitzari eguna eta paid egoera “indexatu” (join azkarra egiteko)
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

        # Hemen batzen ditugu kantitateak eta dirua produktuaren arabera
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

            # Eskari barruko produktu bakoitza prozesatu
            for p in e.get("produktuak") or []:
                if not isinstance(p, dict):
                    continue
                pid = p.get("produktuaId")
                pname = p.get("produktuaIzena") or ""
                qty = int(p.get("kantitatea") or 0)
                price = float(p.get("prezioa") or 0.0)
                if pid is None or qty <= 0:
                    continue

                # Gakoa: egun + produktu + izena + paid → horren barruan pilatzen dugu
                key = (day, int(pid), pname, paid)
                a = agg.setdefault(key, {"qty": 0, "amount": 0.0})
                a["qty"] += qty
                a["amount"] += qty * price

        # DB-ra bidaltzeko erregistro zerrenda prestatzen
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
        # Azken emaitza: dena ordezkatu
        return self._replace_all(vals_list)


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
        # Osagai bakoitzak erregistro bakarra: id-a unique.
        ("osagaia_unique", "unique(osagaia_id)", "Osagai bakoitzeko erregistro bakarra egon daiteke."),
    ]

    # Stocka: API-tik osagai zerrenda hartu eta Odoo-n sinkronizatu.
    @api.model
    def _eguneratu_datuak(self):
        osagaiak = self._api_request("GET", "/api/Osagaiak") or []

        vals_list = []
        now = fields.Datetime.now()
        # APIko osagai bakoitza Odoo-ko erregistro bihurtu
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
        # Stock taula ere “source of truth” moduan: beti ordezkatu azkenarekin
        return self._replace_all(vals_list)


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
        # Dashboard-a irekitzean automatikoki kalkulatzeko (form-a bete aurretik).
        res = super().default_get(fields_list)

        # Salmentetatik totalak eta batezbestekoa atera
        salmentak = self.env["erronka.estatistika.salmenta"].sudo().search([])
        total = sum(s.salmenta_totala for s in salmentak)
        count = sum(s.erreserba_kopurua for s in salmentak)
        avg = total / count if count else 0.0

        # Ordaindutako produktuetatik top produktua kalkulatu (kantitate gehien duena)
        produktuak = self.env["erronka.estatistika.produktua"].sudo().search([("ordainduta", "=", True)])
        top = {}
        for p in produktuak:
            key = p.produktua_izena or str(p.produktua_id)
            top[key] = top.get(key, 0) + int(p.kantitatea)
        top_name, top_qty = ("", 0)
        if top:
            top_name, top_qty = max(top.items(), key=lambda x: x[1])

        # Stock gutxiko osagaiak kontatu (hemen <10 jarrita dago)
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

    # Wizard/popup hau “dena batera eguneratu” egiteko da, erabiltzaileak klik bakarrean egin dezan.
    def action_eguneratu_dena(self):
        # Hiru modeloak eguneratu (salmenta + produktua + stocka)
        for model in ("erronka.estatistika.salmenta", "erronka.estatistika.produktua", "erronka.estatistika.osagaia_stock"):
            self.env[model]._eguneratu_datuak()
        # Popup-a ixteko action bat bueltatzen dugu
        return {"type": "ir.actions.act_window_close"}
