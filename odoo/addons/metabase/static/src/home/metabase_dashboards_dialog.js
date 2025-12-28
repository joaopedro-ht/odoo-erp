/** @odoo-module **/

import { Component, useState } from "@odoo/owl";
import { Dialog } from "@web/core/dialog/dialog";
import { useService } from "@web/core/utils/hooks";

export class MetabaseDashboardsDialog extends Component {
    static template = "metabase.MetabaseDashboardsDialog";
    static components = { Dialog };
    static props = {
        categories: { type: Array },
        dashboards: { type: Array },
    };

    setup() {
        this.action = useService("action");
        this.orm = useService("orm");
        this.state = useState({
            selectedCategoryId: null,
        });
    }

    get categoriesSorted() {
        return [...this.props.categories].sort((a, b) => (a.sequence || 0) - (b.sequence || 0) || a.name.localeCompare(b.name));
    }

    dashboardsForCategory(categoryId) {
        return this.props.dashboards
            .filter((d) => (d.category_id?.[0] || null) === categoryId)
            .sort((a, b) => (a.sequence || 0) - (b.sequence || 0) || a.name.localeCompare(b.name));
    }

    selectCategory(categoryId) {
        this.state.selectedCategoryId = categoryId;
    }

    async openDashboard(dashboard) {
        // Open a new Odoo modal (fullscreen) embedding the dashboard.
        this.action.doAction({
            type: "ir.actions.client",
            tag: "metabase.viewer",
            name: dashboard.name,
            target: "new",
            context: { dialog_size: "fullscreen", footer: false },
            params: { dashboard_id: dashboard.id, url: dashboard.url, name: dashboard.name },
        });
    }

    openListView() {
        this.action.doAction("metabase.action_metabase_dashboard");
    }
}


