from odoo import fields, models


class BarcodeAppTarget(models.Model):
    _name = "stock.barcode.app.target"
    _description = "Barcode App Scanning Target"
    _order = "name"

    name = fields.Char(string="Target Name", required=True, translate=True)
    technical_name = fields.Char(
        required=True,
        help="Technical identifier used in code to reference this target",
    )
    description = fields.Text(translate=True)
    active = fields.Boolean(default=True)
