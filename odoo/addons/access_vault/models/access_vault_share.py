from odoo import api, fields, models
from odoo.exceptions import ValidationError, UserError
import logging

_logger = logging.getLogger(__name__)


class AccessVaultShare(models.Model):
    _name = "access.vault.share"
    _description = "Temporary Access Share"
    _order = "expires_at desc, id desc"

    credential_id = fields.Many2one("access.vault.credential", required=True, ondelete="cascade")
    user_id = fields.Many2one("res.users", required=True, ondelete="cascade")
    expires_at = fields.Datetime(required=True)
    active = fields.Boolean(default=True, index=True)

    created_by = fields.Many2one("res.users", default=lambda self: self.env.user, readonly=True)

    @api.constrains('expires_at')
    def _check_expires_at(self):
        """Ensure expiration date is in the future."""
        now = fields.Datetime.now()
        for record in self:
            if record.expires_at <= now:
                raise ValidationError("A data de expiração deve ser no futuro.")

    @api.constrains('user_id')
    def _check_user_not_self(self):
        """Ensure user cannot share with themselves."""
        for record in self:
            if record.user_id.id == self.env.user.id:
                raise ValidationError("Você não pode compartilhar uma credencial consigo mesmo.")

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for rec in records:
            rec.credential_id._vault_log(
                "share_grant",
                "Acesso temporário concedido para {} até {}".format(rec.user_id.name, rec.expires_at),
            )
            # Enviar notificação para o usuário que recebeu o compartilhamento
            rec._send_share_notification()
        return records

    def _send_share_notification(self):
        """Send notification to user when access is shared with them."""
        self.ensure_one()
        partner = self.user_id.partner_id
        credential = self.credential_id

        title = "Access Vault - Compartilhamento de Acesso"
        message = "Você recebeu acesso temporário à credencial '{}' até {}.".format(credential.name, self.expires_at.strftime('%d/%m/%Y %H:%M'))

        # Toast notification
        self.env["bus.bus"]._sendone(
            partner,
            "simple_notification",
            {
                "type": "success",
                "title": title,
                "message": message,
                "sticky": True
            },
        )

        # Discuss chat message (DM)
        try:
            channel = self.env["discuss.channel"].with_user(self.env.ref("base.user_admin"))._get_or_create_chat(
                partners_to=[partner.id],
                pin=True,
            )
            channel.message_post(
                body="{}\n\nConcedido por: {}".format(message, self.created_by.name),
                message_type="comment",
                subtype_xmlid="mail.mt_comment",
                partner_ids=[partner.id],
            )
        except Exception as e:
            # Log error but don't fail the operation
            _logger.warning("Falha ao enviar notificação de chat para usuário %s: %s", self.user_id.name, str(e))

    def action_revoke(self):
        for rec in self:
            rec.active = False
            rec.credential_id._vault_log("share_revoke", "Acesso temporário revogado para {}".format(rec.user_id.name))

    @api.model
    def _cron_expire_shares(self):
        now = fields.Datetime.now()
        shares = self.search([("active", "=", True), ("expires_at", "<=", now)])
        for share in shares:
            share.active = False
            share.credential_id._vault_log("share_expire", "Acesso temporário expirou para {}".format(share.user_id.name))


