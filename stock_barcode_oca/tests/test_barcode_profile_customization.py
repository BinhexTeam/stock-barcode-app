"""Tests for customized barcode profiles with complex step sequences"""
from .test_common import BarcodeTestCommon


class TestBarcodeProfileCustomization(BarcodeTestCommon):
    """Test custom barcode profiles with non-standard step sequences"""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # Create stock for testing
        cls._create_initial_stock()

    @classmethod
    def _create_initial_stock(cls):
        """Create initial stock for products"""
        # Stock for products without tracking
        cls.env["stock.quant"]._update_available_quantity(
            cls.product_none_a, cls.location_stock, 100
        )
        cls.env["stock.quant"]._update_available_quantity(
            cls.product_none_b, cls.location_stock, 100
        )

        # Stock for products with lot tracking
        cls.env["stock.quant"]._update_available_quantity(
            cls.product_lot_a, cls.location_stock, 50, lot_id=cls.lot_a1
        )
        cls.env["stock.quant"]._update_available_quantity(
            cls.product_lot_a, cls.location_stock, 50, lot_id=cls.lot_a2
        )

        # Stock for products with serial tracking
        cls.env["stock.quant"]._update_available_quantity(
            cls.product_serial_a, cls.location_stock, 1, lot_id=cls.serial_a1
        )
        cls.env["stock.quant"]._update_available_quantity(
            cls.product_serial_a, cls.location_stock, 1, lot_id=cls.serial_a2
        )
        cls.env["stock.quant"]._update_available_quantity(
            cls.product_serial_a, cls.location_stock, 1, lot_id=cls.serial_a3
        )

    def test_01_profile_separate_lot_and_serial_steps(self):
        """Custom Profile: Separate steps for lot and serial scanning

        This may seem illogical (why separate lot and serial if product defines it?)
        but the profile should respect the configured sequence.
        """
        # Create custom profile with explicit lot and serial steps
        profile = self.env["stock.barcode.app.profile"].create(
            {
                "name": "Custom Separate Lot/Serial Profile",
                "profile_type": "picking",
                "barcode_nomenclature_id": self.nomenclature.id,
                "allow_lot_sn_creation": False,
            }
        )

        # Step 1: Scan product (cyclic)
        self.env["stock.barcode.app.profile.target.line"].create(
            {
                "profile_id": profile.id,
                "name": "Step 1: Product",
                "sequence": 10,
                "step_type": "cyclic",
                "required": False,
                "target_ids": [(6, 0, [self.target_product.id])],
            }
        )

        # Step 2: Scan LOT ONLY (cyclic)
        self.env["stock.barcode.app.profile.target.line"].create(
            {
                "profile_id": profile.id,
                "name": "Step 2: Lot Number",
                "sequence": 20,
                "step_type": "cyclic",
                "required": False,
                "target_ids": [(6, 0, [self.target_lot.id])],
            }
        )

        # Step 3: Scan SERIAL ONLY (cyclic) - illogical but should work
        self.env["stock.barcode.app.profile.target.line"].create(
            {
                "profile_id": profile.id,
                "name": "Step 3: Serial Number",
                "sequence": 30,
                "step_type": "cyclic",
                "required": False,
                "target_ids": [
                    (6, 0, [self.target_lot.id])
                ],  # Same target but different step
            }
        )

        # Step 4: Final destination
        self.env["stock.barcode.app.profile.target.line"].create(
            {
                "profile_id": profile.id,
                "name": "Step 4: Destination",
                "sequence": 40,
                "step_type": "final",
                "required": True,
                "target_ids": [(6, 0, [self.target_dest_location.id])],
            }
        )

        # Create picking type with this profile
        picking_type = self.env["stock.picking.type"].create(
            {
                "name": "Custom Separate Lot/Serial",
                "code": "internal",
                "sequence_code": "CUSTOM-SEP",
                "barcode_profile_id": profile.id,
                "default_location_src_id": self.location_stock.id,
                "default_location_dest_id": self.location_shelf_a.id,
            }
        )

        # Create picking with both lot and serial products
        picking = self.env["stock.picking"].create(
            {
                "picking_type_id": picking_type.id,
                "location_id": self.location_stock.id,
                "location_dest_id": self.location_shelf_a.id,
            }
        )

        self._create_move(picking, self.product_lot_a, 2)
        self._create_move(picking, self.product_serial_a, 2)
        picking.action_confirm()

        # Test scanning: The profile should follow the sequence even if illogical
        # Lot product
        result = picking.process_scanned_barcode("PROD-LOT-A")
        self._assert_scan_success(result)
        result = picking.process_scanned_barcode("LOT-A-001")
        self._assert_scan_success(result)  # Should work in "lot only" step

        result = picking.process_scanned_barcode("PROD-LOT-A")
        self._assert_scan_success(result)
        result = picking.process_scanned_barcode("LOT-A-001")
        self._assert_scan_success(result)

        # Serial product
        result = picking.process_scanned_barcode("PROD-SERIAL-A")
        self._assert_scan_success(result)
        result = picking.process_scanned_barcode("SN-A-001")
        self._assert_scan_success(result)  # Should work even though "serial" step

        result = picking.process_scanned_barcode("PROD-SERIAL-A")
        self._assert_scan_success(result)
        result = picking.process_scanned_barcode("SN-A-002")
        self._assert_scan_success(result)

        self._assert_step_is_final(picking)

    def test_02_profile_location_in_middle_of_sequence(self):
        """Custom Profile: Scan location in the middle of product scanning

        This is illogical (why scan destination before finishing products?)
        but the profile should enforce this sequence.
        """
        # Create custom profile
        profile = self.env["stock.barcode.app.profile"].create(
            {
                "name": "Custom Location-Mid-Sequence Profile",
                "profile_type": "picking",
                "barcode_nomenclature_id": self.nomenclature.id,
                "allow_lot_sn_creation": False,
            }
        )

        # Step 1: Scan some products (cyclic)
        self.env["stock.barcode.app.profile.target.line"].create(
            {
                "profile_id": profile.id,
                "name": "Step 1: First Product Batch",
                "sequence": 10,
                "step_type": "cyclic",
                "required": False,
                "target_ids": [(6, 0, [self.target_product.id])],
            }
        )

        # Step 2: Scan destination (intermediate, not final!)
        self.env["stock.barcode.app.profile.target.line"].create(
            {
                "profile_id": profile.id,
                "name": "Step 2: Intermediate Destination Scan",
                "sequence": 20,
                "step_type": "cyclic",  # Illogical but allowed
                "required": True,
                "target_ids": [(6, 0, [self.target_dest_location.id])],
            }
        )

        # Step 3: Scan more products (cyclic)
        self.env["stock.barcode.app.profile.target.line"].create(
            {
                "profile_id": profile.id,
                "name": "Step 3: Second Product Batch",
                "sequence": 30,
                "step_type": "cyclic",
                "required": False,
                "target_ids": [(6, 0, [self.target_product.id])],
            }
        )

        # Step 4: Final confirmation step
        self.env["stock.barcode.app.profile.target.line"].create(
            {
                "profile_id": profile.id,
                "name": "Step 4: Final Confirmation",
                "sequence": 40,
                "step_type": "final",
                "required": True,
                "target_ids": [(6, 0, [self.target_dest_location.id])],
            }
        )

        # Create picking type
        picking_type = self.env["stock.picking.type"].create(
            {
                "name": "Custom Location-Mid-Sequence",
                "code": "internal",
                "sequence_code": "CUSTOM-MID",
                "barcode_profile_id": profile.id,
                "default_location_src_id": self.location_stock.id,
                "default_location_dest_id": self.location_shelf_a.id,
            }
        )

        # Create picking
        picking = self.env["stock.picking"].create(
            {
                "picking_type_id": picking_type.id,
                "location_id": self.location_stock.id,
                "location_dest_id": self.location_shelf_a.id,
            }
        )

        self._create_move(picking, self.product_none_a, 2)
        self._create_move(picking, self.product_none_b, 2)
        picking.action_confirm()

        # Scan first product (Step 1)
        result = picking.process_scanned_barcode("PROD-NONE-A")
        self._assert_scan_success(result)
        result = picking.process_scanned_barcode("PROD-NONE-A")
        self._assert_scan_success(result)
        self._assert_quantity_picked(picking, self.product_none_a, 2)

        # Now must scan destination (Step 2) - this is required before continuing
        # Trying to scan more products should fail if destination not scanned
        state = picking._get_scan_state()
        current_step = self.env["stock.barcode.app.profile.target.line"].browse(
            state.get("current_step_id")
        )

        # The current step should be the destination step
        self.assertIn(
            self.target_dest_location.id,
            current_step.target_ids.ids,
            "Profile should enforce destination scan in middle of sequence",
        )

        # Scan destination as required by profile
        result = picking.process_scanned_barcode("LOC-SHELF-A")
        self._assert_scan_success(result, "destination")

        # Now can continue with second product (Step 3)
        result = picking.process_scanned_barcode("PROD-NONE-B")
        self._assert_scan_success(result)
        result = picking.process_scanned_barcode("PROD-NONE-B")
        self._assert_scan_success(result)
        self._assert_quantity_picked(picking, self.product_none_b, 2)

        # Final step
        self._assert_step_is_final(picking)
        result = picking.process_scanned_barcode("LOC-SHELF-A")
        self._assert_scan_success(result)

    def test_03_profile_multiple_initial_steps(self):
        """Custom Profile: Multiple initial steps that must be scanned first

        Profile requires scanning source, destination, and package before products.
        This enforces a strict upfront data collection sequence.
        """
        # Create custom profile
        profile = self.env["stock.barcode.app.profile"].create(
            {
                "name": "Custom Multi-Initial-Steps Profile",
                "profile_type": "picking",
                "barcode_nomenclature_id": self.nomenclature.id,
                "allow_lot_sn_creation": False,
            }
        )

        # Step 1: Scan source location (initial)
        self.env["stock.barcode.app.profile.target.line"].create(
            {
                "profile_id": profile.id,
                "name": "Step 1: Source Location",
                "sequence": 10,
                "step_type": "initial",
                "required": True,
                "target_ids": [(6, 0, [self.target_source_location.id])],
            }
        )

        # Step 2: Scan destination location (initial)
        self.env["stock.barcode.app.profile.target.line"].create(
            {
                "profile_id": profile.id,
                "name": "Step 2: Destination Location",
                "sequence": 20,
                "step_type": "initial",
                "required": True,
                "target_ids": [(6, 0, [self.target_dest_location.id])],
            }
        )

        # Step 3: Scan package (initial)
        self.env["stock.barcode.app.profile.target.line"].create(
            {
                "profile_id": profile.id,
                "name": "Step 3: Package ID",
                "sequence": 30,
                "step_type": "initial",
                "required": False,  # Optional package
                "target_ids": [(6, 0, [self.target_package.id])],
            }
        )

        # Step 4: Scan products (cyclic)
        self.env["stock.barcode.app.profile.target.line"].create(
            {
                "profile_id": profile.id,
                "name": "Step 4: Products",
                "sequence": 40,
                "step_type": "cyclic",
                "required": False,
                "target_ids": [(6, 0, [self.target_product.id])],
            }
        )

        # Step 5: Final confirmation
        self.env["stock.barcode.app.profile.target.line"].create(
            {
                "profile_id": profile.id,
                "name": "Step 5: Confirm",
                "sequence": 50,
                "step_type": "final",
                "required": True,
                "target_ids": [(6, 0, [self.target_dest_location.id])],
            }
        )

        # Create picking type
        picking_type = self.env["stock.picking.type"].create(
            {
                "name": "Custom Multi-Initial-Steps",
                "code": "internal",
                "sequence_code": "CUSTOM-MULTI",
                "barcode_profile_id": profile.id,
                "default_location_src_id": self.location_stock.id,
                "default_location_dest_id": self.location_shelf_a.id,
            }
        )

        # Create picking
        picking = self.env["stock.picking"].create(
            {
                "picking_type_id": picking_type.id,
                "location_id": self.location_stock.id,
                "location_dest_id": self.location_shelf_a.id,
            }
        )

        self._create_move(picking, self.product_none_a, 2)
        picking.action_confirm()

        # Get initial state
        state = picking._get_scan_state()
        current_step = self.env["stock.barcode.app.profile.target.line"].browse(
            state.get("current_step_id")
        )

        # Should be on first initial step (source location)
        self.assertEqual(current_step.step_type, "initial")
        self.assertIn(self.target_source_location.id, current_step.target_ids.ids)

        # Scan source location
        result = picking.process_scanned_barcode("LOC-STOCK-001")
        self._assert_scan_success(result, "source")

        # Should now be on second initial step (destination location)
        state = picking._get_scan_state()
        current_step = self.env["stock.barcode.app.profile.target.line"].browse(
            state.get("current_step_id")
        )
        self.assertEqual(current_step.step_type, "initial")
        self.assertIn(self.target_dest_location.id, current_step.target_ids.ids)

        # Scan destination location
        result = picking.process_scanned_barcode("LOC-SHELF-A")
        self._assert_scan_success(result, "destination")

        # Should now be on third initial step (package, optional)
        # We'll skip it and go directly to product scanning
        state = picking._get_scan_state()
        current_step = self.env["stock.barcode.app.profile.target.line"].browse(
            state.get("current_step_id")
        )

        # Current step should allow product scanning (cyclic step)
        # Since package step is optional, it should move to cyclic
        self.assertIn(
            current_step.step_type,
            ["initial", "cyclic"],
            "Should be on initial (package) or cyclic (product) step",
        )

        # Scan products
        result = picking.process_scanned_barcode("PROD-NONE-A")
        self._assert_scan_success(result)
        result = picking.process_scanned_barcode("PROD-NONE-A")
        self._assert_scan_success(result)
        self._assert_quantity_picked(picking, self.product_none_a, 2)

        # Should be on final step
        self._assert_step_is_final(picking)

    def test_04_profile_very_granular_lot_steps(self):
        """Custom Profile: Extremely granular - separate step for each scan

        Forces: Product → Lot → Product → Lot for each unit
        This enforces strict alternation even for same product/lot combinations.
        """
        # Create custom profile
        profile = self.env["stock.barcode.app.profile"].create(
            {
                "name": "Custom Granular Lot Steps Profile",
                "profile_type": "picking",
                "barcode_nomenclature_id": self.nomenclature.id,
                "allow_lot_sn_creation": False,
            }
        )

        # Step 1: Scan product ONLY (cyclic)
        self.env["stock.barcode.app.profile.target.line"].create(
            {
                "profile_id": profile.id,
                "name": "Step 1: Product Only",
                "sequence": 10,
                "step_type": "cyclic",
                "required": False,
                "target_ids": [(6, 0, [self.target_product.id])],
            }
        )

        # Step 2: Scan lot ONLY (cyclic)
        self.env["stock.barcode.app.profile.target.line"].create(
            {
                "profile_id": profile.id,
                "name": "Step 2: Lot Only",
                "sequence": 20,
                "step_type": "cyclic",
                "required": False,
                "target_ids": [(6, 0, [self.target_lot.id])],
            }
        )

        # Step 3: Final
        self.env["stock.barcode.app.profile.target.line"].create(
            {
                "profile_id": profile.id,
                "name": "Step 3: Final",
                "sequence": 30,
                "step_type": "final",
                "required": True,
                "target_ids": [(6, 0, [self.target_dest_location.id])],
            }
        )

        # Create picking type
        picking_type = self.env["stock.picking.type"].create(
            {
                "name": "Custom Granular Lot Steps",
                "code": "internal",
                "sequence_code": "CUSTOM-GRAN",
                "barcode_profile_id": profile.id,
                "default_location_src_id": self.location_stock.id,
                "default_location_dest_id": self.location_shelf_a.id,
            }
        )

        # Create picking
        picking = self.env["stock.picking"].create(
            {
                "picking_type_id": picking_type.id,
                "location_id": self.location_stock.id,
                "location_dest_id": self.location_shelf_a.id,
            }
        )

        self._create_move(picking, self.product_lot_a, 3)
        picking.action_confirm()

        # Test strict alternation: Product → Lot → Product → Lot → Product → Lot
        # First unit
        result = picking.process_scanned_barcode("PROD-LOT-A")
        self._assert_scan_success(result)
        result = picking.process_scanned_barcode("LOT-A-001")
        self._assert_scan_success(result)
        self._assert_quantity_picked(picking, self.product_lot_a, 1)

        # Second unit (same lot)
        result = picking.process_scanned_barcode("PROD-LOT-A")
        self._assert_scan_success(result)
        result = picking.process_scanned_barcode("LOT-A-001")
        self._assert_scan_success(result)
        self._assert_quantity_picked(picking, self.product_lot_a, 2)

        # Third unit (same lot)
        result = picking.process_scanned_barcode("PROD-LOT-A")
        self._assert_scan_success(result)
        result = picking.process_scanned_barcode("LOT-A-001")
        self._assert_scan_success(result)
        self._assert_quantity_picked(picking, self.product_lot_a, 3)

        # Should be on final step
        self._assert_step_is_final(picking)
