/** @odoo-module **/

import { registry } from "@web/core/registry";
import { Component, onMounted, useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";

import { MetabaseDashboardsDialog } from "./metabase_dashboards_dialog";

export class MetabaseHomeAction extends Component {
    static template = "metabase.MetabaseHomeAction";
    static components = { MetabaseDashboardsDialog };

    setup() {
        this.dialog = useService("dialog");
        this.orm = useService("orm");
        this.state = useState({ opened: false });

        onMounted(async () => {
            // abre automaticamente ao clicar no app na home
            await this.openDialog();
        });
    }

    async fetchData() {
        const categories = await this.orm.searchRead(
            "metabase.category",
            [],
            ["name", "sequence", "dashboards_count"]
        );
        const dashboards = await this.orm.searchRead(
            "metabase.dashboard",
            [["active", "=", true]],
            ["name", "sequence", "category_id", "url", "description"]
        );
        return { categories, dashboards };
    }

    async openDialog() {
        if (this.state.opened) {
            return;
        }
        this.state.opened = true;
        const data = await this.fetchData();
        this.dialog.add(MetabaseDashboardsDialog, {
            categories: data.categories,
            dashboards: data.dashboards,
        });
    }
}

registry.category("actions").add("metabase.home", MetabaseHomeAction);


