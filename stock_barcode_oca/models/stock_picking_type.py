from odoo import fields, models


class StockPickingType(models.Model):
    _inherit = "stock.picking.type"

    barcode_profile_id = fields.Many2one(
        "stock.barcode.app.profile",
        string="Barcode App Profile",
        domain="[('profile_type', '=', 'picking')]",
        help="Profile to use for barcode operations in this operation type",
    )
