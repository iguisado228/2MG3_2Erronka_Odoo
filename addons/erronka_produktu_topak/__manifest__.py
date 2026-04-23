# -*- coding: utf-8 -*-
{
    "name": "Erronka Eguneko Produktu Topak",
    "summary": "Eskuz aukeratutako daten araberako eguneko produktu salduenen topa",
    "category": "Txostenak",
    "version": "16.0.1.0.0",
    "license": "LGPL-3",
    "author": "Goierri Eskola",
    "depends": ["base", "Erronka_estatistikak"],
    "data": [
        "segurtasuna/ir.model.access.csv",
        "bistak/produktu_topak_bistak.xml",
        "bistak/menua.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "erronka_produktu_topak/static/src/css/produktu_topak.css",
        ],
    },
    "application": True,
    "installable": True,
}
