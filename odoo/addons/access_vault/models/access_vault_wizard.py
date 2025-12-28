from odoo import fields, models
from odoo.exceptions import UserError


class AccessVaultSetSecretWizard(models.TransientModel):
    _name = "access.vault.set_secret.wizard"
    _description = "Set / Rotate Secret"

    secret_id = fields.Many2one("access.vault.secret", required=True, ondelete="cascade")
    secret_value = fields.Char(string="Senha / Segredo", required=True)

    def action_confirm(self):
        self.ensure_one()
        if not self.secret_value:
            raise UserError("Informe um segredo.")
        self.secret_id.set_secret(self.secret_value)
        return {"type": "ir.actions.act_window_close"}


