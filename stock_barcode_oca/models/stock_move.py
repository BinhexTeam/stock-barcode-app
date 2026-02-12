from odoo import _, api, models


class StockMove(models.Model):
    _inherit = "stock.move"

    @api.model
    def increment_qty_picked(self, move_id, amount):
        """
        Incrementa (o decrementa si amount<0) qty_picked de un move.
        Para tracking='lot', solo funciona si hay UN único lote en las move_lines.
        Para tracking='serial', no está permitido (requiere escaneo individual).

        Args:
            move_id: int - ID del stock.move
            amount: float - Cantidad a incrementar (puede ser negativa)

        Returns:
            dict: {'success': bool, 'message': str}
        """
        move = self.browse(move_id)

        if not move.exists():
            return {"success": False, "message": _("Move not found")}

        # Validar que no exceda demand (si amount > 0)
        current_total = sum(move.move_line_ids.mapped("qty_picked"))
        new_total = current_total + amount

        if amount > 0 and new_total > move.product_uom_qty:
            return {
                "success": False,
                "message": _("Cannot exceed demand (%(current)s/%(demand)s)")
                % {"current": new_total, "demand": move.product_uom_qty},
            }

        if new_total < 0:
            return {"success": False, "message": _("Cannot go below zero")}

        # Decidir qué move_line modificar según tracking
        if move.product_id.tracking == "none":
            # Sin tracking: crear/modificar una move_line genérica
            line = move.move_line_ids.filtered(lambda ml: not ml.lot_id)[:1]
            if not line:
                # Crear nueva move_line
                line = (
                    self.env["stock.move.line"]
                    .with_context(move_line_pick_qty=True)
                    .create(
                        {
                            "move_id": move.id,
                            "product_id": move.product_id.id,
                            "location_id": move.location_id.id,
                            "location_dest_id": move.location_dest_id.id,
                            "product_uom_id": move.product_uom.id,
                            "picking_id": move.picking_id.id,
                            "qty_picked": 0,
                        }
                    )
                )

            new_qty = line.qty_picked + amount
            line.with_context(move_line_pick_qty=True).write(
                {"qty_picked": max(0, new_qty)}
            )

            return {"success": True, "message": _("Quantity updated: %s") % new_qty}

        elif move.product_id.tracking == "lot":
            # Con tracking por lote: solo si hay exactamente UN lote
            unique_lots = move.move_line_ids.filtered(lambda ml: ml.lot_id).mapped(
                "lot_id"
            )

            if len(unique_lots) == 0:
                return {
                    "success": False,
                    "message": _("No lot found. Please scan lot first."),
                }

            if len(unique_lots) > 1:
                return {
                    "success": False,
                    "message": _(
                        "Ambiguous: multiple lots found. "
                        "Cannot determine which to modify."
                    ),
                }

            # Incrementar la move_line con ese lote único
            line = move.move_line_ids.filtered(lambda ml: ml.lot_id == unique_lots)[:1]
            new_qty = line.qty_picked + amount

            if new_qty < 0:
                return {"success": False, "message": _("Cannot go below zero")}

            line.with_context(move_line_pick_qty=True).write({"qty_picked": new_qty})

            return {
                "success": True,
                "message": _("Quantity updated: %(qty)s (Lot: %(lot)s)")
                % {"qty": new_qty, "lot": unique_lots.name},
            }

        else:  # serial
            return {
                "success": False,
                "message": _(
                    "Serial tracking requires scanning individual serial numbers"
                ),
            }
