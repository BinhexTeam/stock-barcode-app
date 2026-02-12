"""Tests for reception (incoming) operations with barcode scanning"""
from .test_common import BarcodeTestCommon


class TestBarcodeReception(BarcodeTestCommon):
    """Test barcode scanning for reception operations"""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # Get reception profile from data
        cls.profile_reception = cls.env.ref("stock_barcode_oca.profile_reception_basic")

        # Create reception picking type
        cls.picking_type_in = cls.env["stock.picking.type"].create(
            {
                "name": "Test Reception",
                "code": "incoming",
                "sequence_code": "TEST-IN",
                "barcode_profile_id": cls.profile_reception.id,
                "default_location_src_id": cls.location_supplier.id,
                "default_location_dest_id": cls.location_stock.id,
            }
        )

    def _create_reception(self, products_and_quantities):
        """Create a reception picking with specified products

        Args:
            products_and_quantities: list of tuples (product, qty)
        """
        picking = self.env["stock.picking"].create(
            {
                "picking_type_id": self.picking_type_in.id,
                "location_id": self.location_supplier.id,
                "location_dest_id": self.location_stock.id,
            }
        )

        for product, qty in products_and_quantities:
            self._create_move(picking, product, qty)

        picking.action_confirm()
        return picking

    # ========================================
    # Test all products type 'none' (NNN)
    # ========================================
    def test_01_reception_nnn_sequential(self):
        """Reception: 3 products tracking='none', scanned sequentially"""
        picking = self._create_reception(
            [
                (self.product_none_a, 2),
                (self.product_none_b, 3),
                (self.product_none_c, 1),
            ]
        )

        # Scan product A twice
        result = picking.process_scanned_barcode("PROD-NONE-A")
        self._assert_scan_success(result, "product")
        result = picking.process_scanned_barcode("PROD-NONE-A")
        self._assert_scan_success(result)
        self._assert_quantity_picked(picking, self.product_none_a, 2)

        # Scan product B three times
        result = picking.process_scanned_barcode("PROD-NONE-B")
        self._assert_scan_success(result)
        result = picking.process_scanned_barcode("PROD-NONE-B")
        self._assert_scan_success(result)
        result = picking.process_scanned_barcode("PROD-NONE-B")
        self._assert_scan_success(result)
        self._assert_quantity_picked(picking, self.product_none_b, 3)

        # Scan product C once
        result = picking.process_scanned_barcode("PROD-NONE-C")
        self._assert_scan_success(result)
        self._assert_quantity_picked(picking, self.product_none_c, 1)

        # Should now be in final step
        self._assert_step_is_final(picking)

        # Scan destination
        result = picking.process_scanned_barcode("LOC-STOCK-001")
        self._assert_scan_success(result, "destination")

    def test_02_reception_nnn_mixed(self):
        """Reception: 3 products tracking='none', scanned in mixed order"""
        picking = self._create_reception(
            [
                (self.product_none_a, 2),
                (self.product_none_b, 2),
                (self.product_none_c, 2),
            ]
        )

        # Mixed scanning: A, B, A, C, B, C
        result = picking.process_scanned_barcode("PROD-NONE-A")
        self._assert_scan_success(result)
        result = picking.process_scanned_barcode("PROD-NONE-B")
        self._assert_scan_success(result)
        result = picking.process_scanned_barcode("PROD-NONE-A")
        self._assert_scan_success(result)
        result = picking.process_scanned_barcode("PROD-NONE-C")
        self._assert_scan_success(result)
        result = picking.process_scanned_barcode("PROD-NONE-B")
        self._assert_scan_success(result)
        result = picking.process_scanned_barcode("PROD-NONE-C")
        self._assert_scan_success(result)

        self._assert_quantity_picked(picking, self.product_none_a, 2)
        self._assert_quantity_picked(picking, self.product_none_b, 2)
        self._assert_quantity_picked(picking, self.product_none_c, 2)
        self._assert_step_is_final(picking)

    # ========================================
    # Test all products type 'lot' (LLL)
    # ========================================
    def test_03_reception_lll_sequential_create_lots(self):
        """Reception: 3 products tracking='lot', creating lots on-the-fly"""
        picking = self._create_reception(
            [
                (self.product_lot_a, 3),
                (self.product_lot_b, 2),
                (self.product_lot_c, 3),
            ]
        )

        # Product A with LOT-A-NEW-001 (3 times)
        result = picking.process_scanned_barcode("PROD-LOT-A")
        self._assert_scan_success(result)
        result = picking.process_scanned_barcode("LOT-A-NEW-001")
        self._assert_scan_success(result, "lot")
        result = picking.process_scanned_barcode("PROD-LOT-A")
        self._assert_scan_success(result)
        result = picking.process_scanned_barcode("LOT-A-NEW-001")
        self._assert_scan_success(result)
        result = picking.process_scanned_barcode("PROD-LOT-A")
        self._assert_scan_success(result)
        result = picking.process_scanned_barcode("LOT-A-NEW-001")
        self._assert_scan_success(result)
        self._assert_quantity_picked(picking, self.product_lot_a, 3)

        # Product B with LOT-B-NEW-001 (2 times)
        result = picking.process_scanned_barcode("PROD-LOT-B")
        self._assert_scan_success(result)
        result = picking.process_scanned_barcode("LOT-B-NEW-001")
        self._assert_scan_success(result)
        result = picking.process_scanned_barcode("PROD-LOT-B")
        self._assert_scan_success(result)
        result = picking.process_scanned_barcode("LOT-B-NEW-001")
        self._assert_scan_success(result)
        self._assert_quantity_picked(picking, self.product_lot_b, 2)

        # Product C with LOT-C-NEW-001 (3 times)
        result = picking.process_scanned_barcode("PROD-LOT-C")
        self._assert_scan_success(result)
        result = picking.process_scanned_barcode("LOT-C-NEW-001")
        self._assert_scan_success(result)
        result = picking.process_scanned_barcode("PROD-LOT-C")
        self._assert_scan_success(result)
        result = picking.process_scanned_barcode("LOT-C-NEW-001")
        self._assert_scan_success(result)
        result = picking.process_scanned_barcode("PROD-LOT-C")
        self._assert_scan_success(result)
        result = picking.process_scanned_barcode("LOT-C-NEW-001")
        self._assert_scan_success(result)
        self._assert_quantity_picked(picking, self.product_lot_c, 3)

        self._assert_step_is_final(picking)

        # Verify lots were created
        new_lot_a = self.env["stock.lot"].search(
            [("name", "=", "LOT-A-NEW-001"), ("product_id", "=", self.product_lot_a.id)]
        )
        self.assertTrue(new_lot_a, "LOT-A-NEW-001 should have been created")

    def test_04_reception_lll_mixed_products_same_lot(self):
        """Reception: 3 products tracking='lot', scanning same lot multiple times"""
        picking = self._create_reception(
            [
                (self.product_lot_a, 2),
                (self.product_lot_b, 2),
                (self.product_lot_c, 2),
            ]
        )

        # Mixed: A+LOT, B+LOT, A+LOT, C+LOT, B+LOT, C+LOT
        result = picking.process_scanned_barcode("PROD-LOT-A")
        self._assert_scan_success(result)
        result = picking.process_scanned_barcode("LOT-BATCH-001")
        self._assert_scan_success(result)

        result = picking.process_scanned_barcode("PROD-LOT-B")
        self._assert_scan_success(result)
        result = picking.process_scanned_barcode("LOT-BATCH-002")
        self._assert_scan_success(result)

        result = picking.process_scanned_barcode("PROD-LOT-A")
        self._assert_scan_success(result)
        result = picking.process_scanned_barcode("LOT-BATCH-001")
        self._assert_scan_success(result)

        result = picking.process_scanned_barcode("PROD-LOT-C")
        self._assert_scan_success(result)
        result = picking.process_scanned_barcode("LOT-BATCH-003")
        self._assert_scan_success(result)

        result = picking.process_scanned_barcode("PROD-LOT-B")
        self._assert_scan_success(result)
        result = picking.process_scanned_barcode("LOT-BATCH-002")
        self._assert_scan_success(result)

        result = picking.process_scanned_barcode("PROD-LOT-C")
        self._assert_scan_success(result)
        result = picking.process_scanned_barcode("LOT-BATCH-003")
        self._assert_scan_success(result)

        self._assert_quantity_picked(picking, self.product_lot_a, 2)
        self._assert_quantity_picked(picking, self.product_lot_b, 2)
        self._assert_quantity_picked(picking, self.product_lot_c, 2)
        self._assert_step_is_final(picking)

    # ========================================
    # Test all products type 'serial' (SSS)
    # ========================================
    def test_05_reception_sss_sequential_create_serials(self):
        """Reception: 3 products tracking='serial', creating serials on-the-fly"""
        picking = self._create_reception(
            [
                (self.product_serial_a, 2),
                (self.product_serial_b, 2),
                (self.product_serial_c, 2),
            ]
        )

        # Product A with 2 different serials
        result = picking.process_scanned_barcode("PROD-SERIAL-A")
        self._assert_scan_success(result)
        result = picking.process_scanned_barcode("SN-A-NEW-001")
        self._assert_scan_success(result, "serial")
        result = picking.process_scanned_barcode("PROD-SERIAL-A")
        self._assert_scan_success(result)
        result = picking.process_scanned_barcode("SN-A-NEW-002")
        self._assert_scan_success(result)
        self._assert_quantity_picked(picking, self.product_serial_a, 2)

        # Product B with 2 different serials
        result = picking.process_scanned_barcode("PROD-SERIAL-B")
        self._assert_scan_success(result)
        result = picking.process_scanned_barcode("SN-B-NEW-001")
        self._assert_scan_success(result)
        result = picking.process_scanned_barcode("PROD-SERIAL-B")
        self._assert_scan_success(result)
        result = picking.process_scanned_barcode("SN-B-NEW-002")
        self._assert_scan_success(result)
        self._assert_quantity_picked(picking, self.product_serial_b, 2)

        # Product C with 2 different serials
        result = picking.process_scanned_barcode("PROD-SERIAL-C")
        self._assert_scan_success(result)
        result = picking.process_scanned_barcode("SN-C-NEW-001")
        self._assert_scan_success(result)
        result = picking.process_scanned_barcode("PROD-SERIAL-C")
        self._assert_scan_success(result)
        result = picking.process_scanned_barcode("SN-C-NEW-002")
        self._assert_scan_success(result)
        self._assert_quantity_picked(picking, self.product_serial_c, 2)

        self._assert_step_is_final(picking)

    def test_06_reception_sss_validate_serial_uniqueness(self):
        """Reception: 3 products tracking='serial', validate serial cannot repeat"""
        picking = self._create_reception(
            [
                (self.product_serial_a, 3),
                (self.product_serial_b, 1),
                (self.product_serial_c, 1),
            ]
        )

        # Product A with SN-UNIQUE-001
        result = picking.process_scanned_barcode("PROD-SERIAL-A")
        self._assert_scan_success(result)
        result = picking.process_scanned_barcode("SN-UNIQUE-001")
        self._assert_scan_success(result)

        # Try to scan same serial again - should fail
        result = picking.process_scanned_barcode("PROD-SERIAL-A")
        self._assert_scan_success(result)
        result = picking.process_scanned_barcode("SN-UNIQUE-001")
        self._assert_scan_failed(result, "already used")

    # ========================================
    # Test combinations: NLS, NSL, LNS, LSN, SNL, SLN
    # ========================================
    def test_07_reception_nls_combination(self):
        """Reception: Combination of tracking='none', 'lot', 'serial'"""
        picking = self._create_reception(
            [
                (self.product_none_a, 2),
                (self.product_lot_a, 2),
                (self.product_serial_a, 2),
            ]
        )

        # Scan none product
        result = picking.process_scanned_barcode("PROD-NONE-A")
        self._assert_scan_success(result)
        result = picking.process_scanned_barcode("PROD-NONE-A")
        self._assert_scan_success(result)
        self._assert_quantity_picked(picking, self.product_none_a, 2)

        # Scan lot product
        result = picking.process_scanned_barcode("PROD-LOT-A")
        self._assert_scan_success(result)
        result = picking.process_scanned_barcode("LOT-NLS-001")
        self._assert_scan_success(result)
        result = picking.process_scanned_barcode("PROD-LOT-A")
        self._assert_scan_success(result)
        result = picking.process_scanned_barcode("LOT-NLS-001")
        self._assert_scan_success(result)
        self._assert_quantity_picked(picking, self.product_lot_a, 2)

        # Scan serial product
        result = picking.process_scanned_barcode("PROD-SERIAL-A")
        self._assert_scan_success(result)
        result = picking.process_scanned_barcode("SN-NLS-001")
        self._assert_scan_success(result)
        result = picking.process_scanned_barcode("PROD-SERIAL-A")
        self._assert_scan_success(result)
        result = picking.process_scanned_barcode("SN-NLS-002")
        self._assert_scan_success(result)
        self._assert_quantity_picked(picking, self.product_serial_a, 2)

        self._assert_step_is_final(picking)

    def test_08_reception_nsl_combination(self):
        """Reception: Combination tracking='none', 'serial', 'lot'"""
        picking = self._create_reception(
            [
                (self.product_none_a, 1),
                (self.product_serial_a, 2),
                (self.product_lot_a, 2),
            ]
        )

        # None
        result = picking.process_scanned_barcode("PROD-NONE-A")
        self._assert_scan_success(result)

        # Serial
        result = picking.process_scanned_barcode("PROD-SERIAL-A")
        self._assert_scan_success(result)
        result = picking.process_scanned_barcode("SN-NSL-001")
        self._assert_scan_success(result)
        result = picking.process_scanned_barcode("PROD-SERIAL-A")
        self._assert_scan_success(result)
        result = picking.process_scanned_barcode("SN-NSL-002")
        self._assert_scan_success(result)

        # Lot
        result = picking.process_scanned_barcode("PROD-LOT-A")
        self._assert_scan_success(result)
        result = picking.process_scanned_barcode("LOT-NSL-001")
        self._assert_scan_success(result)
        result = picking.process_scanned_barcode("PROD-LOT-A")
        self._assert_scan_success(result)
        result = picking.process_scanned_barcode("LOT-NSL-001")
        self._assert_scan_success(result)

        self._assert_step_is_final(picking)

    def test_09_reception_lns_combination(self):
        """Reception: Combination tracking='lot', 'none', 'serial'"""
        picking = self._create_reception(
            [
                (self.product_lot_a, 2),
                (self.product_none_a, 1),
                (self.product_serial_a, 2),
            ]
        )

        # Lot
        result = picking.process_scanned_barcode("PROD-LOT-A")
        self._assert_scan_success(result)
        result = picking.process_scanned_barcode("LOT-LNS-001")
        self._assert_scan_success(result)
        result = picking.process_scanned_barcode("PROD-LOT-A")
        self._assert_scan_success(result)
        result = picking.process_scanned_barcode("LOT-LNS-001")
        self._assert_scan_success(result)

        # None
        result = picking.process_scanned_barcode("PROD-NONE-A")
        self._assert_scan_success(result)

        # Serial
        result = picking.process_scanned_barcode("PROD-SERIAL-A")
        self._assert_scan_success(result)
        result = picking.process_scanned_barcode("SN-LNS-001")
        self._assert_scan_success(result)
        result = picking.process_scanned_barcode("PROD-SERIAL-A")
        self._assert_scan_success(result)
        result = picking.process_scanned_barcode("SN-LNS-002")
        self._assert_scan_success(result)

        self._assert_step_is_final(picking)

    def test_10_reception_lsn_combination(self):
        """Reception: Combination tracking='lot', 'serial', 'none'"""
        picking = self._create_reception(
            [
                (self.product_lot_a, 1),
                (self.product_serial_a, 1),
                (self.product_none_a, 1),
            ]
        )

        # Lot
        result = picking.process_scanned_barcode("PROD-LOT-A")
        self._assert_scan_success(result)
        result = picking.process_scanned_barcode("LOT-LSN-001")
        self._assert_scan_success(result)

        # Serial
        result = picking.process_scanned_barcode("PROD-SERIAL-A")
        self._assert_scan_success(result)
        result = picking.process_scanned_barcode("SN-LSN-001")
        self._assert_scan_success(result)

        # None
        result = picking.process_scanned_barcode("PROD-NONE-A")
        self._assert_scan_success(result)

        self._assert_step_is_final(picking)

    def test_11_reception_snl_combination(self):
        """Reception: Combination tracking='serial', 'none', 'lot'"""
        picking = self._create_reception(
            [
                (self.product_serial_a, 2),
                (self.product_none_a, 1),
                (self.product_lot_a, 1),
            ]
        )

        # Serial
        result = picking.process_scanned_barcode("PROD-SERIAL-A")
        self._assert_scan_success(result)
        result = picking.process_scanned_barcode("SN-SNL-001")
        self._assert_scan_success(result)
        result = picking.process_scanned_barcode("PROD-SERIAL-A")
        self._assert_scan_success(result)
        result = picking.process_scanned_barcode("SN-SNL-002")
        self._assert_scan_success(result)

        # None
        result = picking.process_scanned_barcode("PROD-NONE-A")
        self._assert_scan_success(result)

        # Lot
        result = picking.process_scanned_barcode("PROD-LOT-A")
        self._assert_scan_success(result)
        result = picking.process_scanned_barcode("LOT-SNL-001")
        self._assert_scan_success(result)

        self._assert_step_is_final(picking)

    def test_12_reception_sln_combination(self):
        """Reception: Combination tracking='serial', 'lot', 'none'"""
        picking = self._create_reception(
            [
                (self.product_serial_a, 1),
                (self.product_lot_a, 1),
                (self.product_none_a, 1),
            ]
        )

        # Serial
        result = picking.process_scanned_barcode("PROD-SERIAL-A")
        self._assert_scan_success(result)
        result = picking.process_scanned_barcode("SN-SLN-001")
        self._assert_scan_success(result)

        # Lot
        result = picking.process_scanned_barcode("PROD-LOT-A")
        self._assert_scan_success(result)
        result = picking.process_scanned_barcode("LOT-SLN-001")
        self._assert_scan_success(result)

        # None
        result = picking.process_scanned_barcode("PROD-NONE-A")
        self._assert_scan_success(result)

        self._assert_step_is_final(picking)

    # ========================================
    # Additional validation tests
    # ========================================
    def test_13_reception_cannot_exceed_demand(self):
        """Reception: Cannot scan more than expected quantity"""
        picking = self._create_reception([(self.product_none_a, 2)])

        result = picking.process_scanned_barcode("PROD-NONE-A")
        self._assert_scan_success(result)
        result = picking.process_scanned_barcode("PROD-NONE-A")
        self._assert_scan_success(result)

        # Try to scan third time - should fail
        result = picking.process_scanned_barcode("PROD-NONE-A")
        self._assert_scan_failed(result, "exceeds")

    def test_14_reception_lot_requires_product_first(self):
        """Reception: Cannot scan lot without product in context"""
        picking = self._create_reception([(self.product_lot_a, 2)])

        # Try to scan lot first - should fail
        result = picking.process_scanned_barcode("LOT-TEST-001")
        self._assert_scan_failed(result, "product first")
