import json

from odoo import _, fields, models


class StockPicking(models.Model):
    _inherit = "stock.picking"

    barcode_scan_state = fields.Text(
        help="JSON field to store the current scanning state",
        copy=False,
    )

    def action_open_barcode_interface(self):
        self.ensure_one()

        return {
            "type": "ir.actions.client",
            "tag": "stock_barcode_oca.BarcodeInterface",
            "target": "fullscreen",
            "context": {
                "active_id": self.id,
                "active_model": "stock.picking",
                "barcode_profile_id": self.picking_type_id.barcode_profile_id.id
                if self.picking_type_id.barcode_profile_id
                else False,
            },
        }

    def process_scanned_barcode(self, barcode):
        self.ensure_one()

        if not self.picking_type_id.barcode_profile_id:
            return {
                "success": False,
                "message": _("No barcode profile configured for this operation type"),
            }

        current_state = self._get_scan_state()

        result = self.picking_type_id.barcode_profile_id.process_barcode(
            barcode=barcode, picking=self, current_state=current_state
        )

        if result.get("success") and result.get("state_update"):
            self._update_scan_state(result["state_update"])

        return result

    def _get_scan_state(self):
        """Get barcode scan state - ALWAYS calculate from ORM, not from cached state"""
        self.ensure_one()
        if not self.barcode_scan_state:
            return {}
        try:
            state = json.loads(self.barcode_scan_state)
        except (json.JSONDecodeError, TypeError):
            return {}

        # Mantener solo información de flujo (steps, etc)
        scanned_context = state.get("scanned_context", {})

        # Limpiar objetos que se escriben directo al ORM (locations, packages)
        # Y datos calculados (picked_quantities) y campos legacy (serial_id, *_name)
        clean_context = {
            key: value
            for key, value in scanned_context.items()
            if key
            not in [
                "source_location_id",
                "source_location_name",
                "destination_location_id",
                "destination_location_name",
                "package_id",
                "package_name",
                "serial_id",
                "serial_name",
                "picked_quantities",
                "scanned_serials",
                "_tracking",
                "_just_scanned",
            ]
        }

        # Recalcular picked_quantities desde move_lines (solo para UI)
        clean_context[
            "picked_quantities"
        ] = self._compute_picked_quantities_from_move_lines()

        # Detectar producto actual:
        # PRIORIZAR product_id/lot_id persistido (en progreso) - NO sobrescribirlo
        # Solo si no hay persistido, detectar desde última línea con qty_picked > 0
        if not clean_context.get("product_id"):
            last_line = self.move_line_ids.filtered(
                lambda ml: ml.qty_picked > 0
            ).sorted("write_date", reverse=True)[:1]
            if last_line:
                clean_context["product_id"] = last_line.product_id.id
                clean_context["product_name"] = last_line.product_id.name
                if last_line.lot_id:
                    clean_context["lot_id"] = last_line.lot_id.id
                    clean_context["lot_name"] = last_line.lot_id.name

        state["scanned_context"] = clean_context

        return state

    def _update_scan_state(self, state_dict):
        self.ensure_one()
        self.barcode_scan_state = json.dumps(state_dict)

    def _reset_scan_state(self):
        self.ensure_one()
        self.barcode_scan_state = False

    def _compute_picked_quantities_from_move_lines(self):
        """Calcula picked quantities desde move_lines.qty_picked (fuente de verdad)"""
        self.ensure_one()
        picked = {}
        for move in self.move_ids:
            total = sum(move.move_line_ids.mapped("qty_picked"))
            if total > 0:
                picked[str(move.id)] = total
        return picked

    def _get_next_pending_move_line(self, picked_quantities=None):
        self.ensure_one()
        # Calcular desde BD si no se proporciona
        if picked_quantities is None:
            picked_quantities = self._compute_picked_quantities_from_move_lines()
        return self.move_ids.filtered(
            lambda m: picked_quantities.get(str(m.id), 0) < m.product_uom_qty
        ).sorted("sequence")[:1]

    def button_validate(self):
        """
        Override button_validate para usar qty_picked como fuente de verdad
        cuando el picking usa barcode profile.

        Esto asegura que solo se valide la cantidad escaneada,
        no la cantidad reservada que no fue escaneada.
        """
        # Si el picking usa barcode profile, qty_picked es la fuente de verdad
        for picking in self:
            if picking.picking_type_id.barcode_profile_id:
                for move in picking.move_ids:
                    for move_line in move.move_line_ids:
                        # Si tiene qty_picked > 0, forzar que quantity = qty_picked
                        if move_line.qty_picked > 0:
                            move_line.with_context(move_line_pick_qty=True).write(
                                {"quantity": move_line.qty_picked}
                            )
                        else:
                            # Si no fue escaneado (qty_picked=0),
                            # marcar como no procesado
                            # eliminando la cantidad reservada
                            move_line.with_context(move_line_pick_qty=True).write(
                                {"quantity": 0}
                            )

        # Llamar al método original
        return super().button_validate()
