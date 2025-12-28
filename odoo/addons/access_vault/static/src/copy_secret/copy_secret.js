/** @odoo-module **/

import { browser } from "@web/core/browser/browser";
import { registry } from "@web/core/registry";
import { Component } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";

/**
 * Button that fetches the secret from backend and copies it to the clipboard.
 * The secret is never rendered in the UI.
 */
export class AccessVaultCopySecretButton extends Component {
    static template = "access_vault.CopySecretButton";
    static props = { record: Object };

    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");
    }

    async onClick(ev) {
        ev.preventDefault();
        ev.stopPropagation();
        try {
            const secret = await this.orm.call(
                "access.vault.secret",
                "action_get_secret_for_copy",
                [this.props.record.resId],
                {}
            );
            await this._copyText(secret);
            this.notification.add("Credencial copiada.", { type: "success" });
        } catch (e) {
            this.notification.add("Não foi possível copiar a credencial.", { type: "danger" });
            browser.console.warn(e);
        }
    }

    async _copyText(value) {
        // Prefer Clipboard API, fallback to execCommand for stricter browser policies.
        try {
            if (browser.navigator.clipboard?.writeText) {
                await browser.navigator.clipboard.writeText(value);
                return;
            }
        } catch (e) {
            // fallback below
            browser.console.warn(e);
        }
        const ta = document.createElement("textarea");
        ta.value = value;
        ta.setAttribute("readonly", "true");
        ta.style.position = "fixed";
        ta.style.top = "-1000px";
        ta.style.left = "-1000px";
        document.body.appendChild(ta);
        ta.focus();
        ta.select();
        try {
            document.execCommand("copy");
        } finally {
            document.body.removeChild(ta);
        }
    }
}

registry.category("view_widgets").add("access_vault_copy_secret", { component: AccessVaultCopySecretButton });


