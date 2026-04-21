# -*- coding: utf-8 -*-
{
    "name": "Erronka Estatistikak",
    "summary": "Jatetxerako estatistikak (salmentak, produktu arrakastatsuak, stocka)",
    "category": "Txostenak",
    "version": "16.0.1.0.0",
    "license": "LGPL-3",
    "author": "Goierri Eskola",
    "depends": ["base", "board"],
    "assets": {
        "web.assets_backend_legacy_lazy": [
            "Erronka_estatistikak/static/src/scss/dashboard.scss",
        ],
        "web.assets_backend": [
            "Erronka_estatistikak/static/src/scss/dashboard.scss",
        ],
    },
    "data": [
        "security/ir.model.access.csv",
        "views/estatistikak_views.xml",
        "views/menu.xml",
    ],
    "application": True,
    "installable": True,
}
