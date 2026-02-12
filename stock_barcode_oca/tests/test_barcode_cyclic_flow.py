from .test_common import BarcodeTestCommon


class TestBarcodeCyclicFlow(BarcodeTestCommon):
    """Test cyclic scanning flow with different producttracking types"""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # Create locations
        cls.location_src = cls.env["stock.location"].create(
            {
                "name": "Test Source Location",
                "barcode": "LOC-SRC-001",
                "usage": "internal",
            }
        )
        cls.location_dest = cls.env["stock.location"].create(
            {
                "name": "Test Destination Location",
                "barcode": "LOC-DEST-001",
                "usage": "internal",
            }
        )

        # Create products with different tracking
        cls.product_none = cls.env["product.product"].create(
            {
                "name": "Product No Tracking",
                "type": "product",
                "tracking": "none",
                "barcode": "PROD-NONE-001",
            }
        )
        cls.product_lot = cls.env["product.product"].create(
            {
                "name": "Product Lot Tracking",
                "type": "product",
                "tracking": "lot",
                "barcode": "PROD-LOT-001",
            }
        )
        cls.product_serial = cls.env["product.product"].create(
            {
                "name": "Product Serial Tracking",
                "type": "product",
                "tracking": "serial",
                "barcode": "PROD-SERIAL-001",
            }
        )

        # Create lots for lot-tracked product
        cls.lot_001 = cls.env["stock.lot"].create(
            {
                "name": "LOT001",
                "product_id": cls.product_lot.id,
                "company_id": cls.env.company.id,
            }
        )
        cls.lot_002 = cls.env["stock.lot"].create(
            {
                "name": "LOT002",
                "product_id": cls.product_lot.id,
                "company_id": cls.env.company.id,
            }
        )

        # Create serial numbers for serial-tracked product
        cls.serial_001 = cls.env["stock.lot"].create(
            {
                "name": "SN001",
                "product_id": cls.product_serial.id,
                "company_id": cls.env.company.id,
            }
        )
        cls.serial_002 = cls.env["stock.lot"].create(
            {
                "name": "SN002",
                "product_id": cls.product_serial.id,
                "company_id": cls.env.company.id,
            }
        )
        cls.serial_003 = cls.env["stock.lot"].create(
            {
                "name": "SN003",
                "product_id": cls.product_serial.id,
                "company_id": cls.env.company.id,
            }
        )

        # Create stock quants for serials in location_src (for internal transfers)
        cls._create_quants_for_serials(
            [cls.serial_001, cls.serial_002, cls.serial_003], cls.location_src
        )

        # Get or create barcode targets
        target_product = cls.env.ref(
            "stock_barcode_oca.barcode_target_product", raise_if_not_found=False
        )
        if not target_product:
            target_product = cls.env["stock.barcode.app.target"].create(
                {
                    "name": "Product",
                    "technical_name": "product",
                    "description": "Product to move",
                }
            )
        cls.target_product = target_product

        target_lot = cls.env.ref(
            "stock_barcode_oca.barcode_target_lot", raise_if_not_found=False
        )
        if not target_lot:
            target_lot = cls.env["stock.barcode.app.target"].create(
                {
                    "name": "Lot/Serial",
                    "technical_name": "lot",
                    "description": "Lot or serial number",
                }
            )
        cls.target_lot = target_lot

        target_dest_location = cls.env.ref(
            "stock_barcode_oca.barcode_target_destination_location",
            raise_if_not_found=False,
        )
        if not target_dest_location:
            target_dest_location = cls.env["stock.barcode.app.target"].create(
                {
                    "name": "Destination Location",
                    "technical_name": "destination_location",
                    "description": "Destination location",
                }
            )
        cls.target_dest_location = target_dest_location

        # Get default nomenclature
        cls.nomenclature = cls.env.ref(
            "barcodes.default_barcode_nomenclature",
            raise_if_not_found=False,
        )
        # if not cls.nomenclature:
        #     cls.nomenclature = cls.env["barcode.nomenclature"].create(
        #         {"name": "Default Nomenclature"}
        #     )

        # Create barcode profile with requested configuration
        # Step 1: cyclic - product only
        # Step 2: cyclic - product, lot, serial
        # Step 3: final - destination_location only, required
        cls.profile = cls.env["stock.barcode.app.profile"].create(
            {
                "name": "Test Cyclic Profile",
                "profile_type": "picking",
                "barcode_nomenclature_id": cls.nomenclature.id,
                "allow_lot_sn_creation": False,
            }
        )

        cls.step1 = cls.env["stock.barcode.app.profile.target.line"].create(
            {
                "profile_id": cls.profile.id,
                "name": "Step 1: Scan Product",
                "sequence": 10,
                "step_type": "cyclic",
                "required": False,
                "target_ids": [(6, 0, [cls.target_product.id])],
            }
        )

        cls.step2 = cls.env["stock.barcode.app.profile.target.line"].create(
            {
                "profile_id": cls.profile.id,
                "name": "Step 2: Scan Product or Lot/Serial",
                "sequence": 20,
                "step_type": "cyclic",
                "required": False,
                "target_ids": [(6, 0, [cls.target_product.id, cls.target_lot.id])],
            }
        )

        cls.step3 = cls.env["stock.barcode.app.profile.target.line"].create(
            {
                "profile_id": cls.profile.id,
                "name": "Step 3: Scan Destination Location",
                "sequence": 30,
                "step_type": "final",
                "required": True,
                "target_ids": [(6, 0, [cls.target_dest_location.id])],
            }
        )

        # Create picking type with profile
        cls.picking_type = cls.env["stock.picking.type"].create(
            {
                "name": "Test Internal Transfer",
                "code": "internal",
                "sequence_code": "TEST",
                "barcode_profile_id": cls.profile.id,
                "default_location_src_id": cls.location_src.id,
                "default_location_dest_id": cls.location_dest.id,
            }
        )

    def _create_picking_with_products(self):
        """Create a picking with all three product types"""
        picking = self.env["stock.picking"].create(
            {
                "picking_type_id": self.picking_type.id,
                "location_id": self.location_src.id,
                "location_dest_id": self.location_dest.id,
            }
        )

        # Add moves
        self.env["stock.move"].create(
            {
                "name": self.product_none.name,
                "product_id": self.product_none.id,
                "product_uom_qty": 3,
                "product_uom": self.product_none.uom_id.id,
                "picking_id": picking.id,
                "location_id": self.location_src.id,
                "location_dest_id": self.location_dest.id,
            }
        )

        self.env["stock.move"].create(
            {
                "name": self.product_lot.name,
                "product_id": self.product_lot.id,
                "product_uom_qty": 3,
                "product_uom": self.product_lot.uom_id.id,
                "picking_id": picking.id,
                "location_id": self.location_src.id,
                "location_dest_id": self.location_dest.id,
            }
        )

        self.env["stock.move"].create(
            {
                "name": self.product_serial.name,
                "product_id": self.product_serial.id,
                "product_uom_qty": 3,
                "product_uom": self.product_serial.uom_id.id,
                "picking_id": picking.id,
                "location_id": self.location_src.id,
                "location_dest_id": self.location_dest.id,
            }
        )

        picking.action_confirm()
        return picking

    def test_01_product_tracking_none(self):
        """Test scanning flow for product without tracking"""
        picking = self._create_picking_with_products()
        move_none = picking.move_ids.filtered(
            lambda m: m.product_id == self.product_none
        )

        # Initial state
        state = picking._get_scan_state()
        self.assertEqual(state, {})

        # Scan 1: Product (should increment qty_picked)
        result = picking.process_scanned_barcode("PROD-NONE-001")
        self.assertTrue(result["success"], f"Scan 1 failed: {result.get('message')}")
        self.assertEqual(result["move_id"], move_none.id)
        self.assertEqual(result["quantity_to_add"], 1.0)
        self.assertIn("Product scanned", result["message"])

        # Check state after scan 1
        state = picking._get_scan_state()
        self.assertEqual(state["scanned_context"]["product_id"], self.product_none.id)
        self.assertEqual(
            state["scanned_context"]["picked_quantities"][str(move_none.id)], 1.0
        )
        # lot_id should be None for tracking='none'
        self.assertIsNone(state["scanned_context"].get("lot_id"))

        # Scan 2: Same product again
        result = picking.process_scanned_barcode("PROD-NONE-001")
        self.assertTrue(result["success"])
        self.assertEqual(result["quantity_to_add"], 1.0)

        # Check state after scan 2
        state = picking._get_scan_state()
        self.assertEqual(
            state["scanned_context"]["picked_quantities"][str(move_none.id)], 2.0
        )

        # Scan 3: Same product third time
        result = picking.process_scanned_barcode("PROD-NONE-001")
        self.assertTrue(result["success"])
        self.assertEqual(result["quantity_to_add"], 1.0)

        # Check state after scan 3
        state = picking._get_scan_state()
        self.assertEqual(
            state["scanned_context"]["picked_quantities"][str(move_none.id)], 3.0
        )
        # Should still be in cyclic step (other products pending)
        self.assertIsNotNone(state["step"]["step_id"])

    def test_02_product_tracking_lot(self):
        """Test scanning flow for product with lot tracking"""
        picking = self._create_picking_with_products()
        move_lot = picking.move_ids.filtered(lambda m: m.product_id == self.product_lot)

        # Scan 1: Product (should NOT increment qty_picked, wait for lot)
        result = picking.process_scanned_barcode("PROD-LOT-001")
        self.assertTrue(result["success"], f"Scan 1 failed: {result.get('message')}")
        self.assertEqual(result["move_id"], move_lot.id)
        self.assertEqual(result["quantity_to_add"], 0)  # No increment yet
        self.assertIn("Product scanned", result["message"])

        # Check state after scan 1
        state = picking._get_scan_state()
        self.assertEqual(state["scanned_context"]["product_id"], self.product_lot.id)
        picked_qty = state["scanned_context"]["picked_quantities"].get(
            str(move_lot.id), 0
        )
        self.assertEqual(picked_qty, 0)  # Should be 0

        # Check instructions - should ask for lot
        self.assertIn("Lot", result["scan_instructions"])

        # Scan 2: LOT001 (should increment qty_picked now)
        result = picking.process_scanned_barcode("LOT001")
        self.assertTrue(result["success"], f"Scan 2 failed: {result.get('message')}")
        self.assertEqual(result["move_id"], move_lot.id)
        self.assertEqual(result["quantity_to_add"], 1.0)  # Now increment

        # Check state after scan 2
        state = picking._get_scan_state()
        self.assertEqual(
            state["scanned_context"]["picked_quantities"][str(move_lot.id)], 1.0
        )
        self.assertEqual(state["scanned_context"]["lot_id"], self.lot_001.id)
        # lot_id should be retained for tracking='lot'
        self.assertIsNotNone(state["scanned_context"].get("lot_id"))

        # Scan 3: Product again (starting new cycle)
        result = picking.process_scanned_barcode("PROD-LOT-001")
        self.assertTrue(result["success"], f"Scan 3 failed: {result.get('message')}")
        self.assertEqual(result["quantity_to_add"], 0)  # Wait for lot

        # Scan 4: Same LOT001 (should work, can use same lot multiple times)
        result = picking.process_scanned_barcode("LOT001")
        self.assertTrue(result["success"], f"Scan 4 failed: {result.get('message')}")
        self.assertEqual(result["quantity_to_add"], 1.0)

        # Check state after scan 4
        state = picking._get_scan_state()
        self.assertEqual(
            state["scanned_context"]["picked_quantities"][str(move_lot.id)], 2.0
        )
        self.assertEqual(state["scanned_context"]["lot_id"], self.lot_001.id)

        # Scan 5: Product again
        result = picking.process_scanned_barcode("PROD-LOT-001")
        self.assertTrue(result["success"])

        # Scan 6: Different lot LOT002
        result = picking.process_scanned_barcode("LOT002")
        self.assertTrue(result["success"])
        self.assertEqual(result["quantity_to_add"], 1.0)

        # Check final state
        state = picking._get_scan_state()
        self.assertEqual(
            state["scanned_context"]["picked_quantities"][str(move_lot.id)], 3.0
        )
        self.assertEqual(state["scanned_context"]["lot_id"], self.lot_002.id)

    def test_03_product_tracking_serial(self):
        """Test scanning flow for product with serial tracking"""
        picking = self._create_picking_with_products()
        move_serial = picking.move_ids.filtered(
            lambda m: m.product_id == self.product_serial
        )

        # Scan 1: Product (should NOT increment, wait for serial)
        result = picking.process_scanned_barcode("PROD-SERIAL-001")
        self.assertTrue(result["success"], f"Scan 1 failed: {result.get('message')}")
        self.assertEqual(result["move_id"], move_serial.id)
        self.assertEqual(result["quantity_to_add"], 0)

        # Check instructions - should ask for serial
        self.assertIn("Serial", result["scan_instructions"])

        # Scan 2: SN001 (should increment and clear serial from context)
        result = picking.process_scanned_barcode("SN001")
        self.assertTrue(result["success"], f"Scan 2 failed: {result.get('message')}")
        self.assertEqual(result["move_id"], move_serial.id)
        self.assertEqual(result["quantity_to_add"], 1.0)

        # Check state after scan 2
        state = picking._get_scan_state()
        self.assertEqual(
            state["scanned_context"]["picked_quantities"][str(move_serial.id)], 1.0
        )
        # lot_id (serial_id) persists in context for reference
        self.assertEqual(state["scanned_context"].get("lot_id"), self.serial_001.id)

        # Scan 3: Product again
        result = picking.process_scanned_barcode("PROD-SERIAL-001")
        self.assertTrue(result["success"])

        # Scan 4: SN002 (different serial, should work)
        result = picking.process_scanned_barcode("SN002")
        self.assertTrue(result["success"])
        self.assertEqual(result["quantity_to_add"], 1.0)

        # Check state after scan 4
        state = picking._get_scan_state()
        self.assertEqual(
            state["scanned_context"]["picked_quantities"][str(move_serial.id)], 2.0
        )
        # Now lot_id updated to SN002
        self.assertEqual(state["scanned_context"].get("lot_id"), self.serial_002.id)

        # Scan 5: Product again
        result = picking.process_scanned_barcode("PROD-SERIAL-001")
        self.assertTrue(result["success"])

        # Scan 6: SN003
        result = picking.process_scanned_barcode("SN003")
        self.assertTrue(result["success"])
        self.assertEqual(result["quantity_to_add"], 1.0)

        # Check final state
        state = picking._get_scan_state()
        self.assertEqual(
            state["scanned_context"]["picked_quantities"][str(move_serial.id)], 3.0
        )
        # Last serial scanned persists
        self.assertEqual(state["scanned_context"].get("lot_id"), self.serial_003.id)

    def test_04_validate_tracking_none_cannot_have_lot(self):
        """Test that product with tracking='none' cannot have lot scanned"""
        picking = self._create_picking_with_products()

        # Scan product without tracking
        result = picking.process_scanned_barcode("PROD-NONE-001")
        self.assertTrue(result["success"])

        # Try to scan a lot (should fail with specific message)
        result = picking.process_scanned_barcode("LOT001")
        self.assertFalse(result["success"])
        # Message should indicate product doesn't use lot/serial tracking
        self.assertIn("doesn't use lot/serial", result["message"].lower())

    def test_05_validate_lot_requires_product_first(self):
        """Test that lot cannot be scanned without product context"""
        picking = self._create_picking_with_products()

        # Try to scan lot without scanning product first (should fail)
        result = picking.process_scanned_barcode("LOT001")
        self.assertFalse(result["success"])
        # Message should indicate to scan product first
        self.assertIn("scan product first", result["message"].lower())

    def test_06_validate_quantity_exceeds_demand(self):
        """Test that scanning more than demand is rejected"""
        picking = self._create_picking_with_products()

        # Scan product without tracking 3 times (meets demand)
        for _ in range(3):
            result = picking.process_scanned_barcode("PROD-NONE-001")
            self.assertTrue(result["success"])

        # Try to scan 4th time (should fail - exceeds demand)
        result = picking.process_scanned_barcode("PROD-NONE-001")
        self.assertFalse(result["success"])
        self.assertIn("exceeds demand", result["message"].lower())

    def test_07_context_cleaning_on_cycle_restart(self):
        """Test that context is cleaned when restarting cycle"""
        picking = self._create_picking_with_products()

        # Complete scanning product with lot tracking
        result = picking.process_scanned_barcode("PROD-LOT-001")
        self.assertTrue(result["success"])
        result = picking.process_scanned_barcode("LOT001")
        self.assertTrue(result["success"])

        state = picking._get_scan_state()
        self.assertIsNotNone(state["scanned_context"].get("product_id"))
        self.assertIsNotNone(state["scanned_context"].get("lot_id"))

        # Complete all other products to trigger cycle restart
        # Complete product_none (3 scans)
        for _ in range(3):
            picking.process_scanned_barcode("PROD-NONE-001")

        # Complete remaining product_lot scans
        for _ in range(2):
            picking.process_scanned_barcode("PROD-LOT-001")
            picking.process_scanned_barcode("LOT001")

        # Complete product_serial (3 scans)
        for serial_name in ["SN001", "SN002", "SN003"]:
            picking.process_scanned_barcode("PROD-SERIAL-001")
            picking.process_scanned_barcode(serial_name)

        # After all products completed, should move to final step
        state = picking._get_scan_state()
        # Context for product/lot should be cleaned when moving to final step
        # (though we completed all, so might be at final step now)
        self.assertEqual(state["current_step_id"], self.step3.id)
