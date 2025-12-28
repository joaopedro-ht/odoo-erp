from odoo import fields, models


class AccessVaultLog(models.Model):
    _name = "access.vault.log"
    _description = "Access Vault Audit Log"
    _order = "timestamp desc, id desc"

    credential_id = fields.Many2one("access.vault.credential", required=True, ondelete="cascade")
    user_id = fields.Many2one("res.users", required=True, ondelete="cascade", default=lambda self: self.env.user)
    action = fields.Selection(
        [
            ("create", "Criação"),
            ("update", "Alteração"),
            ("rotate", "Rotação de segredo"),
            ("copy", "Cópia de credencial"),
            ("share_grant", "Compartilhamento temporário concedido"),
            ("share_revoke", "Compartilhamento temporário revogado"),
            ("share_expire", "Compartilhamento temporário expirou"),
        ],
        required=True,
    )
    timestamp = fields.Datetime(default=fields.Datetime.now, required=True, readonly=True)
    detail = fields.Char()


