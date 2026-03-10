#-*- coding: utf-8 -*-

from odoo import models, fields, api


class profesor(models.Model):
    _name = 'escuela.profesor'
    _description = 'profesor'

    name = fields.Char(string='Nombre', required=True)
    fotografia = fields.Binary(string='Fotografía')
    description = fields.Text(string='Descripción')
    age = fields.Integer(string='Edad', required=True)
    birthday = fields.Date(string='Fecha de nacimiento')
    saldo = fields.Float(string='Saldo')
    estado = fields.Boolean(string='Estado del profesor', default=True)
    grado = fields.Selection(string='Grado', selection=[('primaria', 'Primaria'), ('secundaria', 'Secundaria'), ('universidad', 'Universidad')], default='primaria', required=True) 
    alumno = fields.One2many('escuela.alumno', 'profesor', string='Alumnos')
    materia = fields.Many2many(comodel_name='escuela.materia', relation_name='escuelas_materias', column1='escuela_id', column2='materia_id', string='Materias')

class alumno(models.Model):
    _name = 'escuela.alumno'
    _description = 'alumno'

    name = fields.Char(string='Nombre', required=True)
    fotografia = fields.Binary(string='Fotografía')
    age = fields.Integer(string='Edad', required=True)
    gender = fields.Selection(string='Género', selection=[('masculino', 'Masculino'), ('femenino', 'Femenino'), ('otro', 'Otro')], default='masculino', required=True)
    profesor = fields.Many2one('escuela.profesor', string='Profesor')
    notas_id = fields.One2many('escuela.nota', 'alumno_id', string='Notas')

class materia(models.Model):
    _name = 'escuela.materia'
    _description = 'materias'

    name = fields.Char(string='Nombre', required=True)
    profesor = fields.Many2many(comodel_name='escuela.profesor', relation_name='escuelas_materias', column1='materia_id', column2='escuela_id', string='Profesores')
    notas_id = fields.One2many('escuela.nota', 'materia_id', string='Notas')
    alumnos_id = fields.Many2many('escuela.alumno', string='Alumnos', compute='_compute_alumnos')

    @api.depends('notas_id', 'notas_id.alumno_id')
    def _compute_alumnos(self):
        for materia in self:
            materia.alumnos_id = materia.notas_id.mapped('alumno_id')


class nota(models.Model):
    _name = 'escuela.nota'
    _description = 'Nota de Alumno en Materia'

    alumno_id = fields.Many2one('escuela.alumno', string='Alumno', required=True)
    materia_id = fields.Many2one('escuela.materia', string='Materia', required=True)
    nota = fields.Float(string='Nota', required=True)
    estado = fields.Char(string='Estado', compute='_compute_estado')

    @api.depends('nota')
    def _compute_estado(self):
        for record in self:
            if record.nota >= 5.0:
                record.estado = 'Aprobado'
            else:
                record.estado = 'Suspenso'