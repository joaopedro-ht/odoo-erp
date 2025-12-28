from odoo import api, fields, models


class MetabaseDashboard(models.Model):
    _name = "metabase.dashboard"
    _description = "Metabase Dashboard"
    _order = "sequence, name, id"

    name = fields.Char(required=True, index=True)
    active = fields.Boolean(default=True)
    sequence = fields.Integer(default=10)

    category_id = fields.Many2one(
        "metabase.category",
        string="Categoria",
        required=True,
        index=True,
        ondelete="restrict",
    )

    url = fields.Char(string="URL", required=True)
    description = fields.Text(string="Descrição")

    @api.constrains("url")
    def _check_url(self):
        for rec in self:
            if rec.url and not (rec.url.startswith("http://") or rec.url.startswith("https://")):
                # Metabase público normalmente é http(s)
                raise models.ValidationError("A URL deve começar com http:// ou https://")

    def action_open_viewer(self):
        self.ensure_one()
        return {
            "name": self.name,
            "type": "ir.actions.client",
            "tag": "metabase.viewer",
            "target": "new",
            "context": {**self.env.context, "dialog_size": "fullscreen", "footer": False},
            "params": {"dashboard_id": self.id, "url": self.url, "name": self.name},
        }


