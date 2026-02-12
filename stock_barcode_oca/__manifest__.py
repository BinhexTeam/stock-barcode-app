{
    "name": "Stock Barcode OCA",
    "summary": "Barcode interface for handling stock operations",
    "author": "Ariel Barreiros",
    "website": "https://github.com/arielbarreiros96/stock-barcode-app",
    "category": "Inventory",
    "version": "17.0.1.0.0",
    "depends": [
        "stock",
        "barcodes",
        "stock_move_line_qty_picked",
    ],
    "data": [
        "security/ir.model.access.csv",
        "data/barcode_target_data.xml",
        "data/barcode_profile_data.xml",
        "views/barcode_profile_views.xml",
        "views/stock_picking_type_views.xml",
        "views/stock_picking_views.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "stock_barcode_oca/static/src/js/**/*",
            "stock_barcode_oca/static/src/xml/**/*",
            "stock_barcode_oca/static/src/css/**/*",
        ],
    },
    "installable": True,
    "application": False,
    "license": "LGPL-3",
}
