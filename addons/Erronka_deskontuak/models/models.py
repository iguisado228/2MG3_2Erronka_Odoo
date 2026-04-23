# -*- coding: utf-8 -*-

from odoo import models, fields, api

class Deskontua(models.Model):
    _name = 'deskontuak.deskontua'
    _description = 'Deskontu Kodea'

    name = fields.Char(string='Kodea', required=True)
    mota = fields.Selection([
        ('finkoa', 'Finkoa'),
        ('ehunekoa', 'Ehunekoa')
    ], string='Deskontu Mota', default='finkoa', required=True)
    balioa = fields.Float(string='Balioa', required=True)
    aktiboa = fields.Boolean(string='Aktiboa', default=True)
    hasiera_data = fields.Date(string='Hasiera Data')
    amaiera_data = fields.Date(string='Amaiera Data')
    deskribapena = fields.Text(string='Deskribapena')

    _sql_constraints = [
        ('name_unique', 'unique(name)', 'Deskontu kodea bakarra izan behar da.')
    ]
