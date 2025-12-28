from odoo import fields, models


class ResUsers(models.Model):
    _inherit = "res.users"

    business_unit = fields.Selection([
        ("platform", "Plataforma"),
        ("b2b", "B2B"),
        ("b2c", "B2C"),
        ("qa_trust", "QA & Trust"),
        ("management", "Gestão"),
        ("board", "Board"),
    ], string="Unidade de Negócio")

    # BPM Statistics
    bpm_execution_count = fields.Integer(
        string="Execuções BPM",
        compute="_compute_bpm_stats",
        help="Número total de execuções BPM que o usuário participa"
    )

    bpm_active_execution_count = fields.Integer(
        string="Execuções Ativas",
        compute="_compute_bpm_stats",
        help="Número de execuções BPM ativas que o usuário participa"
    )

    def _compute_bpm_stats(self):
        for user in self:
            # Count executions where user is creator or participant
            domain = [
                '|',
                ('creator_id', '=', user.id),
                ('participant_ids', 'in', [user.id])
            ]
            user.bpm_execution_count = self.env['threads_bpm.execution'].search_count(domain)

            # Count active executions
            active_domain = domain + [('state', '=', 'in_progress')]
            user.bpm_active_execution_count = self.env['threads_bpm.execution'].search_count(active_domain)
