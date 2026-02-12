from odoo import _, fields, models


class BarcodeAppProfile(models.Model):
    _name = "stock.barcode.app.profile"
    _description = "Barcode App Profile"
    _order = "name"

    name = fields.Char(string="Profile Name", required=True)
    active = fields.Boolean(default=True)
    company_id = fields.Many2one(
        "res.company",
        string="Company",
        default=lambda self: self.env.company,
    )
    profile_type = fields.Selection(
        [("picking", "Stock Pickings")],
        required=True,
        default="picking",
        help="Type of operation this profile handles",
    )
    barcode_nomenclature_id = fields.Many2one(
        "barcode.nomenclature",
        string="Barcode Nomenclature",
        required=True,
        help="Barcode nomenclature used to parse scanned barcodes",
    )
    allow_lot_sn_creation = fields.Boolean(
        string="Allow Lot/SN Creation",
        help="Allow creating new lots or serial numbers on the fly when scanning",
    )
    strict_mode = fields.Boolean(
        default=False,
        help="When enabled, steps must be completed sequentially in exact order. "
        "When disabled (flexible), system will adaptively find "
        "appropriate step based on scanned item.",
    )
    allow_exceed_demand = fields.Boolean(
        string="Allow Exceeding Demand",
        default=False,
        help="When enabled, allows scanning quantities "
        "that exceed the demand, showing only a warning. "
        "When disabled, blocks scanning when demand is "
        "reached and prevents qty_picked from increasing.",
    )
    target_scanning_sequence_ids = fields.One2many(
        "stock.barcode.app.profile.target.line",
        "profile_id",
        string="Scanning Sequence",
        help="Define the order in which targets should be scanned",
    )

    def process_barcode(self, barcode, picking, current_state):
        self.ensure_one()

        sequence_lines = self.target_scanning_sequence_ids.sorted("sequence")
        if not sequence_lines:
            return {
                "success": False,
                "message": _("No scanning sequence configured for this profile"),
            }

        if self.barcode_nomenclature_id.is_gs1_nomenclature:
            return self._process_barcode_gs1(
                barcode, picking, current_state, sequence_lines
            )
        else:
            return self._process_barcode_standard(
                barcode, picking, current_state, sequence_lines
            )

    def _process_barcode_gs1(self, barcode, picking, current_state, sequence_lines):
        parsed_results = self.barcode_nomenclature_id.parse_barcode(barcode)
        if not parsed_results:
            return {
                "success": False,
                "message": _("Invalid GS1 barcode: %s") % barcode,
            }

        if not current_state:
            initial_step = sequence_lines.filtered(
                lambda line: line.step_type == "initial"
            )
            current_step = initial_step if initial_step else sequence_lines[0]
        else:
            current_step = sequence_lines.filtered(
                lambda line: line.id == current_state.get("current_step_id")
            )
            if not current_step:
                current_step = sequence_lines[0]

        context = current_state.get("scanned_context", {})

        matched_data = []
        for parsed_item in parsed_results:
            barcode_data = self._convert_gs1_parsed_to_data(parsed_item)
            if barcode_data:
                validation = self._validate_barcode_for_step(
                    barcode_data, current_step, context
                )
                if validation["valid"]:
                    matched_data.append(
                        {
                            "barcode_data": barcode_data,
                            "target": validation["matched_target"],
                        }
                    )

        if not matched_data:
            return {
                "success": False,
                "message": _(
                    "GS1 barcode does not contain expected data for current step"
                ),
            }

        combined_context_update = {}
        messages = []
        move_id = None
        quantity_to_add = 0

        for match in matched_data:
            apply_result = self._apply_barcode_to_picking(
                match["barcode_data"], picking, context, match["target"]
            )
            if apply_result["success"]:
                combined_context_update.update(apply_result["context_update"])
                messages.append(apply_result["message"])
                if not move_id and "move_id" in apply_result:
                    move_id = apply_result["move_id"]
                    quantity_to_add = apply_result.get("quantity_to_add", 0)

        context.update(combined_context_update)

        next_step_info = self._determine_next_step(current_step, picking, context)

        # Use the context from next_step_info if available (it may be cleaned)
        final_context = next_step_info.get("context", context)

        next_step = next_step_info["step"]
        state_update = {
            "current_step_id": next_step.id if next_step else None,
            "current_step_sequence": next_step.sequence if next_step else None,
            "current_step_type": next_step.step_type if next_step else None,
            # Add nested structure for backward compatibility with tests
            "step": {
                "step_id": next_step.id,
                "sequence": next_step.sequence,
                "step_type": next_step.step_type,
            }
            if next_step
            else None,
            "scanned_context": final_context,
            "completed_steps": current_state.get("completed_steps", [])
            + [current_step.id],
        }

        result = {
            "success": True,
            "message": " | ".join(messages),
            "state_update": state_update,
            "next_step_info": next_step_info,
            "scan_instructions": next_step_info.get("instructions", ""),
            "scanned_data": combined_context_update,
            "completed_step_id": current_step.id,
            "sequence_completed": next_step_info["step"] is None,
        }

        if move_id:
            result["move_id"] = move_id
            result["quantity_to_add"] = quantity_to_add

        return result

    def _parse_and_convert_barcode(self, barcode):
        """Parse and convert barcode to standard data structure"""
        parsed_result = self.barcode_nomenclature_id.parse_barcode(barcode)
        if not parsed_result or parsed_result.get("type") == "error":
            return {
                "success": False,
                "message": _("Barcode not recognized: %s") % barcode,
            }

        barcode_data = self._convert_standard_parsed_to_data(parsed_result, barcode)
        if not barcode_data:
            return {
                "success": False,
                "message": _("Could not interpret barcode: %s") % barcode,
            }

        return {"success": True, "barcode_data": barcode_data}

    def _determine_current_step(self, current_state, sequence_lines):
        """Determine which step is currently active"""
        if not current_state:
            initial_step = sequence_lines.filtered(
                lambda line: line.step_type == "initial"
            )
            return initial_step if initial_step else sequence_lines[0]

        current_step = sequence_lines.filtered(
            lambda line: line.id == current_state.get("current_step_id")
        )
        if not current_step:
            return sequence_lines[0]
        return current_step

    def _validate_early_conditions(self, barcode_data, current_step, picking, context):
        """Perform early validations that can fail fast"""
        # Special early validation for lot/serial
        if barcode_data["type"] == "lot":
            product_id_in_context = context.get("product_id")
            if not product_id_in_context:
                return {
                    "success": False,
                    "message": _(
                        "Please scan product first before scanning lot/serial"
                    ),
                }

        # Special validation for products in final step
        if current_step.step_type == "final" and barcode_data["type"] == "product":
            product_id = barcode_data["id"]
            move = picking.move_ids.filtered(lambda m: m.product_id.id == product_id)[
                :1
            ]
            if move:
                picked_quantities = picking._compute_picked_quantities_from_move_lines()
                current_picked = picked_quantities.get(str(move.id), 0)
                if current_picked >= move.product_uom_qty:
                    if not self.allow_exceed_demand:
                        return {
                            "success": False,
                            "message": _(
                                "Scanned quantity exceeds demand for "
                                "product %(product)s (%(qty)s/%(demand)s)"
                            )
                            % {
                                "product": move.product_id.name,
                                "qty": current_picked,
                                "demand": move.product_uom_qty,
                            },
                        }

        return {"success": True}

    def _validate_and_apply_barcode(
        self, barcode_data, current_step, sequence_lines, picking, context
    ):
        """Validate barcode against step and apply if valid"""
        # Special case: product scanned when lot step is expected
        # This should update context but not apply to picking yet
        if barcode_data["type"] == "product" and current_step.target_ids.filtered(
            lambda t: t.technical_name == "lot"
        ):
            product_id = barcode_data["id"]
            product = self.env["product.product"].browse(product_id)
            if product.tracking in ("lot", "serial"):
                # Update context with product and return success without applying
                return {
                    "success": True,
                    "apply_result": {
                        "success": True,
                        "message": _("Product scanned: %s (waiting for lot/serial)")
                        % product.name,
                        "context_update": {
                            "product_id": product_id,
                            "product_name": product.name,
                        },
                    },
                    "validation": {"valid": True, "matched_target": None},
                    "current_step": current_step,
                    "barcode_data": barcode_data,
                }

        validation = self._validate_barcode_for_step(
            barcode_data, current_step, context
        )

        if not validation["valid"]:
            # Try to skip optional initial step
            if current_step.step_type == "initial" and not current_step.required:
                next_in_sequence = sequence_lines.filtered(
                    lambda line: line.sequence > current_step.sequence
                ).sorted("sequence")[:1]
                if next_in_sequence:
                    next_validation = self._validate_barcode_for_step(
                        barcode_data, next_in_sequence, context
                    )
                    if next_validation["valid"]:
                        current_step = next_in_sequence
                        validation = next_validation

            # If still not valid, try smart detection
            if not validation["valid"]:
                smart_result = self._try_smart_detection(
                    barcode_data, current_step, context
                )
                if smart_result and "detected_product" in smart_result:
                    product_validation = self._validate_barcode_for_step(
                        smart_result["detected_product"], current_step, context
                    )
                    if product_validation["valid"]:
                        context["product_id"] = smart_result["detected_product"]["id"]
                        context["product_name"] = smart_result["detected_product"][
                            "name"
                        ]
                        barcode_data = smart_result
                        validation = self._validate_barcode_for_step(
                            barcode_data, current_step, context
                        )
                        if not validation["valid"]:
                            return {
                                "success": False,
                                "message": validation.get(
                                    "reason", _("Invalid barcode for current step")
                                ),
                            }
                    else:
                        return {
                            "success": False,
                            "message": product_validation.get(
                                "reason", _("Invalid barcode for current step")
                            ),
                        }
                else:
                    return {
                        "success": False,
                        "message": validation.get(
                            "reason", _("Invalid barcode for current step")
                        ),
                    }

        # Ensure we have matched_target
        if not validation.get("matched_target"):
            return {
                "success": False,
                "message": _("Could not determine target for barcode"),
            }

        apply_result = self._apply_barcode_to_picking(
            barcode_data, picking, context, validation["matched_target"]
        )
        if not apply_result["success"]:
            return apply_result

        return {
            "success": True,
            "apply_result": apply_result,
            "validation": validation,
            "current_step": current_step,
            "barcode_data": barcode_data,
        }

    def _process_barcode_standard(
        self, barcode, picking, current_state, sequence_lines
    ):
        # Parse and convert barcode
        parse_result = self._parse_and_convert_barcode(barcode)
        if not parse_result["success"]:
            return parse_result
        barcode_data = parse_result["barcode_data"]

        # Determine current step
        current_step = self._determine_current_step(current_state, sequence_lines)
        context = (
            current_state.get("scanned_context", {}) if current_state else {}
        ).copy()

        # Early validations
        early_validation = self._validate_early_conditions(
            barcode_data, current_step, picking, context
        )
        if not early_validation["success"]:
            return early_validation

        # Validate and apply barcode
        apply_wrapper = self._validate_and_apply_barcode(
            barcode_data, current_step, sequence_lines, picking, context
        )
        if not apply_wrapper["success"]:
            return apply_wrapper

        # Extract results from wrapper
        apply_result = apply_wrapper["apply_result"]
        validation = apply_wrapper["validation"]
        current_step = apply_wrapper["current_step"]
        barcode_data = apply_wrapper["barcode_data"]

        # Build context for next step (filter out internal/transient keys)
        flow_context = {
            key: value
            for key, value in apply_result.get("context_update", {}).items()
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
        context.update(flow_context)

        # Add product detection info to message if applicable
        if validation.get("detected_product"):
            apply_result["message"] += (
                _(" (Product detected: %s)") % validation["detected_product"]["name"]
            )

        # Determine next step
        next_step_info = self._determine_next_step(current_step, picking, context)
        final_context = next_step_info.get("context", context)

        # Build state update
        next_step = next_step_info["step"]
        state_update = {
            "current_step_id": next_step.id if next_step else None,
            "current_step_sequence": next_step.sequence if next_step else None,
            "current_step_type": next_step.step_type if next_step else None,
            "step": {
                "step_id": next_step.id,
                "sequence": next_step.sequence,
                "step_type": next_step.step_type,
            }
            if next_step
            else None,
            "scanned_context": final_context,
            "completed_steps": current_state.get("completed_steps", [])
            + [current_step.id],
        }

        # Build final result
        result = {
            "success": True,
            "message": apply_result.get("message", _("Barcode processed successfully")),
            "state_update": state_update,
            "next_step_info": next_step_info,
            "scan_instructions": next_step_info.get("instructions", ""),
            "scanned_data": apply_result["context_update"],
            "completed_step_id": current_step.id,
            "sequence_completed": next_step_info["step"] is None,
        }

        if "move_id" in apply_result:
            result["move_id"] = apply_result["move_id"]
            result["quantity_to_add"] = apply_result.get("quantity_to_add", 0)

        return result

    def _convert_gs1_parsed_to_data(self, parsed_item):
        item_type = parsed_item.get("rule").type
        value = parsed_item.get("value")
        ai = parsed_item.get("ai")

        if item_type == "product":
            product = self.env["product.product"].search(
                [("barcode", "=", value)], limit=1
            )
            if product:
                return {
                    "type": "product",
                    "id": product.id,
                    "record": product,
                    "name": product.name,
                    "ai": ai,
                }

        elif item_type in ("lot", "lot_number"):
            lot = self.env["stock.lot"].search([("name", "=", value)], limit=1)
            if lot:
                return {
                    "type": "lot",
                    "id": lot.id,
                    "record": lot,
                    "name": lot.name,
                    "product_id": lot.product_id.id,
                    "ai": ai,
                }
            else:
                return {
                    "type": "lot",
                    "id": None,
                    "name": value,
                    "ai": ai,
                }

        elif item_type == "quantity":
            return {"type": "quantity", "value": value, "ai": ai}

        elif item_type in ("expiration_date", "use_date", "pack_date"):
            return {"type": item_type, "value": value, "ai": ai}

        elif item_type in ("location", "location_dest"):
            location = self.env["stock.location"].search(
                [("barcode", "=", value)], limit=1
            )
            if location:
                return {
                    "type": item_type,
                    "id": location.id,
                    "record": location,
                    "name": location.complete_name,
                    "ai": ai,
                }

        elif item_type == "package":
            package = self.env["stock.quant.package"].search(
                [("name", "=", value)], limit=1
            )
            if package:
                return {
                    "type": "package",
                    "id": package.id,
                    "record": package,
                    "name": package.name,
                    "ai": ai,
                }

        return None

    def _convert_standard_parsed_to_data(self, parsed_result, original_barcode):
        result_type = parsed_result.get("type")
        code = parsed_result.get("code", original_barcode)

        if result_type == "product":
            product = self.env["product.product"].search(
                [("barcode", "=", code)], limit=1
            )
            if product:
                return {
                    "type": "product",
                    "id": product.id,
                    "record": product,
                    "name": product.name,
                }
            product = self.env["product.product"].search(
                [("default_code", "=", code)], limit=1
            )
            if product:
                return {
                    "type": "product",
                    "id": product.id,
                    "record": product,
                    "name": product.name,
                }

        location = self.env["stock.location"].search(
            [("barcode", "=", original_barcode)], limit=1
        )
        if location:
            return {
                "type": "location",
                "id": location.id,
                "record": location,
                "name": location.complete_name,
            }

        lot = self.env["stock.lot"].search([("name", "=", original_barcode)], limit=1)
        if lot:
            return {
                "type": "lot",
                "id": lot.id,
                "record": lot,
                "name": lot.name,
                "product_id": lot.product_id.id,
            }

        package = self.env["stock.quant.package"].search(
            [("name", "=", original_barcode)], limit=1
        )
        if package:
            return {
                "type": "package",
                "id": package.id,
                "record": package,
                "name": package.name,
            }

        # If nothing matched but barcode looks like it could be a lot/serial
        # (alphanumeric text), return it as a potential lot for creation
        if original_barcode and original_barcode.strip():
            return {
                "type": "lot",
                "id": None,
                "name": original_barcode,
            }

        return None

    def _validate_barcode_for_step(self, barcode_data, step, context):
        target_tech_names = step.target_ids.mapped("technical_name")
        barcode_type = barcode_data["type"]

        # Validación de modo estricto: no permitir cambiar de producto
        # hasta completar el actual
        if self.strict_mode and barcode_type == "product":
            current_product_id = context.get("product_id")
            scanned_product_id = barcode_data["id"]

            # Si hay un producto en contexto y es diferente al escaneado
            if current_product_id and current_product_id != scanned_product_id:
                # Verificar si el producto actual está completo
                # Necesitamos el picking para verificar
                # Nota: En modo estricto debemos completar secuencialmente
                return {
                    "valid": False,
                    "reason": _(
                        "Strict mode: Complete current product before scanning another"
                    ),
                }

        if barcode_type == "location":
            if "source_location" in target_tech_names:
                matched_target = step.target_ids.filtered(
                    lambda t: t.technical_name == "source_location"
                )[0]
                return {"valid": True, "matched_target": matched_target}
            elif "destination_location" in target_tech_names:
                matched_target = step.target_ids.filtered(
                    lambda t: t.technical_name == "destination_location"
                )[0]
                return {"valid": True, "matched_target": matched_target}

        elif barcode_type == "location_dest":
            if "destination_location" in target_tech_names:
                matched_target = step.target_ids.filtered(
                    lambda t: t.technical_name == "destination_location"
                )[0]
                return {"valid": True, "matched_target": matched_target}

        elif barcode_type == "product":
            if "product" in target_tech_names:
                matched_target = step.target_ids.filtered(
                    lambda t: t.technical_name == "product"
                )[0]
                return {"valid": True, "matched_target": matched_target}

        elif barcode_type == "lot":
            # Special handling for lot/serial validation
            # Even if step doesn't have lot/serial
            # target, provide specific error messages

            # First check if product is in context
            product_id = context.get("product_id")
            if not product_id:
                return {
                    "valid": False,
                    "reason": _("Please scan product first before scanning lot/serial"),
                }

            # Validate tracking if product is in context
            product = self.env["product.product"].browse(product_id)
            if product.tracking == "none":
                return {
                    "valid": False,
                    "reason": _("Product %(product)s doesn't use lot/serial tracking")
                    % {"product": product.name},
                }

            # Now check if step allows lot/serial
            if "lot" in target_tech_names or "serial" in target_tech_names:
                matched_target = step.target_ids.filtered(
                    lambda t: t.technical_name in ("lot", "serial")
                )[0]
                return {"valid": True, "matched_target": matched_target}
            else:
                # Step doesn't allow lot/serial
                return {
                    "valid": False,
                    "reason": _("Expected %(expected)s, got %(actual)s")
                    % {
                        "expected": ", ".join(target_tech_names),
                        "actual": barcode_type,
                    },
                }

        elif barcode_type == "package":
            if "package" in target_tech_names:
                matched_target = step.target_ids.filtered(
                    lambda t: t.technical_name == "package"
                )[0]
                return {"valid": True, "matched_target": matched_target}

        return {
            "valid": False,
            "reason": _("Expected %(expected)s, got %(actual)s")
            % {"expected": ", ".join(target_tech_names), "actual": barcode_type},
        }

    def _try_smart_detection(self, barcode_data, step, context):
        if (
            barcode_data["type"] == "lot"
            and "product_id" in barcode_data
            and barcode_data["product_id"]
        ):
            product_target = step.target_ids.filtered(
                lambda t: t.technical_name == "product"
            )
            if product_target:
                product_id = barcode_data["product_id"]
                product = self.env["product.product"].browse(product_id)
                barcode_data["detected_product"] = {
                    "type": "product",
                    "id": product_id,
                    "name": product.name,
                    "record": product,
                }
                return barcode_data
        return None

    def _should_increment_quantity(self, barcode_type, product, context):
        """
        Determine if qty_picked should be incremented based on:
        - Type of barcode scanned
        - Product tracking type
        - Current context state

        Returns 1.0 if quantity should be incremented, 0 otherwise
        """
        if barcode_type == "product":
            # Only increment if product has no tracking
            return 1.0 if product.tracking == "none" else 0

        elif barcode_type == "lot":
            # Increment only if product has lot or serial tracking
            return 1.0 if product.tracking in ("lot", "serial") else 0

        return 0

    def _create_or_update_move_line_for_serial(self, move, lot_id, picking, context):
        """
        Para productos con tracking='serial', crea un stock.move.line individual.

        Args:
            move: stock.move - El movimiento que se está procesando
            lot_id: int - ID del lote/serial escaneado
            picking: stock.picking - El picking actual
            context: dict - Contexto de escaneo

        Returns:
            dict con:
                - success: bool
                - message: str
                - move_line_id: int (si success=True)
        """
        # 1. Buscar move_line existente con este serial YA asignado
        existing_line_with_serial = move.move_line_ids.filtered(
            lambda ml: ml.lot_id and ml.lot_id.id == lot_id
        )

        if existing_line_with_serial:
            # Si ya tiene qty_picked > 0, significa que ya fue escaneado/procesado
            if existing_line_with_serial[0].qty_picked > 0:
                return {
                    "success": False,
                    "message": _("Serial already used in this operation"),
                }

            # Si qty_picked == 0, es un move_line reservado - actualizarlo
            lot = existing_line_with_serial[0].lot_id
            update_vals = {
                "qty_picked": 1.0,
                "lot_name": lot.name,
            }
            existing_line_with_serial[0].with_context(move_line_pick_qty=True).write(
                update_vals
            )
            return {
                "success": True,
                "message": _("Serial %(serial)s registered") % {"serial": lot.name},
                "move_line_id": existing_line_with_serial[0].id,
            }

        # 2. Buscar move_line SIN serial asignado (reserva genérica de action_confirm)
        #    Esto evita crear líneas duplicadas cuando ya hay reservas sin serial
        line_without_serial = move.move_line_ids.filtered(
            lambda ml: not ml.lot_id and ml.qty_picked == 0
        )

        if line_without_serial:
            # Asignar serial a línea existente reservada
            lot = self.env["stock.lot"].browse(lot_id)
            update_vals = {
                "lot_id": lot_id,
                "qty_picked": 1.0,
                "quantity": 1.0,
                "lot_name": lot.name,
            }

            # Buscar quant si es outgoing/internal
            if picking.picking_type_id.code in ("outgoing", "internal"):
                quant = self.env["stock.quant"].search(
                    [
                        ("lot_id", "=", lot_id),
                        ("location_id", "=", move.location_id.id),
                        ("product_id", "=", move.product_id.id),
                    ],
                    limit=1,
                )

                if quant:
                    # Calcular qty disponible en Python
                    available_qty = quant.quantity - quant.reserved_quantity
                    if available_qty < 1.0:
                        lot = self.env["stock.lot"].browse(lot_id)
                        return {
                            "success": False,
                            "message": _(
                                "Serial %(serial)s has no available quantity "
                                "in source location (qty: %(qty)s, "
                                "reserved: %(reserved)s)"
                            )
                            % {
                                "serial": lot.name,
                                "qty": quant.quantity,
                                "reserved": quant.reserved_quantity,
                            },
                        }
                    update_vals["quant_id"] = quant.id
                else:
                    lot = self.env["stock.lot"].browse(lot_id)
                    return {
                        "success": False,
                        "message": _(
                            "Serial %(serial)s not found "
                            "in source location %(location)s"
                        )
                        % {
                            "serial": lot.name,
                            "location": move.location_id.display_name,
                        },
                    }

            line_without_serial[0].with_context(move_line_pick_qty=True).write(
                update_vals
            )
            return {
                "success": True,
                "message": _("Serial %(serial)s registered") % {"serial": lot.name},
                "move_line_id": line_without_serial[0].id,
            }

        # 3. Verificar disponibilidad para operaciones outgoing e internal
        if picking.picking_type_id.code in ("outgoing", "internal"):
            # Validar que el serial existe en inventario en la ubicación de origen
            quant = self.env["stock.quant"].search(
                [
                    ("lot_id", "=", lot_id),
                    ("location_id", "=", move.location_id.id),
                    ("product_id", "=", move.product_id.id),
                ],
                limit=1,
            )

            if not quant:
                lot = self.env["stock.lot"].browse(lot_id)
                return {
                    "success": False,
                    "message": _(
                        "Serial %(serial)s not found in source location %(location)s"
                    )
                    % {
                        "serial": lot.name,
                        "location": move.location_id.display_name,
                    },
                }

            # Calcular qty disponible en Python (no en dominio)
            available_qty = quant.quantity - quant.reserved_quantity

            if available_qty < 1.0:
                lot = self.env["stock.lot"].browse(lot_id)
                return {
                    "success": False,
                    "message": _(
                        "Serial %(serial)s has no available "
                        "quantity (qty: %(qty)s, reserved: %(reserved)s)"
                    )
                    % {
                        "serial": lot.name,
                        "qty": quant.quantity,
                        "reserved": quant.reserved_quantity,
                    },
                }

        # 4. Crear nueva move_line con qty=1.0 y qty_picked=1.0
        lot = self.env["stock.lot"].browse(lot_id)
        move_line_vals = {
            "move_id": move.id,
            "product_id": move.product_id.id,
            "lot_id": lot_id,
            "lot_name": lot.name,
            "qty_picked": 1.0,
            "quantity": 1.0,
            "product_uom_id": move.product_uom.id,
            "location_id": move.location_id.id,
            "location_dest_id": move.location_dest_id.id,
            "picking_id": picking.id,
        }

        # Buscar quant si ya existe en operaciones outgoing/internal
        if picking.picking_type_id.code in ("outgoing", "internal"):
            quant = self.env["stock.quant"].search(
                [
                    ("lot_id", "=", lot_id),
                    ("location_id", "=", move.location_id.id),
                    ("product_id", "=", move.product_id.id),
                    ("quantity", ">", 0),
                ],
                limit=1,
            )
            if quant:
                move_line_vals["quant_id"] = quant.id

        move_line = (
            self.env["stock.move.line"]
            .with_context(move_line_pick_qty=True)
            .create(move_line_vals)
        )

        return {
            "success": True,
            "message": _("Serial %(serial)s registered")
            % {"serial": move_line.lot_id.name},
            "move_line_id": move_line.id,
        }

    def _create_or_update_move_line_for_lot(
        self, move, lot_id, qty_to_add, picking, lot_name=None
    ):
        """
        Crea o actualiza move_lines para productos con tracking='lot'.
        Similar a _create_or_update_move_line_for_serial pero permite qty > 1.

        :param lot_name: Optional lot name for error messages,
                         will be fetched if not provided
        """
        # Get lot name for messages if not provided
        if not lot_name:
            lot = self.env["stock.lot"].browse(lot_id)
            lot_name = lot.name

        # Buscar move_line existente con este lote
        existing_line = move.move_line_ids.filtered(
            lambda ml: ml.lot_id and ml.lot_id.id == lot_id
        )

        if existing_line:
            # Actualizar qty_picked en línea existente
            new_qty = existing_line[0].qty_picked + qty_to_add
            existing_line[0].with_context(move_line_pick_qty=True).write(
                {"qty_picked": new_qty}
            )
            return {
                "success": True,
                "message": _("Lot %(lot)s quantity updated: %(qty)s")
                % {"lot": existing_line[0].lot_id.name, "qty": new_qty},
                "move_line_id": existing_line[0].id,
            }

        # Buscar move_line sin lote asignado (reserva genérica)
        line_without_lot = move.move_line_ids.filtered(lambda ml: not ml.lot_id)

        if line_without_lot:
            # Asignar lote a línea existente
            lot = self.env["stock.lot"].browse(lot_id)
            update_vals = {
                "lot_id": lot_id,
                "qty_picked": qty_to_add,
                "lot_name": lot.name,
            }

            # Buscar quant si es outgoing/internal y validar
            if picking.picking_type_id.code in ("outgoing", "internal"):
                quant = self.env["stock.quant"].search(
                    [
                        ("lot_id", "=", lot_id),
                        ("location_id", "=", move.location_id.id),
                        ("product_id", "=", move.product_id.id),
                    ],
                    limit=1,
                )

                if not quant:
                    return {
                        "success": False,
                        "message": _(
                            "Lot %(lot)s not found in source location %(location)s"
                        )
                        % {
                            "lot": lot.name,
                            "location": move.location_id.display_name,
                        },
                    }

                # Calcular qty disponible en Python
                available_qty = quant.quantity - quant.reserved_quantity

                if available_qty < qty_to_add:
                    return {
                        "success": False,
                        "message": _(
                            "Insufficient available quantity for "
                            "lot %(lot)s. Available: %(available)s, "
                            "Requesting: %(request)s"
                        )
                        % {
                            "lot": lot.name,
                            "available": available_qty,
                            "request": qty_to_add,
                        },
                    }

                update_vals["quant_id"] = quant.id

            line_without_lot[0].with_context(move_line_pick_qty=True).write(update_vals)
            return {
                "success": True,
                "message": _("Lot %(lot)s assigned") % {"lot": lot.name},
                "move_line_id": line_without_lot[0].id,
            }

        # Crear nueva move_line
        lot = self.env["stock.lot"].browse(lot_id)
        move_line_vals = {
            "move_id": move.id,
            "product_id": move.product_id.id,
            "lot_id": lot_id,
            "lot_name": lot.name,
            "qty_picked": qty_to_add,
            "quantity": qty_to_add,
            "product_uom_id": move.product_uom.id,
            "location_id": move.location_id.id,
            "location_dest_id": move.location_dest_id.id,
            "picking_id": picking.id,
        }

        # Buscar quant si es outgoing/internal y validar
        if picking.picking_type_id.code in ("outgoing", "internal"):
            quant = self.env["stock.quant"].search(
                [
                    ("lot_id", "=", lot_id),
                    ("location_id", "=", move.location_id.id),
                    ("product_id", "=", move.product_id.id),
                ],
                limit=1,
            )

            if not quant:
                return {
                    "success": False,
                    "message": _(
                        "Lot %(lot)s not found in source location %(location)s"
                    )
                    % {
                        "lot": lot_name,
                        "location": move.location_id.display_name,
                    },
                }

            # Calcular qty disponible en Python
            available_qty = quant.quantity - quant.reserved_quantity

            # Calcular cuánto ya se escaneo de este lote
            already_picked_from_lot = sum(
                picking.move_line_ids.filtered(
                    lambda ml: ml.lot_id.id == lot_id
                    and ml.product_id.id == move.product_id.id
                ).mapped("qty_picked")
            )

            total_needed = qty_to_add + already_picked_from_lot

            if available_qty < total_needed:
                lot = self.env["stock.lot"].browse(lot_id)
                return {
                    "success": False,
                    "message": _(
                        "Insufficient available quantity for "
                        "lot %(lot)s. Available: %(available)s, "
                        "Already picked: %(picked)s, Requesting: %(request)s"
                    )
                    % {
                        "lot": lot.name,
                        "available": available_qty,
                        "picked": already_picked_from_lot,
                        "request": qty_to_add,
                    },
                }

            move_line_vals["quant_id"] = quant.id

        move_line = (
            self.env["stock.move.line"]
            .with_context(move_line_pick_qty=True)
            .create(move_line_vals)
        )

        return {
            "success": True,
            "message": _("Lot %(lot)s added") % {"lot": move_line.lot_id.name},
            "move_line_id": move_line.id,
        }

    def _create_or_update_move_line_for_product(self, move, qty_to_add, picking):
        """
        Para productos SIN tracking.
        Crea o actualiza move_lines sin lote.
        """
        # Buscar move_line sin lote
        available_line = move.move_line_ids.filtered(lambda ml: not ml.lot_id)

        if available_line:
            new_qty = available_line[0].qty_picked + qty_to_add
            available_line[0].with_context(move_line_pick_qty=True).write(
                {"qty_picked": new_qty}
            )
            return {
                "success": True,
                "message": _("Quantity updated: %(qty)s") % {"qty": new_qty},
                "move_line_id": available_line[0].id,
            }

        # Crear nueva move_line
        move_line_vals = {
            "move_id": move.id,
            "product_id": move.product_id.id,
            "qty_picked": qty_to_add,
            "quantity": qty_to_add,
            "product_uom_id": move.product_uom.id,
            "location_id": move.location_id.id,
            "location_dest_id": move.location_dest_id.id,
            "picking_id": picking.id,
        }

        move_line = (
            self.env["stock.move.line"]
            .with_context(move_line_pick_qty=True)
            .create(move_line_vals)
        )

        return {
            "success": True,
            "message": _("Product quantity added: %(qty)s") % {"qty": qty_to_add},
            "move_line_id": move_line.id,
        }

    def _handle_product_scan(self, barcode_data, picking, context, target):
        """Handle product barcode scan"""
        context_update = {}
        # Guardar product_id en contexto TRANSITORIAMENTE (se filtrará al persistir)
        context_update["product_id"] = barcode_data["id"]
        context_update["product_name"] = barcode_data["name"]
        message = _("Product scanned: %s") % barcode_data["name"]

        move = picking.move_ids.filtered(
            lambda m: m.product_id.id == barcode_data["id"]
        )[:1]

        move_id = None
        quantity_to_add = 0

        if move:
            move_id = move.id
            # Only increment qty if tracking='none', otherwise wait for lot/serial
            quantity_to_add = self._should_increment_quantity(
                "product", move.product_id, context
            )

            # Persistir inmediatamente para productos sin tracking
            if quantity_to_add > 0 and move.product_id.tracking == "none":
                # VALIDATE BEFORE updating backend: check if would exceed demand
                picked_quantities = picking._compute_picked_quantities_from_move_lines()
                current_picked = picked_quantities.get(str(move.id), 0)
                would_exceed = (current_picked + quantity_to_add) > move.product_uom_qty

                if would_exceed and not self.allow_exceed_demand:
                    # Block completely - do not update backend or UI
                    return {
                        "success": False,
                        "message": _(
                            "Quantity exceeds demand for "
                            "product %(product)s (%(picked)s/%(demand)s)"
                        )
                        % {
                            "product": move.product_id.name,
                            "picked": current_picked + quantity_to_add,
                            "demand": move.product_uom_qty,
                        },
                    }

                # Update backend (either allowed to exceed, or not exceeding)
                product_result = self._create_or_update_move_line_for_product(
                    move, quantity_to_add, picking
                )
                if not product_result.get("success", True):
                    return {
                        "success": False,
                        "message": product_result.get(
                            "message", "Failed to update quantity"
                        ),
                    }

                # If exceeded but allowed, add warning to message
                if would_exceed and self.allow_exceed_demand:
                    message = _(
                        "⚠️ Product scanned: %(product)s "
                        "(EXCEEDS DEMAND: %(picked)s/%(demand)s)"
                    ) % {
                        "product": barcode_data["name"],
                        "picked": current_picked + quantity_to_add,
                        "demand": move.product_uom_qty,
                    }

        result = {
            "success": True,
            "message": message,
            "context_update": context_update,
        }
        if move_id:
            result["move_id"] = move_id
            result["quantity_to_add"] = quantity_to_add
        return result

    def _handle_location_scan(self, barcode_data, picking, context, target):
        """Handle location barcode scan (source or destination)"""
        if target.technical_name == "source_location":
            # Validar que coincide con la ubicación de origen del picking
            if picking.location_id.id != barcode_data["id"]:
                return {
                    "success": False,
                    "message": _(
                        "Scanned source location %(scanned)s doesn't "
                        "match picking source %(expected)s"
                    )
                    % {
                        "scanned": barcode_data["name"],
                        "expected": picking.location_id.display_name,
                    },
                }
            message = _("Source location verified: %s") % barcode_data["name"]
            # NO guardar en contexto, ya está en picking.location_id

        elif target.technical_name == "destination_location":
            # Actualizar picking (template para nuevas move_lines)
            picking.location_dest_id = barcode_data["id"]

            # Actualizar también todas las
            # move_lines existentes (con o sin qty_picked)
            if picking.move_line_ids:
                picking.move_line_ids.with_context(move_line_pick_qty=True).write(
                    {"location_dest_id": barcode_data["id"]}
                )

            message = _("Destination location: %s") % barcode_data["name"]
            # NO guardar en contexto

        return {
            "success": True,
            "message": message,
            "context_update": {},
        }

    def _handle_location_dest_scan(self, barcode_data, picking, context, target):
        """Handle location_dest barcode scan"""
        # Actualizar picking (template para nuevas move_lines)
        picking.location_dest_id = barcode_data["id"]

        # Actualizar también todas las move_lines existentes (con o sin qty_picked)
        if picking.move_line_ids:
            picking.move_line_ids.with_context(move_line_pick_qty=True).write(
                {"location_dest_id": barcode_data["id"]}
            )

        message = _("Destination location: %s") % barcode_data["name"]
        # NO guardar en contexto

        return {
            "success": True,
            "message": message,
            "context_update": {},
        }

    def _handle_package_scan(self, barcode_data, picking, context, target):
        """Handle package barcode scan"""
        # Escribir directo a move_lines activas
        # (con qty_picked y sin package ya asignado)
        lines_to_update = picking.move_line_ids.filtered(
            lambda ml: ml.qty_picked > 0 and not ml.result_package_id
        )
        if lines_to_update:
            lines_to_update.with_context(move_line_pick_qty=True).write(
                {"result_package_id": barcode_data["id"]}
            )

        message = _("Package scanned: %s") % barcode_data["name"]
        # NO guardar en contexto

        return {
            "success": True,
            "message": message,
            "context_update": {},
        }

    def _handle_lot_serial_scan(self, barcode_data, picking, context, target):
        """Handle lot/serial barcode scan - delegates to specific handlers"""
        # Get product from barcode data or context
        product_id = barcode_data.get("product_id") or context.get("product_id")
        if not product_id:
            return {
                "success": False,
                "message": _("Please scan product first before scanning lot/serial"),
            }

        product = self.env["product.product"].browse(product_id)

        # Validate that product requires tracking
        if product.tracking == "none":
            return {
                "success": False,
                "message": _("Product %(product)s doesn't require lot/serial tracking")
                % {"product": product.name},
            }

        # Validar contra move_lines reales, no contra contexto
        if product.tracking == "serial" and barcode_data["id"]:
            # Buscar si este serial ya fue escaneado en este picking
            already_scanned = picking.move_line_ids.filtered(
                lambda ml: ml.lot_id
                and ml.lot_id.id == barcode_data["id"]
                and ml.qty_picked >= 1
            )
            if already_scanned:
                return {
                    "success": False,
                    "message": _("Serial %(serial)s already used in this operation")
                    % {
                        "serial": barcode_data["name"],
                    },
                }

        # Create lot/serial if doesn't exist and allowed
        lot_id = barcode_data["id"]
        if not lot_id:
            if not self.allow_lot_sn_creation:
                return {
                    "success": False,
                    "message": _(
                        "Lot/Serial %(name)s not found and creation not allowed"
                    )
                    % {"name": barcode_data["name"]},
                }

            # Verificar si ya existe antes de crear
            existing_lot = self.env["stock.lot"].search(
                [
                    ("name", "=", barcode_data["name"]),
                    ("product_id", "=", product_id),
                    ("company_id", "in", [picking.company_id.id, False]),
                ],
                limit=1,
            )

            if existing_lot:
                # Ya existe, usar el existente
                lot_id = existing_lot.id
                barcode_data["id"] = lot_id
                barcode_data["record"] = existing_lot
            else:
                # Crear nuevo lot/serial
                lot = self.env["stock.lot"].create(
                    {
                        "name": barcode_data["name"],
                        "product_id": product_id,
                        "company_id": picking.company_id.id or self.env.company.id,
                    }
                )
                lot_id = lot.id
                barcode_data["id"] = lot_id
                barcode_data["record"] = lot
            barcode_data["product_id"] = product_id

        # Context update
        context_update = {
            "lot_id": lot_id,
            "lot_name": self.env["stock.lot"].browse(lot_id).name,
        }

        # If product wasn't in context, add it now (smart detection case)
        if "product_id" in barcode_data and barcode_data["product_id"]:
            # Agregar transitoriamente
            context_update["product_id"] = barcode_data["product_id"]
            context_update["product_name"] = product.name
            message = _(
                "Lot/Serial scanned: %(lot_name)s (Product: %(product_name)s)"
            ) % {"lot_name": barcode_data["name"], "product_name": product.name}
        else:
            message = _("Lot/Serial scanned: %s") % barcode_data["name"]

        move = picking.move_ids.filtered(lambda m: m.product_id.id == product_id)[:1]
        if not move:
            return {
                "success": True,
                "message": message,
                "context_update": context_update,
            }

        # Delegate to specific serial or lot handler
        if product.tracking == "serial":
            return self._process_serial_scan(
                move, lot_id, picking, context, barcode_data, context_update, message
            )
        else:  # tracking == "lot"
            return self._process_lot_scan(
                move, lot_id, picking, context, barcode_data, context_update, message
            )

    def _process_serial_scan(
        self, move, lot_id, picking, context, barcode_data, context_update, message
    ):
        """Process serial number scan"""
        # VALIDATE BEFORE updating backend: check if would exceed demand for serial
        picked_quantities = picking._compute_picked_quantities_from_move_lines()
        current_picked = picked_quantities.get(str(move.id), 0)
        would_exceed = (current_picked + 1.0) > move.product_uom_qty

        if would_exceed and not self.allow_exceed_demand:
            # Block completely - do not update backend or UI
            return {
                "success": False,
                "message": _(
                    "Quantity exceeds demand for "
                    "product %(product)s (%(picked)s/%(demand)s)"
                )
                % {
                    "product": move.product_id.name,
                    "picked": current_picked + 1.0,
                    "demand": move.product_uom_qty,
                },
            }

        # Para serials: crear move_line inmediatamente
        serial_result = self._create_or_update_move_line_for_serial(
            move, lot_id, picking, context
        )

        if not serial_result["success"]:
            return serial_result

        # Serial registrado exitosamente
        message = serial_result["message"]

        # If exceeded but allowed, add warning to message
        if would_exceed and self.allow_exceed_demand:
            message = _(
                "⚠️ Serial scanned: %(serial)s "
                "(EXCEEDS DEMAND: %(picked)s/%(demand)s)"
            ) % {
                "serial": barcode_data["name"],
                "picked": current_picked + 1.0,
                "demand": move.product_uom_qty,
            }

        return {
            "success": True,
            "message": message,
            "context_update": context_update,
            "move_id": move.id,
            "quantity_to_add": 1.0,
        }

    def _process_lot_scan(
        self, move, lot_id, picking, context, barcode_data, context_update, message
    ):
        """Process lot number scan"""
        # Para lotes: persistir inmediatamente como serials
        quantity_to_add = self._should_increment_quantity(
            "lot", move.product_id, context
        )

        if quantity_to_add > 0:
            # VALIDATE BEFORE updating backend: check if would exceed demand for lot
            picked_quantities = picking._compute_picked_quantities_from_move_lines()
            current_picked = picked_quantities.get(str(move.id), 0)
            would_exceed = (current_picked + quantity_to_add) > move.product_uom_qty

            if would_exceed and not self.allow_exceed_demand:
                # Block completely - do not update backend or UI
                return {
                    "success": False,
                    "message": _(
                        "Quantity exceeds demand for "
                        "product %(product)s (%(picked)s/%(demand)s)"
                    )
                    % {
                        "product": move.product_id.name,
                        "picked": current_picked + quantity_to_add,
                        "demand": move.product_uom_qty,
                    },
                }

            lot_result = self._create_or_update_move_line_for_lot(
                move,
                barcode_data["id"],
                quantity_to_add,
                picking,
                barcode_data["name"],
            )
            if lot_result["success"]:
                message = lot_result["message"]

                # If exceeded but allowed, add warning to message
                if would_exceed and self.allow_exceed_demand:
                    message = _(
                        "⚠️ Lot scanned: %(lot)s "
                        "(EXCEEDS DEMAND: %(picked)s/%(demand)s)"
                    ) % {
                        "lot": barcode_data["name"],
                        "picked": current_picked + quantity_to_add,
                        "demand": move.product_uom_qty,
                    }

        return {
            "success": True,
            "message": message,
            "context_update": context_update,
            "move_id": move.id,
            "quantity_to_add": quantity_to_add,
        }

    def _apply_barcode_to_picking(self, barcode_data, picking, context, target):
        """
        Apply scanned barcode to picking - Dispatcher pattern.
        Delegates to specialized handlers based on barcode type.
        """
        barcode_type = barcode_data["type"]

        # Dispatch table for barcode handlers
        handlers = {
            "product": self._handle_product_scan,
            "location": self._handle_location_scan,
            "location_dest": self._handle_location_dest_scan,
            "lot": self._handle_lot_serial_scan,
            "package": self._handle_package_scan,
        }

        handler = handlers.get(barcode_type)
        if not handler:
            return {
                "success": False,
                "message": _("Unknown barcode type: %s") % barcode_type,
            }

        # Call the appropriate handler
        result = handler(barcode_data, picking, context, target)

        # Clean internal tracking keys (not needed in result)
        if "context_update" in result:
            result["context_update"].pop("_tracking", None)
            result["context_update"].pop("_just_scanned", None)

        return result

    def _find_step_with_target(self, target_tech_name):
        """Find first cyclic step that has the specified target"""
        self.ensure_one()
        sequence_lines = self.target_scanning_sequence_ids.sorted("sequence")
        cyclic_steps = sequence_lines.filtered(lambda line: line.step_type == "cyclic")

        for step in cyclic_steps:
            if any(t.technical_name == target_tech_name for t in step.target_ids):
                return step
        return None

    def _all_moves_completed(self, picking, picked_quantities):
        """
        Verifica si todos los moves del picking están completos.
        Siempre recalcula desde move_lines (fuente de verdad).
        Nota: picked_quantities se mantiene como parámetro por
        compatibilidad pero se ignora.
        """
        # SIEMPRE recalcular desde BD para garantizar consistencia
        # Invalidar cache para asegurar que leemos datos frescos
        picking.move_ids.invalidate_recordset(["move_line_ids"])
        picking.move_ids.move_line_ids.invalidate_recordset(["qty_picked"])

        picked_quantities = picking._compute_picked_quantities_from_move_lines()

        for move in picking.move_ids:
            move_id_str = str(move.id)
            scanned_qty = picked_quantities.get(move_id_str, 0)

            if scanned_qty < move.product_uom_qty:
                return False

        return True

    def _clean_context_for_final(self, context):
        """
        Limpia product/lot del contexto al avanzar al step final.
        Solo mantiene estado esencial de sesión (scanned_serials).
        """
        cleaned = context.copy()
        # Limpiar IDs temporales de sesión
        cleaned.pop("product_id", None)
        cleaned.pop("lot_id", None)
        # scanned_serials se mantiene para evitar duplicados
        return cleaned

    def _determine_next_step(self, current_step, picking, context):
        """
        Determine next step based on current state - FLEXIBLE LOGIC.

        No rigid cycles. Decision flow:
        1. If on final step → End
        2. If all moves complete → Move to final step (if exists)
        3. If product with tracking in context → Ask for lot/serial
        4. Otherwise → Allow scanning any product
        """
        sequence_lines = self.target_scanning_sequence_ids.sorted("sequence")

        # 1. Final step means we're done
        if current_step.step_type == "final":
            return {
                "step": None,
                "instructions": _("Scanning sequence completed"),
                "applicable_targets": [],
                "context": context,
            }

        # 2. Check if all cyclic work is complete
        if current_step.step_type == "cyclic":
            picked_quantities = context.get("picked_quantities", {})

            # Usar método mejorado para detectar completitud
            if self._all_moves_completed(picking, picked_quantities):
                # All products scanned, move to final step if exists
                final_step = sequence_lines.filtered(
                    lambda line: line.step_type == "final"
                )
                if final_step:
                    # Limpiar contexto al avanzar a final
                    cleaned_context = self._clean_context_for_final(context)
                    return self._get_step_info(final_step[0], cleaned_context)
                else:
                    return {
                        "step": None,
                        "instructions": _("All products scanned"),
                        "applicable_targets": [],
                        "context": context,
                    }

            # 3. Still have work to do - decide based on context
            product_id = context.get("product_id")

            if product_id:
                product = self.env["product.product"].browse(product_id)

                # If product has tracking, we should be on lot/serial step
                if product.tracking in ("lot", "serial"):
                    lot_serial_step = self._find_step_with_target("lot")
                    if not lot_serial_step:
                        lot_serial_step = self._find_step_with_target("serial")

                    if lot_serial_step:
                        return self._get_step_info(lot_serial_step, context)

            # 4. Default: stay on product step (allows scanning any product)
            product_step = self._find_step_with_target("product")
            if product_step:
                return self._get_step_info(product_step, context)

            # Fallback: stay on current step
            return self._get_step_info(current_step, context)

        # For initial step, advance to first cyclic
        current_index = list(sequence_lines).index(current_step)
        if current_index + 1 < len(sequence_lines):
            next_step = sequence_lines[current_index + 1]
            return self._get_step_info(next_step, context)
        else:
            return {
                "step": None,
                "instructions": _("Scanning sequence completed"),
                "applicable_targets": [],
                "context": context,
            }

    def _get_step_info(self, step, context):
        applicable_targets = step.get_applicable_targets(context)
        instructions = self._generate_scan_instructions(
            step, context, applicable_targets
        )
        return {
            "step": step,
            "instructions": instructions,
            "applicable_targets": [
                {
                    "id": t.id,
                    "technical_name": t.technical_name,
                    "display_name": t.name,
                }
                for t in applicable_targets
            ],
            "context": context,  # Return the context used
        }

    def _generate_scan_instructions(self, step, context, applicable_targets):
        if not applicable_targets:
            return _("Continue scanning")

        target_tech_names = applicable_targets.mapped("technical_name")
        target_names = applicable_targets.mapped("name")

        # Get product info from context if available
        product_id = context.get("product_id")
        product_name = context.get("product_name")
        lot_id = context.get("lot_id")

        # If we have a product in context, get its tracking
        product_tracking = None
        if product_id:
            product = self.env["product.product"].browse(product_id)
            product_tracking = product.tracking

        # Special handling for lot/serial targets when product is known
        if len(target_tech_names) == 1:
            tech_name = target_tech_names[0]
            target_name = target_names[0]

            # Lot/Serial target with known product
            if tech_name in ("lot", "serial") and product_name:
                if product_tracking == "serial":
                    return _("Scan Serial Number for %(product)s") % {
                        "product": product_name
                    }
                elif product_tracking == "lot":
                    return _("Scan Lot for %(product)s") % {"product": product_name}
                else:
                    return _("Scan %(target)s for %(product)s") % {
                        "target": target_name,
                        "product": product_name,
                    }

            # Product target - indicate if it's start of new cycle
            elif tech_name == "product":
                if product_name and lot_id and product_tracking == "lot":
                    # Same lot can be used for multiple units
                    return _("Scan Product (or continue with same lot)")
                return _("Scan %(target)s") % {"target": target_name}

            # Other targets
            else:
                return _("Scan %(target)s") % {"target": target_name}

        # Multiple targets
        else:
            # If we have product with tracking and the step allows lot/serial,
            # prioritize showing what's needed next
            if (
                product_id
                and product_tracking in ("lot", "serial")
                and any(t in target_tech_names for t in ("lot", "serial"))
            ):
                # Product is scanned and needs lot/serial, show that instruction
                if product_tracking == "serial":
                    return _("Scan Serial Number for %(product)s") % {
                        "product": product_name
                    }
                elif product_tracking == "lot":
                    return _("Scan Lot for %(product)s") % {"product": product_name}

            # Default: show all available options
            instruction = _("Scan %(targets)s") % {
                "targets": _(" or ").join(target_names)
            }
            if product_name and any(t in target_tech_names for t in ("lot", "serial")):
                instruction += _(" for %(product)s") % {"product": product_name}
            return instruction

    def get_interface_config(self):
        self.ensure_one()
        method_name = f"get_interface_config_{self.profile_type}"

        if hasattr(self, method_name):
            return getattr(self, method_name)()
        else:
            return {"type": self.profile_type}

    def get_interface_config_picking(self):
        sequence_lines = self.target_scanning_sequence_ids.sorted("sequence")
        return {
            "type": "picking",
            "profile_id": self.id,
            "profile_name": self.name,
            "nomenclature_id": self.barcode_nomenclature_id.id,
            "is_gs1": self.barcode_nomenclature_id.is_gs1_nomenclature,
            "allow_lot_sn_creation": self.allow_lot_sn_creation,
            "scanning_sequence": [
                {
                    "id": line.id,
                    "sequence": line.sequence,
                    "name": line.name,
                    "step_type": line.step_type,
                    "targets": [
                        {
                            "id": t.id,
                            "technical_name": t.technical_name,
                            "display_name": t.name,
                            "description": t.description,
                        }
                        for t in line.target_ids
                    ],
                    "required": line.required,
                }
                for line in sequence_lines
            ],
            "has_initial_step": bool(
                sequence_lines.filtered(lambda line: line.step_type == "initial")
            ),
            "has_final_step": bool(
                sequence_lines.filtered(lambda line: line.step_type == "final")
            ),
            "cyclic_steps_count": len(
                sequence_lines.filtered(lambda line: line.step_type == "cyclic")
            ),
        }
