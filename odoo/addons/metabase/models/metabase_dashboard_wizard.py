from markupsafe import Markup

from odoo import api, fields, models


class MetabaseDashboardOpenWizard(models.TransientModel):
    _name = "metabase.dashboard.open.wizard"
    _description = "Open Metabase Dashboard (Embedded)"

    dashboard_id = fields.Many2one("metabase.dashboard", required=True, ondelete="cascade")
    url = fields.Char(related="dashboard_id.url", readonly=True)

    embed_html = fields.Html(string="Dashboard", compute="_compute_embed_html", sanitize=False)

    @api.depends("dashboard_id", "dashboard_id.url")
    def _compute_embed_html(self):
        for wiz in self:
            url = wiz.dashboard_id.url or ""
            # Keep it simple; Metabase public dashboards usually allow iframe.
            # sandbox kept permissive enough for Metabase, but still constrained.
            iframe = (
                # The ActionDialog header takes ~56px; keep a small buffer.
                f'<iframe src="{url}" style="width:100vw;max-width:100%;height:calc(100vh - 70px);border:0;" '
                'referrerpolicy="no-referrer" '
                'sandbox="allow-same-origin allow-scripts allow-forms allow-popups allow-popups-to-escape-sandbox" '
                'loading="lazy"></iframe>'
            )
            wiz.embed_html = Markup(iframe) if url else ""


