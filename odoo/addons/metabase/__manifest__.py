{
    "name": "METABASE",
    "summary": "Catálogo de dashboards do Metabase",
    "version": "19.0.1.0.0",
    "category": "Productivity",
    "license": "OEEL-1",
    "author": "Hypetech",
    "depends": ["web", "web_enterprise"],
    "data": [
        "security/ir.model.access.csv",
        "views/metabase_category_views.xml",
        "views/metabase_dashboard_views.xml",
        "views/metabase_dashboard_wizard_views.xml",
        "views/metabase_menus.xml",
        "data/metabase_data.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "metabase/static/src/**/*.js",
            "metabase/static/src/**/*.xml",
            "metabase/static/src/**/*.scss",
        ],
    },
    "application": True,
    "installable": True,
}


