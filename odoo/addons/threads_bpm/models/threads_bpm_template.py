from datetime import timedelta
from odoo import api, fields, models
from odoo.exceptions import ValidationError
import logging

_logger = logging.getLogger(__name__)


class ThreadsBPMTemplate(models.Model):
    _name = "threads_bpm.template"
    _description = "Threads BPM Template"
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = "name"

    name = fields.Char(required=True, string="Nome do Modelo")
    description = fields.Text(string="Descrição")

    template_type = fields.Selection([
        ("thread", "Thread (Pontual)"),
        ("process", "Processo (Recorrente)")
    ], required=True, string="Tipo")

    business_unit = fields.Selection([
        ("platform", "Plataforma"),
        ("b2b", "B2B"),
        ("b2c", "B2C"),
        ("qa_trust", "QA & Trust"),
        ("management", "Gestão"),
        ("board", "Board"),
    ], required=True, string="Unidade de Negócio")

    owner_id = fields.Many2one("res.users", string="Dono do Modelo",
                              default=lambda self: self.env.user, required=True)

    active = fields.Boolean(default=True)

    # Auto-recreation (only for processes)
    auto_recreate = fields.Boolean(string="Recriação Automática")
    recreate_interval = fields.Integer(string="A cada X", default=1)
    recreate_unit = fields.Selection([
        ("days", "Dias"),
        ("weeks", "Semanas"),
        ("months", "Meses")
    ], default="days", string="Unidade")

    # Steps
    step_ids = fields.One2many("threads_bpm.step", "template_id", string="Etapas")

    # Executions
    execution_ids = fields.One2many("threads_bpm.execution", "template_id", string="Execuções")

    execution_count = fields.Integer(compute="_compute_execution_stats", string="Total de Execuções")
    active_execution_count = fields.Integer(compute="_compute_execution_stats", string="Execuções Ativas")

    @api.depends("execution_ids", "execution_ids.state")
    def _compute_execution_stats(self):
        for rec in self:
            executions = rec.execution_ids
            rec.execution_count = len(executions)
            rec.active_execution_count = len(executions.filtered(lambda e: e.state == 'in_progress'))

    @api.constrains('auto_recreate', 'template_type')
    def _check_auto_recreate(self):
        for rec in self:
            if rec.auto_recreate and rec.template_type != 'process':
                raise ValidationError("Recriação automática só é permitida para Processos.")

    @api.constrains('recreate_interval')
    def _check_recreate_interval(self):
        for rec in self:
            if rec.recreate_interval and rec.recreate_interval < 1:
                raise ValidationError("Intervalo de recriação deve ser maior que 0.")

    def action_create_execution(self):
        """Create a new execution from this template"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Nova Execução',
            'res_model': 'threads_bpm.execution',
            'view_mode': 'form',
            'context': {
                'default_template_id': self.id,
                'default_name': self.name,
                'default_business_unit': self.business_unit,
            },
            'target': 'new',
        }

    def action_view_executions(self):
        """View all executions for this template"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Execuções',
            'res_model': 'threads_bpm.execution',
            'view_mode': 'tree,form',
            'domain': [('template_id', '=', self.id)],
            'context': {'default_template_id': self.id},
        }
