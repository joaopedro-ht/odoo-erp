/** @odoo-module **/

import { registry } from "@web/core/registry";
import { Component, useState } from "@odoo/owl";

export class MetabaseViewerAction extends Component {
    static template = "metabase.MetabaseViewerAction";

    setup() {
        const params = this.props?.action?.params || {};
        this.state = useState({
            name: params.name || "Metabase",
            url: params.url || "",
        });
    }
}

registry.category("actions").add("metabase.viewer", MetabaseViewerAction);


