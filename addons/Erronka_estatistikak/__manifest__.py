# -*- coding: utf-8 -*-
{
    # Moduluaren izena Odoo-n (Apps-en agertzen dena)
    "name": "Erronka Estatistikak",
    # Laburpena: zertarako den, esaldi batean
    "summary": "Jatetxerako estatistikak (salmentak, produktu arrakastatsuak, stocka)",
    # Kategoria: Odoo-ko menuan/Apps-en antolaketa egiteko
    "category": "Txostenak",
    # Bertsioa: 16.0 = Odoo 16, eta gero gure bertsio txikia
    "version": "16.0.1.0.0",
    # Lizentzia (Odoo addoietan normala)
    "license": "LGPL-3",
    # Egilea
    "author": "Goierri Eskola",
    # Mendekotasunak: `board` behar da dashboard grafiko motarako
    "depends": ["base", "board"],
    "assets": {
        # CSS/SCSS: dashboard-eko itxura apur bat ukitzeko
        "web.assets_backend_legacy_lazy": [
            "Erronka_estatistikak/static/src/scss/dashboard.scss",
        ],
        "web.assets_backend": [
            "Erronka_estatistikak/static/src/scss/dashboard.scss",
        ],
    },
    "data": [
        # Segurtasuna: zein taldeek (group_user) irakurri/idatzi/… egin dezaketen
        "security/ir.model.access.csv",
        # View-ak eta action-ak (grafikoak, botoiak, server action-ak, wizard-a…)
        "views/estatistikak_views.xml",
        # Menua (Estatistikak → …)
        "views/menu.xml",
    ],
    # Aplikazio moduan agertzeko (menu propioarekin)
    "application": True,
    # Instalagarri dagoen ala ez
    "installable": True,
}
