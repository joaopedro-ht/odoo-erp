from datetime import timedelta

from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError
import logging

_logger = logging.getLogger(__name__)


class AccessVaultCredential(models.Model):
    _name = "access.vault.credential"
    _description = "Access / Credential"
    _order = "criticality desc, name, id"

    name = fields.Char(required=True)

    access_type = fields.Selection(
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

    criticality = fields.Selection(
        [("low", "Baixa"), ("medium", "Média"), ("high", "Alta"), ("critical", "Crítica")],
        required=True,
    )

    business_unit = fields.Selection(
        [
            ("platform", "Plataforma"),
            ("b2b", "B2B"),
            ("b2c", "B2C"),
            ("qa_trust", "QA & Trust"),
            ("management", "Gestão"),
            ("board", "Board"),
        ],
        required=True,
    )

    environment = fields.Selection(
        [("production", "Produção"), ("staging", "Staging"), ("development", "Desenvolvimento")],
        required=True,
    )

    rotation_days = fields.Selection(
        [("7", "7d"), ("15", "15d"), ("30", "30d"), ("60", "60d"), ("90", "90d"), ("180", "180d")],
        string="Rotatividade de senha",
    )

    @api.constrains('rotation_days')
    def _check_rotation_days(self):
        """Ensure rotation days are reasonable."""
        for record in self:
            if record.rotation_days:
                days = int(record.rotation_days)
                if days < 1 or days > 365:
                    raise ValidationError("Os dias de rotação devem estar entre 1 e 365.")

    @api.constrains('name')
    def _check_name_unique_per_env(self):
        """Ensure credential names are unique per environment."""
        for record in self:
            if record.name:
                existing = self.search([
                    ('name', '=', record.name),
                    ('environment', '=', record.environment),
                    ('id', '!=', record.id)
                ])
                if existing:
                    raise ValidationError("Já existe uma credencial com este nome neste ambiente.")

    @api.constrains('owner_ids')
    def _check_at_least_one_owner(self):
        """Ensure at least one owner is assigned."""
        for record in self:
            if not record.owner_ids:
                raise ValidationError("Pelo menos um proprietário deve ser definido para a credencial.")

    owner_ids = fields.Many2many(
        "res.users",
        "access_vault_credential_owner_rel",
        "credential_id",
        "user_id",
        string="Dono(s)",
        required=True,
    )

    allowed_user_ids = fields.Many2many(
        "res.users",
        "access_vault_credential_user_rel",
        "credential_id",
        "user_id",
        string="Usuários (leitura)",
    )
    allowed_group_ids = fields.Many2many(
        "res.groups",
        "access_vault_credential_group_rel",
        "credential_id",
        "group_id",
        string="Grupos (leitura / RBAC)",
    )

    allowed_manager_user_ids = fields.Many2many(
        "res.users",
        "access_vault_credential_manager_user_rel",
        "credential_id",
        "user_id",
        string="Usuários (gerenciamento)",
        help="Pode editar/excluir/rotacionar/gerenciar compartilhamentos.",
    )
    allowed_manager_group_ids = fields.Many2many(
        "res.groups",
        "access_vault_credential_manager_group_rel",
        "credential_id",
        "group_id",
        string="Grupos (gerenciamento / RBAC)",
        help="Pode editar/excluir/rotacionar/gerenciar compartilhamentos.",
    )

    privacy = fields.Selection([("public", "Público"), ("private", "Privado")], required=True)

    # Computed fields for permissions
    can_manage = fields.Boolean(
        string="Pode gerenciar",
        compute="_compute_permissions",
        help="Usuário tem permissão para editar/gerenciar esta credencial"
    )
    can_read_secrets = fields.Boolean(
        string="Pode ver segredos",
        compute="_compute_permissions",
        help="Usuário tem permissão para ver os segredos desta credencial"
    )

    last_rotation_at = fields.Datetime(string="Última rotação")

    next_rotation_at = fields.Datetime(string="Próxima rotação", compute="_compute_rotation_status")
    rotation_due = fields.Boolean(
        string="Precisa rotacionar",
        compute="_compute_rotation_status",
        search="_search_rotation_due",
    )
    days_to_rotation = fields.Integer(
        string="Dias para rotacionar",
        compute="_compute_rotation_status",
        search="_search_days_to_rotation",
        help="Negativo = já passou do prazo.",
    )

    state = fields.Selection(
        [("active", "Ativo"), ("expired", "Expirado"), ("revoked", "Revogado")],
        default="active",
        required=True,
    )

    rotation_reminder_day1_at = fields.Datetime(string="Lembrete (D-1)", readonly=True)
    rotation_reminder_due_at = fields.Datetime(string="Lembrete (D0)", readonly=True)

    secret_ids = fields.One2many("access.vault.secret", "credential_id", string="Segredos")
    share_ids = fields.One2many("access.vault.share", "credential_id", string="Compartilhamentos temporários")
    log_ids = fields.One2many("access.vault.log", "credential_id", string="Logs")

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for rec in records:
            rec._vault_log("create", "Credencial criada")
        return records

    def write(self, vals):
        res = super().write(vals)
        for rec in self:
            rec._vault_log("update", "Credencial alterada")
        return res

    def _vault_log(self, action, detail=""):
        self.env["access.vault.log"].sudo().create(
            {
                "credential_id": self.id,
                "user_id": self.env.user.id,
                "action": action,
                "detail": detail,
            }
        )

    # ------------------------------------------------------------
    # Rotation status (does NOT auto-expire; only indicates "needs rotation")
    # ------------------------------------------------------------

    def _get_rotation_info(self, now=None):
        """Return (next_rotation_at, days_to_rotation, rotation_due) for self (single record)."""
        self.ensure_one()
        now = now or fields.Datetime.now()

        if self.state != "active" or not self.rotation_days:
            return (False, 0, False)

        days = int(self.rotation_days)
        if not self.last_rotation_at:
            # never rotated -> due
            return (False, -days, True)

        next_rotation_at = self.last_rotation_at + timedelta(days=days)
        delta = next_rotation_at - now
        days_to_rotation = int(delta.total_seconds() // 86400)
        rotation_due = next_rotation_at <= now
        return (next_rotation_at, days_to_rotation, rotation_due)

    @api.depends("owner_ids", "allowed_user_ids", "allowed_manager_user_ids", "allowed_group_ids", "allowed_manager_group_ids")
    def _compute_permissions(self):
        """Compute user permissions for current record based on ownership and access rules."""
        for rec in self:
            user = self.env.user
            rec.can_manage = (
                user.id in rec.owner_ids.ids or
                user.id in rec.allowed_manager_user_ids.ids or
                bool(set(rec.allowed_manager_group_ids.ids) & set(user.all_group_ids.ids))
            )
            rec.can_read_secrets = rec.can_manage or (
                user.id in rec.allowed_user_ids.ids or
                bool(set(rec.allowed_group_ids.ids) & set(user.all_group_ids.ids))
            )

    @api.depends("rotation_days", "last_rotation_at", "state")
    def _compute_rotation_status(self):
        now = fields.Datetime.now()
        for rec in self:
            rec.next_rotation_at = False
            rec.rotation_due = False
            rec.days_to_rotation = 0

            # Only track rotation needs for active credentials with a policy
            next_rotation_at, days_to_rotation, rotation_due = rec._get_rotation_info(now=now)
            rec.next_rotation_at = next_rotation_at
            rec.days_to_rotation = days_to_rotation
            rec.rotation_due = rotation_due

    def _rotation_due_domain(self, now=None):
        """
        Build a domain matching credentials that need rotation.
        - active only
        - rotation_days set
        - last_rotation_at missing OR too old for the policy
        """
        now = now or fields.Datetime.now()
        # If never rotated -> due (for any policy)
        base = ["&", ("state", "=", "active"), ("rotation_days", "!=", False)]
        never_rotated = ("last_rotation_at", "=", False)

        # (rotation_days = X) AND (last_rotation_at <= now - X days)
        parts = []
        for d in (7, 15, 30, 60, 90, 180):
            cutoff = now - timedelta(days=d)
            parts.append(["&", ("rotation_days", "=", str(d)), ("last_rotation_at", "<=", cutoff)])

        # OR-chain: never_rotated OR any cutoff match
        domain = ["|", never_rotated, parts[0]]
        for p in parts[1:]:
            domain = ["|", domain, p]

        return ["&"] + base + [domain]

    @api.model
    def _search_rotation_due(self, operator, value):
        # supported: = True/False, != True/False
        if operator not in ("=", "!="):
            return []
        want_due = bool(value)
        if operator == "!=":
            want_due = not want_due

        due_domain = self._rotation_due_domain()
        return due_domain if want_due else ["!"] + due_domain

    @api.model
    def _search_days_to_rotation(self, operator, value):
        # Minimal support: allow filtering overdue (days_to_rotation < 0) via rotation_due
        if operator in ("<", "<=") and (value == 0 or value is False):
            return self._rotation_due_domain()
        if operator in (">", ">=") and value == 0:
            return ["!"] + self._rotation_due_domain()
        return []

    # ------------------------------------------------------------
    # Dashboard + reminders
    # ------------------------------------------------------------

    @api.model
    def get_dashboard_stats(self):
        """Optimized dashboard stats with credentials list."""
        self.check_access("read")
        now = fields.Datetime.now()
        today = fields.Date.today()

        # Get basic counts using SQL for better performance
        self.env.cr.execute("""
            SELECT
                COUNT(*) as total,
                COUNT(CASE WHEN state = 'active' THEN 1 END) as total_active,
                COUNT(CASE WHEN state = 'active' AND rotation_days IS NOT NULL THEN 1 END) as rotation_enabled
            FROM access_vault_credential
        """)
        result = self.env.cr.fetchone()
        total, total_active, rotation_enabled = result

        # Get rotation stats using optimized query
        due_today = 0
        due_tomorrow = 0
        due_ids = []

        if rotation_enabled > 0:
            # Use SQL to find credentials needing rotation
            self.env.cr.execute("""
                SELECT c.id, c.name, c.environment, c.business_unit, c.criticality,
                       c.last_rotation_at, c.rotation_days,
                       ARRAY_AGG(u.name) as owner_names
                FROM access_vault_credential c
                LEFT JOIN access_vault_credential_owner_rel cor ON c.id = cor.credential_id
                LEFT JOIN res_users u ON cor.user_id = u.id
                WHERE c.state = 'active' AND c.rotation_days IS NOT NULL
                GROUP BY c.id, c.name, c.environment, c.business_unit, c.criticality,
                         c.last_rotation_at, c.rotation_days
                ORDER BY c.criticality DESC, c.name
            """)

            creds_data = self.env.cr.fetchall()
            for cred_data in creds_data:
                cred_id, name, environment, business_unit, criticality, last_rotation, rotation_days, owner_names = cred_data

                # Calculate rotation info
                next_rotation_at, days_to_rotation, rotation_due = self._calculate_rotation_info_single(
                    last_rotation, rotation_days, now
                )

                # Check if secret exists
                self.env.cr.execute("""
                    SELECT COUNT(*) FROM access_vault_secret
                    WHERE credential_id = %s AND _secret_encrypted IS NOT NULL
                """, (cred_id,))
                has_secret = self.env.cr.fetchone()[0] > 0

                if not has_secret:
                    continue

                if rotation_due:
                    due_today += 1
                    due_ids.append(cred_id)
                elif days_to_rotation == 1:
                    due_tomorrow += 1

        # Get due list with limit
        due_list = []
        if due_ids:
            due_credentials = self.browse(due_ids[:50])
            due_list = [{
                'id': c.id,
                'name': c.name,
                'environment': c.environment,
                'business_unit': c.business_unit,
                'criticality': c.criticality,
                'owner_ids': [{'id': u.id, 'name': u.name} for u in c.owner_ids],
                'next_rotation_at': c.next_rotation_at,
                'days_to_rotation': c.days_to_rotation,
            } for c in due_credentials]

        # Get credentials by environment (limit to recent ones)
        self.env.cr.execute("""
            SELECT c.id, c.name, c.access_type, c.environment, c.business_unit,
                   c.criticality, c.state, c.privacy, c.rotation_days,
                   c.last_rotation_at, c.next_rotation_at, c.days_to_rotation,
                   c.rotation_due, ARRAY_AGG(u.name) as owner_names
            FROM access_vault_credential c
            LEFT JOIN access_vault_credential_owner_rel cor ON c.id = cor.credential_id
            LEFT JOIN res_users u ON cor.user_id = u.id
            GROUP BY c.id, c.name, c.access_type, c.environment, c.business_unit,
                     c.criticality, c.state, c.privacy, c.rotation_days,
                     c.last_rotation_at, c.next_rotation_at, c.days_to_rotation,
                     c.rotation_due
            ORDER BY c.environment, c.criticality DESC, c.name
            LIMIT 50
        """)

        credentials_by_env = []
        for row in self.env.cr.fetchall():
            (cred_id, name, access_type, environment, business_unit, criticality,
             state, privacy, rotation_days, last_rotation_at, next_rotation_at,
             days_to_rotation, rotation_due, owner_names) = row

            credentials_by_env.append({
                'id': cred_id,
                'name': name,
                'access_type': access_type,
                'environment': environment,
                'business_unit': business_unit,
                'criticality': criticality,
                'state': state,
                'privacy': privacy,
                'rotation_days': rotation_days,
                'last_rotation_at': last_rotation_at,
                'next_rotation_at': next_rotation_at,
                'days_to_rotation': days_to_rotation,
                'rotation_due': rotation_due,
                'owner_names': ', '.join(filter(None, owner_names or [])),
            })

        return {
            "today": str(today),
            "total": total,
            "total_active": total_active,
            "due_today": due_today,
            "due_tomorrow": due_tomorrow,
            "due_list": due_list,
            "credentials_by_env": credentials_by_env,
        }

    @api.model
    def _calculate_rotation_info_single(self, last_rotation_at, rotation_days, now):
        """Calculate rotation info for a single credential (optimized version)."""
        if not rotation_days:
            return (False, 0, False)

        days = int(rotation_days)
        if not last_rotation_at:
            return (False, -days, True)

        next_rotation_at = last_rotation_at + timedelta(days=days)
        delta = next_rotation_at - now
        days_to_rotation = int(delta.total_seconds() // 86400)
        rotation_due = next_rotation_at <= now
        return (next_rotation_at, days_to_rotation, rotation_due)

    @api.model
    def _cron_rotation_reminders(self):
        """Notify owners 1 day before and on due day. No auto-expire. Idempotent per day."""
        now = fields.Datetime.now()
        today = fields.Date.today()
        creds = self.search([("state", "=", "active"), ("rotation_days", "!=", False)])
        for c in creds:
            # only if at least one secret has been set
            if not c.secret_ids.filtered(lambda s: s._secret_encrypted):
                continue

            next_rotation_at, days_to_rotation, rotation_due = c._get_rotation_info(now=now)
            if not next_rotation_at and not rotation_due:
                # never rotated (rotation_due True in that case) OR no policy
                pass

            send_day1 = days_to_rotation == 1
            send_due = rotation_due or days_to_rotation <= 0

            if send_day1 and c.rotation_reminder_day1_at and c.rotation_reminder_day1_at.date() == today:
                send_day1 = False
            if send_due and c.rotation_reminder_due_at and c.rotation_reminder_due_at.date() == today:
                send_due = False

            if not (send_day1 or send_due):
                continue

            title = "Access Vault"
            if send_due:
                msg = "Senha/segredo precisa ser rotacionado HOJE: {}".format(c.name)
                sticky = True
            else:
                msg = "Senha/segredo precisa ser rotacionado AMANHÃ: {}".format(c.name)
                sticky = False

            # Send to each owner
            for user in c.owner_ids:
                partner = user.partner_id
                # Toast notification
                self.env["bus.bus"]._sendone(
                    partner,
                    "simple_notification",
                    {"type": "danger", "title": title, "message": msg, "sticky": sticky},
                )

                # Discuss chat message (DM)
                try:
                    channel = self.env["discuss.channel"].with_user(self.env.ref("base.user_admin"))._get_or_create_chat(
                        partners_to=[partner.id],
                        pin=True,
                    )
                    channel.message_post(
                        body=msg,
                        message_type="comment",
                        subtype_xmlid="mail.mt_comment",
                        partner_ids=[partner.id],
                    )
                except Exception as e:
                    # Log error but keep cron robust
                    _logger.warning("Falha ao enviar notificação de rotação para usuário %s: %s", user.name, str(e))

            if send_day1:
                c.sudo().write({"rotation_reminder_day1_at": now})
                c._vault_log("update", "Lembrete de rotação (D-1) enviado")
            if send_due:
                c.sudo().write({"rotation_reminder_due_at": now})
                c._vault_log("update", "Lembrete de rotação (D0) enviado")


