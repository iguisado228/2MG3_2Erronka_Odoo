# -*- coding: utf-8 -*-

import json

from odoo import http
from odoo.http import Response, request


class LangileakAPI(http.Controller):
    @http.route("/api/lanpostuak", type="http", auth="public", methods=["GET", "POST"], csrf=False)
    def obtener_lanpostuak(self, **kwargs):
        token_esperado = "MI_TOKEN_SECRETO_123"
        token_recibido = kwargs.get("token")

        if token_recibido != token_esperado:
            return Response(json.dumps({"error": "No autorizado"}), status=401, content_type="application/json")

        try:
            lanpostuak = request.env["erronka.lanpostu"].sudo().search_read([], ["name", "external_id", "active"])

            datos_formateados = []
            for lanpostu in lanpostuak:
                datos_formateados.append(
                    {
                        "id": lanpostu.get("external_id") or lanpostu.get("id"),
                        "lanpostua": lanpostu.get("name") or "",
                        "active": bool(lanpostu.get("active")),
                    }
                )

            return Response(
                json.dumps({"success": True, "data": datos_formateados}),
                status=200,
                content_type="application/json;charset=utf-8",
            )
        except Exception as exc:
            return Response(
                json.dumps({"success": False, "error": str(exc)}),
                status=500,
                content_type="application/json;charset=utf-8",
            )

    @http.route("/api/langileak", type="http", auth="public", methods=["GET", "POST"], csrf=False)
    def obtener_langileak(self, **kwargs):
        token_esperado = "MI_TOKEN_SECRETO_123"
        token_recibido = kwargs.get("token")

        if token_recibido != token_esperado:
            return Response(json.dumps({"error": "No autorizado"}), status=401, content_type="application/json")

        try:
            langileak = request.env["erronka.langile"].sudo().search_read(
                [],
                [
                    "izena",
                    "abizena",
                    "nan",
                    "erabiltzaile_izena",
                    "langile_kodea",
                    "password_hash",
                    "helbidea",
                    "lanpostu_id",
                    "external_id",
                    "active",
                ],
            )

            datos_formateados = []
            for langile in langileak:
                lanpostu_id = False
                if langile.get("lanpostu_id"):
                    lanpostu = request.env["erronka.lanpostu"].sudo().browse(langile["lanpostu_id"][0])
                    lanpostu_id = lanpostu.external_id or lanpostu.id

                datos_formateados.append(
                    {
                        "id": langile.get("external_id") or langile.get("id"),
                        "izena": langile.get("izena") or "",
                        "abizena": langile.get("abizena") or "",
                        "NAN": langile.get("nan") or "",
                        "erabiltzaile_izena": langile.get("erabiltzaile_izena") or "",
                        "langile_kodea": langile.get("langile_kodea") or 0,
                        "pasahitza": langile.get("password_hash") or "",
                        "helbidea": langile.get("helbidea") or "",
                        "lanpostuak_id": lanpostu_id,
                        "active": bool(langile.get("active")),
                    }
                )

            return Response(
                json.dumps({"success": True, "data": datos_formateados}),
                status=200,
                content_type="application/json;charset=utf-8",
            )
        except Exception as exc:
            return Response(
                json.dumps({"success": False, "error": str(exc)}),
                status=500,
                content_type="application/json;charset=utf-8",
            )

