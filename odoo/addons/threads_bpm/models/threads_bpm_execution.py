from datetime import timedelta
from odoo import api, fields, models
from odoo.exceptions import ValidationError
import logging

_logger = logging.getLogger(__name__)


class ThreadsBPMExecution(models.Model):
    _name = "threads_bpm.execution"
    _description = "Threads BPM Execution"
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = "create_date desc"

    name = fields.Char(required=True, string="Nome da Execução")
    description = fields.Text(string="Descrição")

    template_id = fields.Many2one("threads_bpm.template", string="Modelo", required=True, ondelete="restrict")

    # Inherited from template
    template_type = fields.Selection(related="template_id.template_type", store=True)
    business_unit = fields.Selection(related="template_id.business_unit", store=True)

    # Status and progress
    state = fields.Selection([
        ("draft", "Rascunho"),
        ("in_progress", "Em Andamento"),
        ("completed", "Concluída"),
        ("cancelled", "Cancelada")
    ], default="draft", string="Status")

    # Current step
    current_step_id = fields.Many2one("threads_bpm.step", compute="_compute_current_step", string="Etapa Atual")

    # Dates
    started_at = fields.Datetime(string="Iniciada em", readonly=True)
    completed_at = fields.Datetime(string="Concluída em", readonly=True)

    # Steps
    step_ids = fields.One2many("threads_bpm.step", "execution_id", string="Etapas")

    # SLA and risk tracking
    has_overdue_steps = fields.Boolean(compute="_compute_risk_status", string="Tem Etapas Atrasadas")
    has_at_risk_steps = fields.Boolean(compute="_compute_risk_status", string="Tem Etapas em Risco")

    # Progress
    progress_percentage = fields.Float(compute="_compute_progress", string="Progresso (%)")

    # Participants (all users involved)
    participant_ids = fields.Many2many("res.users", compute="_compute_participants", string="Participantes")

    # Creator
    creator_id = fields.Many2one("res.users", string="Criador", default=lambda self: self.env.user, readonly=True)

    # Logs
    log_ids = fields.One2many("threads_bpm.log", "execution_id", string="Histórico")

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for rec in records:
            rec._initialize_steps()
            rec._log_action("created", "Execução criada")
        return records

    def _initialize_steps(self):
        """Create steps from template"""
        self.ensure_one()
        if not self.template_id:
            return

        # Create steps from template
        for template_step in self.template_id.step_ids:
            step_vals = {
                'execution_id': self.id,
                'name': template_step.name,
                'sequence': template_step.sequence,
                'user_ids': [(6, 0, template_step.user_ids.ids)],
                'sla_enabled': template_step.sla_enabled,
                'sla_hours': template_step.sla_hours,
                'sla_days': template_step.sla_days,
                'is_required': template_step.is_required,
            }
            new_step = self.env['threads_bpm.step'].create(step_vals)

            # Create checklist items
            for checklist_item in template_step.checklist_ids:
                self.env['threads_bpm.checklist'].create({
                    'step_id': new_step.id,
                    'name': checklist_item.name,
                    'sequence': checklist_item.sequence,
                    'is_required': checklist_item.is_required,
                })

    @api.depends("step_ids", "step_ids.state")
    def _compute_current_step(self):
        for rec in self:
            pending_steps = rec.step_ids.filtered(lambda s: s.state in ['pending', 'in_progress'])
            rec.current_step_id = pending_steps.sorted('sequence')[:1] if pending_steps else False

    @api.depends("step_ids", "step_ids.is_overdue", "step_ids.is_at_risk")
    def _compute_risk_status(self):
        for rec in self:
            rec.has_overdue_steps = any(rec.step_ids.mapped('is_overdue'))
            rec.has_at_risk_steps = any(rec.step_ids.mapped('is_at_risk'))

    @api.depends("step_ids", "step_ids.state")
    def _compute_progress(self):
        for rec in self:
            if not rec.step_ids:
                rec.progress_percentage = 0.0
                continue

            total_steps = len(rec.step_ids)
            completed_steps = len(rec.step_ids.filtered(lambda s: s.state in ['completed', 'skipped']))
            rec.progress_percentage = (completed_steps / total_steps) * 100

    @api.depends("step_ids", "step_ids.user_ids", "creator_id")
    def _compute_participants(self):
        for rec in self:
            participants = rec.creator_id
            for step in rec.step_ids:
                participants |= step.user_ids
            rec.participant_ids = participants

    def action_start_execution(self):
        """Start the execution"""
        self.ensure_one()
        if self.state == 'draft':
            self.write({
                'state': 'in_progress',
                'started_at': fields.Datetime.now()
            })
            self._log_action("started", "Execução iniciada")

            # Start first step if exists
            first_step = self.step_ids.sorted('sequence')[:1]
            if first_step:
                first_step.action_start_step()

            # Notify participants
            self._notify_participants("execution_started")

    def action_complete_execution(self):
        """Complete the execution"""
        self.ensure_one()
        if self.state == 'in_progress':
            # Check if all required steps are completed
            required_steps = self.step_ids.filtered(lambda s: s.is_required)
            incomplete_required = required_steps.filtered(lambda s: s.state not in ['completed', 'skipped'])

            if incomplete_required:
                raise ValidationError("Todas as etapas obrigatórias devem ser concluídas antes de finalizar a execução.")

            self.write({
                'state': 'completed',
                'completed_at': fields.Datetime.now()
            })
            self._log_action("completed", "Execução concluída")

    def action_cancel_execution(self):
        """Cancel the execution"""
        self.ensure_one()
        self.write({'state': 'cancelled'})
        self._log_action("cancelled", "Execução cancelada")

    def _check_completion(self):
        """Check if execution is complete and auto-complete if needed"""
        self.ensure_one()
        if self.state != 'in_progress':
            return

        # Check if all steps are completed or skipped
        incomplete_steps = self.step_ids.filtered(lambda s: s.state not in ['completed', 'skipped'])
        if not incomplete_steps:
            self.action_complete_execution()

    def _log_action(self, action, detail=""):
        """Log an action"""
        self.ensure_one()
        self.env['threads_bpm.log'].sudo().create({
            'execution_id': self.id,
            'user_id': self.env.user.id,
            'action': action,
            'detail': detail,
        })

    def _notify_participants(self, notification_type):
        """Send notifications to all participants"""
        self.ensure_one()

        messages = {
            "execution_started": {
                "title": "Threads BPM - Execução Iniciada",
                "body": "Você foi incluído na execução '%s'" % self.name
            },
            "step_assigned": {
                "title": "Threads BPM - Etapa Atribuída",
                "body": "Uma nova etapa foi atribuída a você na execução '%s'" % self.name
            }
        }

        if notification_type not in messages:
            return

        msg = messages[notification_type]

        # Send to all participants
        for user in self.participant_ids:
            if user == self.env.user:  # Don't notify the current user
                continue

            partner = user.partner_id

            # Toast notification
            self.env["bus.bus"]._sendone(
                partner,
                "simple_notification",
                {
                    "type": "info",
                    "title": msg["title"],
                    "message": msg["body"],
                    "sticky": True
                },
            )

            # Discuss chat message
            try:
                channel = self.env["discuss.channel"].with_user(self.env.ref("base.user_admin"))._get_or_create_chat(
                    partners_to=[partner.id],
                    pin=True,
                )
                channel.message_post(
                    body="%s\n\n<a href=\"/web#id=%s&model=threads_bpm.execution&view_type=form\" target=\"_blank\">Abrir Execução</a>" % (msg["body"], self.id),
                    message_type="comment",
                    subtype_xmlid="mail.mt_comment",
                    partner_ids=[partner.id],
                )
            except Exception as e:
                _logger.warning("Failed to send chat notification to user %s: %s", user.name, str(e))

    @api.model
    def get_user_executions(self, user_id=None):
        """Get executions for a specific user (dashboard data)"""
        if user_id is None:
            user_id = self.env.user.id

        domain = [
            '|', '|',
            ('creator_id', '=', user_id),  # Created by user
            ('step_ids.user_ids', 'in', [user_id]),  # Assigned to user
            ('participant_ids', 'in', [user_id])  # Involved in execution
        ]

        executions = self.search_read(domain, [
            'id', 'name', 'state', 'template_type', 'business_unit',
            'started_at', 'completed_at', 'has_overdue_steps', 'has_at_risk_steps',
            'progress_percentage', 'current_step_id'
        ], limit=50)

        # Categorize by status
        result = {
            'on_track': [],
            'at_risk': [],
            'overdue': [],
            'completed': []
        }

        for exec_data in executions:
            if exec_data['state'] == 'completed':
                result['completed'].append(exec_data)
            elif exec_data['has_overdue_steps']:
                result['overdue'].append(exec_data)
            elif exec_data['has_at_risk_steps']:
                result['at_risk'].append(exec_data)
            else:
                result['on_track'].append(exec_data)

        return result

    @api.model
    def _cron_auto_recreate_processes(self):
        """Auto-recreate recurring processes"""
        now = fields.Datetime.now()

        # Find active process templates with auto-recreate enabled
        templates = self.env['threads_bpm.template'].search([
            ('template_type', '=', 'process'),
            ('active', '=', True),
            ('auto_recreate', '=', True)
        ])

        for template in templates:
            # Check if we need to create a new execution
            last_execution = self.search([
                ('template_id', '=', template.id)
            ], order='create_date desc', limit=1)

            if not last_execution:
                # No executions yet, create first one
                self._create_auto_execution(template)
                continue

            # Calculate next execution date
            interval_delta = self._get_interval_delta(template)
            next_execution_date = last_execution.create_date + interval_delta

            if now >= next_execution_date:
                self._create_auto_execution(template)

    def _get_interval_delta(self, template):
        """Get timedelta for auto-recreation interval"""
        amount = template.recreate_interval or 1
        unit = template.recreate_unit or 'days'

        if unit == 'days':
            return timedelta(days=amount)
        elif unit == 'weeks':
            return timedelta(weeks=amount)
        elif unit == 'months':
            return timedelta(days=amount * 30)  # Approximation
        else:
            return timedelta(days=amount)

    def _create_auto_execution(self, template):
        """Create an automatic execution for a recurring process"""
        execution = self.create({
            'name': '%s - %s' % (template.name, fields.Date.today().strftime('%Y-%m-%d')),
            'template_id': template.id,
            'state': 'in_progress',
            'started_at': fields.Datetime.now(),
        })

        # Auto-start the execution
        execution.action_start_execution()

        _logger.info("Auto-created execution %s for template %s", execution.name, template.name)

    @api.model
    def _cron_sla_reminders(self):
        """Send SLA reminders for overdue and at-risk steps"""
        now = fields.Datetime.now()

        # Find executions with overdue or at-risk steps
        executions = self.search([
            ('state', '=', 'in_progress'),
            '|', ('has_overdue_steps', '=', True), ('has_at_risk_steps', '=', True)
        ])

        for execution in executions:
            overdue_steps = execution.step_ids.filtered(lambda s: s.is_overdue and not s.completed_at)
            at_risk_steps = execution.step_ids.filtered(lambda s: s.is_at_risk and not s.completed_at)

            # Notify assignees of overdue steps
            for step in overdue_steps:
                for user in step.user_ids:
                    if user != self.env.user:  # Don't notify current user
                        self._notify_step_sla(user, step, "overdue")

            # Notify assignees of at-risk steps
            for step in at_risk_steps:
                for user in step.user_ids:
                    if user != self.env.user:  # Don't notify current user
                        self._notify_step_sla(user, step, "at_risk")

    def _notify_step_sla(self, user, step, sla_type):
        """Send SLA notification for a specific step"""
        messages = {
            "overdue": {
                "title": "Threads BPM - SLA Atrasado",
                "body": "A etapa '%s' da execução '%s' está atrasada!" % (step.name, step.execution_id.name),
                "type": "danger"
            },
            "at_risk": {
                "title": "Threads BPM - SLA em Risco",
                "body": "A etapa '%s' da execução '%s' vence em menos de 24 horas!" % (step.name, step.execution_id.name),
                "type": "warning"
            }
        }

        msg = messages.get(sla_type)
        if not msg:
            return

        partner = user.partner_id

        # Toast notification
        self.env["bus.bus"]._sendone(
            partner,
            "simple_notification",
            {
                "type": msg["type"],
                "title": msg["title"],
                "message": msg["body"],
                "sticky": True
            },
        )

        # Discuss chat message
        try:
            channel = self.env["discuss.channel"].with_user(self.env.ref("base.user_admin"))._get_or_create_chat(
                partners_to=[partner.id],
                pin=True,
            )
            channel.message_post(
                body="%s\n\n<a href=\"/web#id=%s&model=threads_bpm.execution&view_type=form\" target=\"_blank\">Abrir Execução</a>" % (msg["body"], step.execution_id.id),
                message_type="comment",
                subtype_xmlid="mail.mt_comment",
                partner_ids=[partner.id],
            )
        except Exception as e:
            _logger.warning("Failed to send SLA chat notification to user %s: %s", user.name, str(e))
