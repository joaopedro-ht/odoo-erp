import os

from cryptography.fernet import Fernet

from odoo import api, models
from odoo.exceptions import UserError
from odoo.tools import config
import logging
import base64

_logger = logging.getLogger(__name__)


class AccessVaultCrypto(models.AbstractModel):
    _name = "access.vault.crypto"
    _description = "Access Vault - Crypto helpers"

    @api.model
    def _get_master_key(self):
        """
        Returns a Fernet key (bytes). Precedence:
          1) env var ODOO_ACCESS_VAULT_MASTER_KEY
          2) odoo.conf option access_vault_master_key
          3) ir.config_parameter access_vault.master_key (auto-generated if missing)
        """
        key = os.getenv("ODOO_ACCESS_VAULT_MASTER_KEY") or config.get("access_vault_master_key")
        if key:
            return key.encode() if isinstance(key, str) else key

        params = self.env["ir.config_parameter"].sudo()
        key = params.get_param("access_vault.master_key")
        if not key:
            # Bootstrap for dev/testing. For production, prefer env var / odoo.conf.
            _logger.warning("Gerando chave mestre automaticamente. Em produção, configure manualmente via ODOO_ACCESS_VAULT_MASTER_KEY")
            key = Fernet.generate_key().decode()
            params.set_param("access_vault.master_key", key)
        return key.encode()

    @api.model
    def _validate_master_key(self, key):
        """Validate that the key is a proper Fernet key."""
        if not key:
            return False
        try:
            # Fernet keys must be 32 bytes base64 encoded
            decoded = base64.b64decode(key)
            return len(decoded) == 32
        except Exception:
            return False

    @api.model
    def _fernet(self):
        key = self._get_master_key()
        if not self._validate_master_key(key):
            raise UserError(
                "Access Vault: chave mestre inválida. A chave deve ser uma chave Fernet válida "
                "(32 bytes em base64). Defina uma chave válida em ODOO_ACCESS_VAULT_MASTER_KEY "
                "ou no odoo.conf (access_vault_master_key)."
            )
        try:
            return Fernet(key)
        except Exception as e:
            _logger.error("Erro ao inicializar Fernet com chave mestre: %s", str(e))
            raise UserError("Erro interno de criptografia. Contate o administrador.")

    @api.model
    def encrypt(self, plaintext):
        if not plaintext:
            return ""
        token = self._fernet().encrypt(plaintext.encode("utf-8"))
        return token.decode("utf-8")

    @api.model
    def decrypt(self, token):
        if not token:
            return ""
        plaintext = self._fernet().decrypt(token.encode("utf-8"))
        return plaintext.decode("utf-8")


