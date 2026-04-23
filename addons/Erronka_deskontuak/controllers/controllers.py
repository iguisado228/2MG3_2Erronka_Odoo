# -*- coding: utf-8 -*-
from odoo import http
from odoo.http import request
import json
from odoo import fields

class DeskontuakAPI(http.Controller):

    @http.route('/api/deskontuak/aktiboak', type='http', auth='public', methods=['GET'], csrf=False)
    def deskontu_aktiboak(self, **kw):
        """Aktibo dauden deskontu guztien zerrenda itzultzen du."""
        deskontuak = request.env['deskontuak.deskontua'].sudo().search([('aktiboa', '=', True)])
        data = []
        for d in deskontuak:
            data.append({
                'kodea': d.name,
                'mota': d.mota,
                'balioa': d.balioa,
                'deskribapena': d.deskribapena or '',
                'amaiera_data': d.amaiera_data.strftime('%Y-%m-%d') if d.amaiera_data else None
            })
        
        return request.make_response(
            json.dumps(data),
            headers=[('Content-Type', 'application/json')]
        )

    @http.route('/api/deskontuak/guztiak', type='http', auth='public', methods=['GET'], csrf=False)
    def deskontu_guztiak(self, **kw):
        """Deskontu guztien zerrenda itzultzen du (aktiboak eta ez-aktiboak)."""
        deskontuak = request.env['deskontuak.deskontua'].sudo().search([])
        data = []
        for d in deskontuak:
            data.append({
                'kodea': d.name,
                'mota': d.mota,
                'balioa': d.balioa,
                'aktiboa': d.aktiboa,
                'deskribapena': d.deskribapena or '',
                'hasiera_data': d.hasiera_data.strftime('%Y-%m-%d') if d.hasiera_data else None,
                'amaiera_data': d.amaiera_data.strftime('%Y-%m-%d') if d.amaiera_data else None
            })
        
        return self._json_response(data)

    @http.route('/api/deskontuak/balioztatu/<string:kodea>', type='http', auth='public', methods=['GET'], csrf=False)
    def deskontua_balioztatu(self, kodea, **kw):
        """Kode baten baliozkotasuna egiaztatzen du."""
        deskontua = request.env['deskontuak.deskontua'].sudo().search([
            ('name', '=', kodea),
            ('aktiboa', '=', True)
        ], limit=10)

        today = fields.Date.today()
        if deskontua:
            if deskontua.hasiera_data and deskontua.hasiera_data > today:
                return self._json_response({'baliozkoa': False, 'mezua': 'Kodea oraindik ez da hasi.'})
            if deskontua.amaiera_data and deskontua.amaiera_data < today:
                return self._json_response({'baliozkoa': False, 'mezua': 'Kodea iraungita dago.'})
            
            return self._json_response({
                'baliozkoa': True,
                'kodea': deskontua.name,
                'mota': deskontua.mota,
                'balioa': deskontua.balioa
            })
        
        return self._json_response({'baliozkoa': False, 'mezua': 'Kodea ez da existitzen edo ez dago aktibo.'}, status=404)

    def _json_response(self, data, status=200):
        return request.make_response(
            json.dumps(data),
            headers=[('Content-Type', 'application/json')],
            status=status
        )