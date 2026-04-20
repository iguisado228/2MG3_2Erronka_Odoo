# -*- coding: utf-8 -*-
{
    "name": "Erronka Langileak",
    "summary": "Gestión de trabajadores (langileak) y puestos (lanpostuak)",
    "category": "Recursos humanos",
    "version": "16.0.1.0.0",
    "license": "LGPL-3",
    "author": "Goierri Eskola",
    "website": "",
    "depends": ["base"],
    "data": [
        "security/ir.model.access.csv",
        "views/langile_views.xml",
        "views/lanpostu_views.xml",
        "views/menu.xml",
    ],
    "application": True,
    "installable": True,
}
