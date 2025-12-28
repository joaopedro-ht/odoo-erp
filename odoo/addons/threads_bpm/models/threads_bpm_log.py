from odoo import fields, models


class ThreadsBPMLog(models.Model):
    _name = "threads_bpm.log"
    _description = "Threads BPM Audit Log"
    _order = "timestamp desc, id desc"

    execution_id = fields.Many2one("threads_bpm.execution", string="Execução", required=True, ondelete="cascade")
    user_id = fields.Many2one("res.users", string="Usuário", required=True, readonly=True)
    timestamp = fields.Datetime(default=fields.Datetime.now, required=True, readonly=True)

    action = fields.Selection([
        ("created", "Criação"),
        ("started", "Iniciada"),
        ("completed", "Concluída"),
        ("cancelled", "Cancelada"),
        ("step_started", "Etapa Iniciada"),
        ("step_completed", "Etapa Concluída"),
        ("step_skipped", "Etapa Pulada"),
        ("checklist_completed", "Checklist Item Concluído"),
        ("checklist_uncompleted", "Checklist Item Desmarcado"),
    ], required=True, string="Ação")

    detail = fields.Text(string="Detalhes")

    # Related fields for easier filtering
    template_id = fields.Many2one(related="execution_id.template_id", store=True, string="Modelo")
    template_type = fields.Selection(related="execution_id.template_type", store=True)
    business_unit = fields.Selection(related="execution_id.business_unit", store=True)
