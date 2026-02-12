from odoo import _, api, fields, models


class BarcodeAppProfileTargetLine(models.Model):
    _name = "stock.barcode.app.profile.target.line"
    _description = "Barcode App Profile Target Sequence Line"
    _order = "sequence, id"

    name = fields.Char(string="Step Name", required=True, translate=True)
    profile_id = fields.Many2one(
        "stock.barcode.app.profile",
        string="Profile",
        required=True,
        ondelete="cascade",
    )
    target_ids = fields.Many2many(
        "stock.barcode.app.target",
        relation="barcode_profile_target_line_target_rel",
        column1="line_id",
        column2="target_id",
        string="Targets",
        help=(
            "Targets to be scanned at this step. "
            "If multiple targets are selected, they can be scanned in any order."
        ),
    )
    sequence = fields.Integer(default=10)
    required = fields.Boolean(
        help="If checked, this target must be scanned",
    )
    step_type = fields.Selection(
        [
            ("initial", "Initial"),
            ("cyclic", "Cyclic"),
            ("final", "Final"),
        ],
        required=True,
        default="cyclic",
        help=(
            "Initial: Executed once at the beginning\n"
            "Cyclic: Repeated for each product line\n"
            "Final: Executed once at the end"
        ),
    )

    @api.constrains("step_type", "profile_id")
    def _check_step_type_uniqueness(self):
        for line in self:
            if line.step_type in ("initial", "final"):
                existing = self.search(
                    [
                        ("profile_id", "=", line.profile_id.id),
                        ("step_type", "=", line.step_type),
                        ("id", "!=", line.id),
                    ]
                )
                if existing:
                    raise models.ValidationError(
                        _("Only one %s step is allowed per profile.") % line.step_type
                    )

    def get_applicable_targets(self, context_data):
        self.ensure_one()
        applicable_targets = self.target_ids

        if context_data.get("product_id"):
            product = self.env["product.product"].browse(context_data["product_id"])

            if product.tracking == "none":
                # Product without tracking: remove lot/serial targets
                applicable_targets = applicable_targets.filtered(
                    lambda t: t.technical_name not in ("lot", "serial")
                )
            elif product.tracking in ("lot", "serial"):
                # Product with tracking: remove product target (already scanned),
                # keep only lot/serial targets
                applicable_targets = applicable_targets.filtered(
                    lambda t: t.technical_name != "product"
                )

        return applicable_targets
