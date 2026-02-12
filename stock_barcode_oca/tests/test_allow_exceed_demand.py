from .test_common import BarcodeTestCommon


class TestAllowExceedDemand(BarcodeTestCommon):
    """Test the allow_exceed_demand feature"""

    def test_01_exceed_demand_not_allowed_product_no_tracking(self):
        """
        Test that exceeding demand is blocked when
        allow_exceed_demand=False for products without tracking
        """
        # Create profile with allow_exceed_demand=False (default)
        profile = self._create_profile_nnn_sequential()
        profile.allow_exceed_demand = False

        picking_type = self._create_picking_type_with_profile(profile)
        picking = self._create_picking(picking_type)

        # Create move with demand of 2 units
        self._create_move(picking, self.product_no_track_a, 2)
        picking.action_confirm()

        # Scan product twice (reaches demand exactly)
        result = picking.process_scanned_barcode("PROD-NO-TRACK-A")
        self._assert_scan_success(result)
        self._assert_quantity_picked(picking, self.product_no_track_a, 1)

        result = picking.process_scanned_barcode("PROD-NO-TRACK-A")
        self._assert_scan_success(result)
        self._assert_quantity_picked(picking, self.product_no_track_a, 2)

        # Try to scan again (would exceed demand) - should be BLOCKED
        result = picking.process_scanned_barcode("PROD-NO-TRACK-A")
        self.assertFalse(result["success"])
        self.assertIn("exceeds demand", result["message"].lower())

        # Quantity should NOT have increased in backend
        self._assert_quantity_picked(picking, self.product_no_track_a, 2)

    def test_02_exceed_demand_allowed_product_no_tracking(self):
        """
        Test that exceeding demand shows warning but allows
        when allow_exceed_demand=True for products without tracking
        """
        # Create profile with allow_exceed_demand=True
        profile = self._create_profile_nnn_sequential()
        profile.allow_exceed_demand = True

        picking_type = self._create_picking_type_with_profile(profile)
        picking = self._create_picking(picking_type)

        # Create move with demand of 2 units
        self._create_move(picking, self.product_no_track_a, 2)
        picking.action_confirm()

        # Scan product twice (reaches demand exactly)
        result = picking.process_scanned_barcode("PROD-NO-TRACK-A")
        self._assert_scan_success(result)
        self._assert_quantity_picked(picking, self.product_no_track_a, 1)

        result = picking.process_scanned_barcode("PROD-NO-TRACK-A")
        self._assert_scan_success(result)
        self._assert_quantity_picked(picking, self.product_no_track_a, 2)

        # Scan again (exceeds demand) - should be ALLOWED with warning
        result = picking.process_scanned_barcode("PROD-NO-TRACK-A")
        self.assertTrue(
            result["success"], "Scan should succeed when allow_exceed_demand=True"
        )
        self.assertIn("EXCEEDS DEMAND", result["message"])
        self.assertIn("⚠️", result["message"])

        # Quantity SHOULD have increased in backend and UI
        self._assert_quantity_picked(picking, self.product_no_track_a, 3)

    def test_03_exceed_demand_not_allowed_serial(self):
        """Test that exceeding demand is blocked "
        "when allow_exceed_demand=False for serials"""
        # Create profile with allow_exceed_demand=False (default)
        profile = self._create_profile_sss_sequential()
        profile.allow_exceed_demand = False

        picking_type = self._create_picking_type_with_profile(profile)
        picking = self._create_picking(picking_type)

        # Create move with demand of 2 serials
        self._create_move(picking, self.product_serial_a, 2)
        picking.action_confirm()

        # Scan product and 2 serials (reaches demand exactly)
        result = picking.process_scanned_barcode("PROD-SERIAL-A")
        self._assert_scan_success(result)

        result = picking.process_scanned_barcode("SERIAL-A-001")
        self._assert_scan_success(result)
        self._assert_quantity_picked(picking, self.product_serial_a, 1)

        result = picking.process_scanned_barcode("SERIAL-A-002")
        self._assert_scan_success(result)
        self._assert_quantity_picked(picking, self.product_serial_a, 2)

        # Try to scan third serial (would exceed demand) - should be BLOCKED
        result = picking.process_scanned_barcode("SERIAL-A-003")
        self.assertFalse(result["success"])
        self.assertIn("exceeds demand", result["message"].lower())

        # Quantity should NOT have increased in backend
        self._assert_quantity_picked(picking, self.product_serial_a, 2)

    def test_04_exceed_demand_allowed_serial(self):
        """
        Test that exceeding demand shows warning but
        allows when allow_exceed_demand=True for serials
        """
        # Create profile with allow_exceed_demand=True
        profile = self._create_profile_sss_sequential()
        profile.allow_exceed_demand = True

        picking_type = self._create_picking_type_with_profile(profile)
        picking = self._create_picking(picking_type)

        # Create move with demand of 2 serials
        self._create_move(picking, self.product_serial_a, 2)
        picking.action_confirm()

        # Scan product and 2 serials (reaches demand exactly)
        result = picking.process_scanned_barcode("PROD-SERIAL-A")
        self._assert_scan_success(result)

        result = picking.process_scanned_barcode("SERIAL-A-001")
        self._assert_scan_success(result)
        self._assert_quantity_picked(picking, self.product_serial_a, 1)

        result = picking.process_scanned_barcode("SERIAL-A-002")
        self._assert_scan_success(result)
        self._assert_quantity_picked(picking, self.product_serial_a, 2)

        # Scan third serial (exceeds demand) - should be ALLOWED with warning
        result = picking.process_scanned_barcode("SERIAL-A-003")
        self.assertTrue(
            result["success"], "Scan should succeed when allow_exceed_demand=True"
        )
        self.assertIn("EXCEEDS DEMAND", result["message"])
        self.assertIn("⚠️", result["message"])

        # Quantity SHOULD have increased in backend and UI
        self._assert_quantity_picked(picking, self.product_serial_a, 3)

    def test_05_exceed_demand_not_allowed_lot(self):
        """
        Test that exceeding demand is blocked
        when allow_exceed_demand=False for lots
        """
        # Create profile with allow_exceed_demand=False (default)
        profile = self._create_profile_lll_sequential()
        profile.allow_exceed_demand = False

        picking_type = self._create_picking_type_with_profile(profile)
        picking = self._create_picking(picking_type)

        # Create move with demand of 2 units
        self._create_move(picking, self.product_lot_a, 2)
        picking.action_confirm()

        # Scan product and lot twice (reaches demand exactly)
        result = picking.process_scanned_barcode("PROD-LOT-A")
        self._assert_scan_success(result)

        result = picking.process_scanned_barcode("LOT-A-001")
        self._assert_scan_success(result)
        self._assert_quantity_picked(picking, self.product_lot_a, 1)

        result = picking.process_scanned_barcode("LOT-A-001")
        self._assert_scan_success(result)
        self._assert_quantity_picked(picking, self.product_lot_a, 2)

        # Try to scan lot again (would exceed demand) - should be BLOCKED
        result = picking.process_scanned_barcode("LOT-A-001")
        self.assertFalse(result["success"])
        self.assertIn("exceeds demand", result["message"].lower())

        # Quantity should NOT have increased in backend
        self._assert_quantity_picked(picking, self.product_lot_a, 2)

    def test_06_exceed_demand_allowed_lot(self):
        """
        Test that exceeding demand shows warning but allows
        when allow_exceed_demand=True for lots
        """
        # Create profile with allow_exceed_demand=True
        profile = self._create_profile_lll_sequential()
        profile.allow_exceed_demand = True

        picking_type = self._create_picking_type_with_profile(profile)
        picking = self._create_picking(picking_type)

        # Create move with demand of 2 units
        self._create_move(picking, self.product_lot_a, 2)
        picking.action_confirm()

        # Scan product and lot twice (reaches demand exactly)
        result = picking.process_scanned_barcode("PROD-LOT-A")
        self._assert_scan_success(result)

        result = picking.process_scanned_barcode("LOT-A-001")
        self._assert_scan_success(result)
        self._assert_quantity_picked(picking, self.product_lot_a, 1)

        result = picking.process_scanned_barcode("LOT-A-001")
        self._assert_scan_success(result)
        self._assert_quantity_picked(picking, self.product_lot_a, 2)

        # Scan lot again (exceeds demand) - should be ALLOWED with warning
        result = picking.process_scanned_barcode("LOT-A-001")
        self.assertTrue(
            result["success"], "Scan should succeed when allow_exceed_demand=True"
        )
        self.assertIn("EXCEEDS DEMAND", result["message"])
        self.assertIn("⚠️", result["message"])

        # Quantity SHOULD have increased in backend and UI
        self._assert_quantity_picked(picking, self.product_lot_a, 3)
