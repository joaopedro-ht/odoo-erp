{
    "name": "Access Vault (Credentials / Secrets Management)",
    "version": "19.0.1.0.0",
    "category": "Security",
    "summary": "Secure credentials/secrets management with RBAC, audit logs, and temporary sharing",
    "author": "Hypetech",
    "depends": ["base", "web", "mail"],
    "data": [
        "security/access_vault_groups.xml",
        "security/ir.model.access.csv",
        "security/access_vault_record_rules.xml",
        "views/access_vault_wizard_views.xml",
        "views/access_vault_dashboard_views.xml",
        "views/access_vault_credential_views.xml",
        "views/access_vault_share_views.xml",
        "views/access_vault_log_views.xml",
        "views/access_vault_menus.xml",
        "data/ir_cron.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "access_vault/static/src/**/*.js",
            "access_vault/static/src/**/*.xml",
            "access_vault/static/src/**/*.scss",
        ],
    },
    "application": True,
    "license": "LGPL-3",
}


