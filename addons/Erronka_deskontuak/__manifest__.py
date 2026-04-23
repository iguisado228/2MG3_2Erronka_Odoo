# -*- coding: utf-8 -*-
{
    'name': "Deskontuen Kudeaketa",

    'summary': """
        Deskontu kodeak kudeatzeko modulua.""",

    'description': """
        Modulu honek deskontu kodeak sortzea eta kudeatzea ahalbidetzen du, prozesu ezberdinetan aplikatu ahal izateko.
    """,

    'author': "Jon",
    'website': "https://www.yourcompany.com",

    'category': 'Sales',
    'version': '1.0',

    'depends': ['base'],

    'data': [
        'security/ir.model.access.csv',
        'views/views.xml',
        'views/templates.xml',
    ],
    'demo': [
        'demo/demo.xml',
    ],
    'application': True,
    'installable': True,
}
