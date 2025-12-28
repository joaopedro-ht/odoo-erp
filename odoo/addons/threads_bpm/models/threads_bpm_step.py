from datetime import timedelta
from odoo import api, fields, models
from odoo.exceptions import ValidationError


class ThreadsBPStep(models.Model):
    _name = "threads_bpm.step"
    _description = "Threads BPM Step"
    _order = "sequence"

    template_id = fields.Many2one("threads_bpm.template", string="Modelo", required=True, ondelete="cascade")
    execution_id = fields.Many2one("threads_bpm.execution", string="Execução", ondelete="cascade")

    name = fields.Char(required=True, string="Nome da Etapa")
    sequence = fields.Integer(default=10, string="Ordem")

    # Responsible users
    user_ids = fields.Many2many("res.users", string="Responsáveis",
                               relation="threads_bpm_step_user_rel",
                               column1="step_id", column2="user_id")

    # SLA Configuration
    sla_enabled = fields.Boolean(string="SLA Habilitado", default=False)
    sla_hours = fields.Integer(string="SLA (Horas)")
    sla_days = fields.Integer(string="SLA (Dias)")

    # Checklist
    checklist_ids = fields.One2many("threads_bpm.checklist", "step_id", string="Checklist")

    # Execution fields
    state = fields.Selection([
        ("pending", "Pendente"),
        ("in_progress", "Em Andamento"),
        ("completed", "Concluída"),
        ("skipped", "Pulada")
    ], default="pending", string="Status")

    is_required = fields.Boolean(default=True, string="Obrigatória")

    # Dates
    started_at = fields.Datetime(string="Iniciada em")
    completed_at = fields.Datetime(string="Concluída em")

    # SLA tracking
    sla_deadline = fields.Datetime(string="Prazo SLA", compute="_compute_sla_deadline")
    is_overdue = fields.Boolean(string="Em Atraso", compute="_compute_sla_status")
    is_at_risk = fields.Boolean(string="Em Risco", compute="_compute_sla_status")

    # Task integration
    task_id = fields.Many2one("project.task", string="Tarefa Vinculada")

    checklist_progress = fields.Float(compute="_compute_checklist_progress", string="Progresso Checklist (%)")

    @api.depends("checklist_ids", "checklist_ids.is_completed")
    def _compute_checklist_progress(self):
        for rec in self:
            if not rec.checklist_ids:
                rec.checklist_progress = 100.0 if rec.state == 'completed' else 0.0
            else:
                completed = len(rec.checklist_ids.filtered(lambda c: c.is_completed))
                total = len(rec.checklist_ids)
                rec.checklist_progress = (completed / total) * 100 if total > 0 else 0.0

    @api.depends("execution_id.started_at", "sla_enabled", "sla_hours", "sla_days")
    def _compute_sla_deadline(self):
        for rec in self:
            if not rec.execution_id or not rec.execution_id.started_at or not rec.sla_enabled:
                rec.sla_deadline = False
                continue

            start_date = rec.execution_id.started_at
            sla_delta = timedelta()

            if rec.sla_days:
                sla_delta += timedelta(days=rec.sla_days)
            if rec.sla_hours:
                sla_delta += timedelta(hours=rec.sla_hours)

            rec.sla_deadline = start_date + sla_delta

    @api.depends("sla_deadline", "completed_at")
    def _compute_sla_status(self):
        now = fields.Datetime.now()
        for rec in self:
            if not rec.sla_deadline:
                rec.is_overdue = False
                rec.is_at_risk = False
                continue

            if rec.completed_at:
                # Already completed
                rec.is_overdue = rec.completed_at > rec.sla_deadline
                rec.is_at_risk = False
            else:
                # Still in progress
                rec.is_overdue = now > rec.sla_deadline
                # At risk if within 24 hours of deadline
                rec.is_at_risk = not rec.is_overdue and (rec.sla_deadline - now).total_seconds() < 86400

    @api.constrains('sla_hours', 'sla_days')
    def _check_sla_values(self):
        for rec in self:
            if rec.sla_enabled and not (rec.sla_hours or rec.sla_days):
                raise ValidationError("SLA deve ter pelo menos horas ou dias configurados.")

    def action_start_step(self):
        """Start this step"""
        self.ensure_one()
        if self.state == 'pending':
            self.write({
                'state': 'in_progress',
                'started_at': fields.Datetime.now()
            })
            self._create_task_if_needed()
            self.execution_id._log_action("step_started", "Etapa '%s' iniciada" % self.name)

    def action_complete_step(self):
        """Complete this step"""
        self.ensure_one()
        if self.state == 'in_progress':
            # Check if checklist is complete for required steps
            if self.is_required and self.checklist_ids and self.checklist_progress < 100:
                raise ValidationError("Todos os itens do checklist devem ser concluídos antes de finalizar a etapa.")

            self.write({
                'state': 'completed',
                'completed_at': fields.Datetime.now()
            })

            # Close related task
            if self.task_id:
                self.task_id.write({'stage_id': self.task_id.project_id.type_ids.filtered(lambda t: t.is_closed)[:1].id})

            self.execution_id._log_action("step_completed", "Etapa '%s' concluída" % self.name)

            # Check if execution is complete
            self.execution_id._check_completion()

    def action_skip_step(self):
        """Skip this step (only for optional steps)"""
        self.ensure_one()
        if not self.is_required:
            self.write({'state': 'skipped'})
            self.execution_id._log_action("step_skipped", "Etapa '%s' pulada" % self.name)
        else:
            raise ValidationError("Etapas obrigatórias não podem ser puladas.")

    def _create_task_if_needed(self):
        """Create a project task for this step if it has assignees"""
        self.ensure_one()
        if not self.user_ids or self.task_id:
            return

        # Find or create a project for BPM tasks
        project = self.env['project.project'].search([('name', '=', 'BPM Tasks')], limit=1)
        if not project:
            project = self.env['project.project'].create({
                'name': 'BPM Tasks',
                'use_tasks': True,
                'type': 'task',
            })

        # Calculate deadline
        deadline = self.sla_deadline if self.sla_enabled and self.sla_deadline else False

        task = self.env['project.task'].create({
            'name': '%s - %s' % (self.execution_id.name, self.name),
            'project_id': project.id,
            'user_ids': [(6, 0, self.user_ids.ids)],
            'date_deadline': deadline,
            'description': """
            <p><strong>Thread BPM:</strong> %s</p>
            <p><strong>Etapa:</strong> %s</p>
            <p><strong>Prazo:</strong> %s</p>
            <p><a href="/web#id=%s&model=threads_bpm.execution&view_type=form" target="_blank">Abrir Thread</a></p>
            """ % (self.execution_id.name, self.name, deadline or 'N/A', self.execution_id.id)
        })

        self.task_id = task
