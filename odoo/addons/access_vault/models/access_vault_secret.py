from odoo import api, fields, models
from odoo.exceptions import AccessError, UserError
import logging
import time

_logger = logging.getLogger(__name__)
from odoo.exceptions import AccessError, UserError


class AccessVaultSecret(models.Model):
    _name = "access.vault.secret"
    _description = "Credential Secret"
    _order = "sequence, id"

    credential_id = fields.Many2one("access.vault.credential", required=True, ondelete="cascade")
    sequence = fields.Integer(default=10)

    name = fields.Char(required=True)
    secret_type = fields.Selection(
        [
            ("user_password", "Usuário + Senha"),
            ("api_key", "API Key"),
            ("token", "Token"),
            ("certificate", "Certificado"),
            ("ssh_key", "SSH Key"),
            ("multi", "Multi-acessos"),
        ],
        required=True,
    )

    login_identifier = fields.Char(string="Login / Identificador")
    _secret_encrypted = fields.Text(string="Segredo (criptografado)", readonly=True)
    secret_set = fields.Boolean(compute="_compute_secret_set", store=True)
    last_rotation_at = fields.Datetime(string="Última rotação", readonly=True)

    @api.depends("_secret_encrypted")
    def _compute_secret_set(self):
        for rec in self:
            rec.secret_set = bool(rec._secret_encrypted)

    def _ensure_read_allowed(self):
        # rely on record rules, but keep explicit guard for RPC copy
        self.check_access("read")

        # Additional check: only admins can actually see secret values
        # Others can see the record but not the actual secret content
        credential = self.credential_id
        user = self.env.user

        # Check if user is admin
        is_admin = user.has_group('access_vault.group_access_vault_admin')

        if not is_admin:
            # For non-admins, check if they have read permission on secrets
            can_read_secrets = (
                user.id in credential.allowed_manager_user_ids.ids or
                user.id in credential.owner_ids.ids or
                bool(set(credential.allowed_manager_group_ids.ids) & set(user.all_group_ids.ids))
            )

            if not can_read_secrets:
                raise AccessError("Você não tem permissão para visualizar o conteúdo deste segredo. Apenas gestores e administradores podem ver valores de segredos.")

    def set_secret(self, plaintext):
        self.ensure_one()
        if not plaintext:
            raise UserError("Segredo vazio.")
        # must have management permission to rotate/set
        self.credential_id.check_access("write")
        crypto = self.env["access.vault.crypto"]
        self._secret_encrypted = crypto.encrypt(plaintext)
        self.last_rotation_at = fields.Datetime.now()
        self.credential_id.last_rotation_at = self.last_rotation_at
        self.credential_id._vault_log("rotate", "Segredo rotacionado ({})".format(self.name))

    def action_get_secret_for_copy(self):
        """
        Returns plaintext secret to be copied by the client.
        Must never be rendered in UI; only used for clipboard write.
        Includes rate limiting to prevent abuse.
        """
        self.ensure_one()
        self._ensure_read_allowed()

        if not self._secret_encrypted:
            raise UserError("Nenhum segredo definido para este item.")

        # Rate limiting: max 10 copies per minute per user per credential
        self._check_rate_limit()

        try:
            crypto = self.env["access.vault.crypto"]
            value = crypto.decrypt(self._secret_encrypted)

            # audit
            self.credential_id._vault_log("copy", "Credencial copiada ({})".format(self.name))
            return value

        except Exception as e:
            _logger.error("Erro ao descriptografar segredo %s: %s", self.name, str(e))
            raise UserError("Erro interno ao acessar a credencial. Tente novamente.")

    def _check_rate_limit(self):
        """Simple rate limiting for secret copy operations."""
        cache_key = "access_vault_copy_rate_{}_{}".format(self.env.user.id, self.credential_id.id)
        now = int(time.time())

        # Get or create rate limit data
        rate_data = self.env['ir.config_parameter'].sudo().get_param(cache_key, '{}')
        try:
            rate_info = eval(rate_data) if rate_info else {}
        except:
            rate_info = {}

        # Clean old entries (older than 1 minute)
        current_minute = now // 60
        rate_info = {k: v for k, v in rate_info.items() if k >= current_minute - 1}

        # Check current minute count
        count = rate_info.get(current_minute, 0)
        if count >= 10:  # Max 10 copies per minute
            raise UserError("Limite de cópia excedido. Aguarde um minuto antes de tentar novamente.")

        # Update rate limit
        rate_info[current_minute] = count + 1
        self.env['ir.config_parameter'].sudo().set_param(cache_key, str(rate_info))


