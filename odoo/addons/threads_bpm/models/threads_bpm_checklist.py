from odoo import fields, models


class ThreadsBPMChecklist(models.Model):
    _name = "threads_bpm.checklist"
    _description = "Threads BPM Checklist Item"
    _order = "sequence"

    step_id = fields.Many2one("threads_bpm.step", string="Etapa", required=True, ondelete="cascade")

    name = fields.Char(required=True, string="Item do Checklist")
    sequence = fields.Integer(default=10, string="Ordem")

    is_required = fields.Boolean(default=True, string="Obrigatório")
    is_completed = fields.Boolean(default=False, string="Concluído")

    completed_at = fields.Datetime(string="Concluído em", readonly=True)
    completed_by = fields.Many2one("res.users", string="Concluído por", readonly=True)

    def action_toggle_completed(self):
        """Toggle the completion status of this checklist item"""
        self.ensure_one()

        if self.is_completed:
            # Mark as not completed
            self.write({
                'is_completed': False,
                'completed_at': False,
                'completed_by': False
            })
        else:
            # Mark as completed
            self.write({
                'is_completed': True,
                'completed_at': fields.Datetime.now(),
                'completed_by': self.env.user.id
            })

        # Log the action
        action = "checklist_completed" if self.is_completed else "checklist_uncompleted"
        detail = "Item '%s' marcado como %s" % (self.name, "concluído" if self.is_completed else "pendente")
        self.step_id.execution_id._log_action(action, detail)

        # Check if step can be auto-completed
        if self.is_completed and self.step_id.checklist_progress >= 100:
            # All checklist items completed, check if we can complete the step
            pass  # The step completion is handled by the step logic
