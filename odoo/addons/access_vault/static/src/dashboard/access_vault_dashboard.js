/** @odoo-module **/

import { Component, onWillStart, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

export class AccessVaultDashboard extends Component {
    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.state = useState({
            loading: true,
            tab: "overview",
            stats: null,
        });

        onWillStart(async () => {
            await this.reload();
        });
    }

    async reload() {
        this.state.loading = true;
        this.state.stats = await this.orm.call("access.vault.credential", "get_dashboard_stats", [], {});
        this.state.loading = false;
    }

    setTab(tab) {
        this.state.tab = tab;
    }

    openAll() {
        this.action.doAction("access_vault.action_access_vault_credential");
    }

    openDue() {
        this.action.doAction("access_vault.action_access_vault_credential_rotation_due");
    }


    newCredential() {
        this.action.doAction("access_vault.action_access_vault_credential_create_modal");
    }

    openCredential(id) {
        this.action.doAction({
            type: "ir.actions.act_window",
            name: "Credencial",
            res_model: "access.vault.credential",
            res_id: id,
            view_mode: "form",
            views: [[false, "form"]],
            target: "current",
        });
    }
}

AccessVaultDashboard.template = "access_vault.Dashboard";

registry.category("actions").add("access_vault.dashboard", AccessVaultDashboard);


