import json
import os
from collections import defaultdict
from datetime import timedelta

import requests

from odoo import _, api, fields, models
from odoo.exceptions import UserError


class ErronkaProduktuTopApiMixina(models.AbstractModel):
    _name = "erronka.produktu.top.api.mixina"
    _description = "Produktu topetarako API mixina"

    def _api_base_url(self):
        return os.getenv("ERRONKA_API_URL", "http://host.docker.internal:8080").rstrip("/")

    def _api_headers(self):
        api_key = os.getenv("ERRONKA_API_KEY", "")
        headers = {"Accept": "application/json"}
        if api_key:
            headers["X-API-Key"] = api_key
        return headers

    def _api_request(self, metodoa, amaiera_puntua):
        url = f"{self._api_base_url()}{amaiera_puntua}"
        erantzuna = requests.request(
            metodoa,
            url,
            headers=self._api_headers(),
            timeout=30,
        )
        erantzuna.raise_for_status()

        if not erantzuna.text:
            return []

        edukia = erantzuna.json()
        if isinstance(edukia, str):
            edukia = json.loads(edukia)
        return edukia


class ErronkaEgunekoProduktuTopa(models.Model):
    _name = "erronka.eguneko.produktu.topa"
    _description = "Eguneko produktu salduenen topa"
    _inherit = "erronka.produktu.top.api.mixina"
    _order = "eguna desc, posizioa asc, kantitatea desc"
    _rec_name = "produktua_izena"

    eguna = fields.Date(string="Eguna", required=True, index=True)
    posizioa = fields.Integer(string="Posizioa", required=True, group_operator=False)
    produktua_id = fields.Integer(string="Produktu ID", required=True, index=True)
    produktua_izena = fields.Char(string="Produktua", required=True, index=True)
    kantitatea = fields.Integer(string="Kantitatea", required=True, group_operator=False)
    diru_totala = fields.Float(string="Diru totala", required=True, group_operator=False)
    hasiera_data = fields.Date(string="Hasiera data", required=True, readonly=True)
    amaiera_data = fields.Date(string="Amaiera data", required=True, readonly=True)
    top_muga = fields.Integer(string="Eguneko top muga", required=True, readonly=True, group_operator=False)
    eguneko_azkena = fields.Boolean(string="Eguneko azkena", readonly=True, group_operator=False)

    @api.model
    def _irakurri_iturburua_estatistiketatik(self, hasiera_data, amaiera_data, iturburua_eguneratu=False):
        iturburu_modeloa = self.env["erronka.estatistika.produktua"].sudo()
        if iturburua_eguneratu and hasattr(iturburu_modeloa, "_eguneratu_datuak"):
            iturburu_modeloa._eguneratu_datuak()

        domain = [
            ("eguna", ">=", hasiera_data),
            ("eguna", "<=", amaiera_data),
            ("ordainduta", "=", True),
        ]
        return iturburu_modeloa.search(domain)

    @api.model
    def _irakurri_iturburua_apitik(self, hasiera_data, amaiera_data):
        erreserbak = self._api_request("GET", "/api/Erreserbak") or []
        eskariak = self._api_request("GET", "/api/Eskariak") or []

        hasiera = fields.Date.to_date(hasiera_data)
        amaiera = fields.Date.to_date(amaiera_data)

        erreserba_egunak = {}
        for erreserba in erreserbak:
            if not erreserba.get("ordainduta"):
                continue

            data_testua = erreserba.get("eguna")
            if not data_testua:
                continue

            try:
                eguna = fields.Date.to_date(data_testua)
            except Exception:
                continue

            if hasiera <= eguna <= amaiera:
                erreserba_egunak[erreserba.get("id")] = eguna

        lineak = []
        for eskaria in eskariak:
            eguna = erreserba_egunak.get(eskaria.get("erreserbaId"))
            if not eguna:
                continue

            for produktua in eskaria.get("produktuak", []):
                produktua_id = produktua.get("produktuaId")
                izena = produktua.get("produktuIzena")
                if not produktua_id or not izena:
                    continue

                lineak.append(
                    {
                        "eguna": eguna,
                        "produktua_id": int(produktua_id),
                        "produktua_izena": izena,
                        "kantitatea": int(produktua.get("kantitatea", 0) or 0),
                        "diru_totala": float(produktua.get("prezioa", 0.0) or 0.0),
                    }
                )
        return lineak

    @api.model
    def _eskuratu_iturburu_lerroak(self, hasiera_data, amaiera_data, iturburua_eguneratu=False):
        if "erronka.estatistika.produktua" in self.env:
            erregistroak = self._irakurri_iturburua_estatistiketatik(
                hasiera_data,
                amaiera_data,
                iturburua_eguneratu=iturburua_eguneratu,
            )
            return [
                {
                    "eguna": erregistroa.eguna,
                    "produktua_id": erregistroa.produktua_id,
                    "produktua_izena": erregistroa.produktua_izena,
                    "kantitatea": erregistroa.kantitatea,
                    "diru_totala": erregistroa.diru_totala,
                }
                for erregistroa in erregistroak
            ]

        return self._irakurri_iturburua_apitik(hasiera_data, amaiera_data)

    @api.model
    def _eraiki_eguneko_topa(self, hasiera_data, amaiera_data, top_muga=5, iturburua_eguneratu=False):
        hasiera = fields.Date.to_date(hasiera_data)
        amaiera = fields.Date.to_date(amaiera_data)

        if hasiera > amaiera:
            raise UserError(_("Hasiera-data ezin da amaiera-data baino beranduagoa izan."))
        if top_muga < 1:
            raise UserError(_("Topako produktu kopurua zero baino handiagoa izan behar da."))

        lineak = self._eskuratu_iturburu_lerroak(
            hasiera_data,
            amaiera_data,
            iturburua_eguneratu=iturburua_eguneratu,
        )

        agregados = defaultdict(lambda: {"kantitatea": 0, "diru_totala": 0.0})
        for linea in lineak:
            key = (linea["eguna"], linea["produktua_id"], linea["produktua_izena"])
            agregados[key]["kantitatea"] += int(linea["kantitatea"] or 0)
            agregados[key]["diru_totala"] += float(linea["diru_totala"] or 0.0)

        egunekoak = defaultdict(list)
        for (eguna, produktua_id, produktua_izena), balioak in agregados.items():
            egunekoak[eguna].append(
                {
                    "produktua_id": produktua_id,
                    "produktua_izena": produktua_izena,
                    "kantitatea": balioak["kantitatea"],
                    "diru_totala": balioak["diru_totala"],
                }
            )

        balio_zerrenda = []
        for eguna in sorted(egunekoak.keys()):
            sailkatuta = sorted(
                egunekoak[eguna],
                key=lambda item: (
                    -item["kantitatea"],
                    -item["diru_totala"],
                    item["produktua_izena"].lower(),
                ),
            )
            hautatutakoak = sailkatuta[:top_muga]
            for posizioa, item in enumerate(hautatutakoak, start=1):
                balio_zerrenda.append(
                    {
                        "eguna": eguna,
                        "posizioa": posizioa,
                        "produktua_id": item["produktua_id"],
                        "produktua_izena": item["produktua_izena"],
                        "kantitatea": item["kantitatea"],
                        "diru_totala": item["diru_totala"],
                        "hasiera_data": hasiera,
                        "amaiera_data": amaiera,
                        "top_muga": top_muga,
                        "eguneko_azkena": posizioa == len(hautatutakoak),
                    }
                )
        return balio_zerrenda

    @api.model
    def kargatu_estatistikak(self, hasiera_data, amaiera_data, top_muga=5, iturburua_eguneratu=False):
        balio_zerrenda = self._eraiki_eguneko_topa(
            hasiera_data,
            amaiera_data,
            top_muga=top_muga,
            iturburua_eguneratu=iturburua_eguneratu,
        )
        self.sudo().search([]).unlink()
        if balio_zerrenda:
            self.sudo().create(balio_zerrenda)
        return len(balio_zerrenda)


class ErronkaEgunekoProduktuTopaMorroia(models.TransientModel):
    _name = "erronka.eguneko.produktu.topa.morroia"
    _description = "Eguneko produktu topen morroia"

    hasiera_data = fields.Date(
        string="Hasiera data",
        required=True,
        default=lambda self: self._default_hasiera_data(),
    )
    amaiera_data = fields.Date(
        string="Amaiera data",
        required=True,
        default=fields.Date.context_today,
    )
    top_muga = fields.Integer(string="Eguneko produktu kopurua", required=True, default=5)
    iturburua_eguneratu = fields.Boolean(
        string="Iturburuko datuak eguneratu",
        default=False,
        help="Aktibatuta badago eta estatistiken modulua existitzen bada, jatorrizko taula freskatzen du topa kalkulatu aurretik.",
    )

    @api.model
    def _default_hasiera_data(self):
        gaur = fields.Date.to_date(fields.Date.context_today(self))
        return gaur - timedelta(days=6)

    def action_sortu(self):
        self.ensure_one()

        emaitza_kopurua = self.env["erronka.eguneko.produktu.topa"].kargatu_estatistikak(
            self.hasiera_data,
            self.amaiera_data,
            top_muga=self.top_muga,
            iturburua_eguneratu=self.iturburua_eguneratu,
        )

        ekintza = self.env.ref("erronka_produktu_topak.action_erronka_eguneko_produktu_topa").read()[0]
        ekintza["domain"] = [
            ("hasiera_data", "=", self.hasiera_data),
            ("amaiera_data", "=", self.amaiera_data),
        ]
        ekintza["context"] = dict(self.env.context)
        if emaitza_kopurua:
            ekintza["context"]["search_default_taldekatu_eguna"] = 1
        return ekintza
