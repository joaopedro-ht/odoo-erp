from odoo import api, fields, models


class MetabaseCategory(models.Model):
    _name = "metabase.category"
    _description = "Metabase Category"
    _order = "sequence, name, id"

    name = fields.Char(required=True, index=True)
    sequence = fields.Integer(default=10)

    dashboard_ids = fields.One2many(
        "metabase.dashboard",
        "category_id",
        string="Dashboards",
    )

    dashboards_count = fields.Integer(compute="_compute_dashboards_count")

    @api.depends("dashboard_ids")
    def _compute_dashboards_count(self):
        for rec in self:
            rec.dashboards_count = len(rec.dashboard_ids)


