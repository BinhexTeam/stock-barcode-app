"""Tests for internal transfer operations with barcode scanning"""
from .test_common import BarcodeTestCommon


class TestBarcodeInternalTransfer(BarcodeTestCommon):
    """Test barcode scanning for internal transfer operations"""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # Get internal transfer profile from data
        cls.profile_internal = cls.env.ref(
            "stock_barcode_oca.profile_internal_transfer_basic"
        )

        # Create internal transfer picking type
        cls.picking_type_internal = cls.env["stock.picking.type"].create(
            {
                "name": "Test Internal Transfer",
                "code": "internal",
                "sequence_code": "TEST-INT",
                "barcode_profile_id": cls.profile_internal.id,
                "default_location_src_id": cls.location_shelf_a.id,
                "default_location_dest_id": cls.location_shelf_b.id,
            }
        )

        # Create stock quants for products that need inventory
        cls._create_initial_stock()

    @classmethod
    def _create_initial_stock(cls):
        """Create initial stock for products"""
        # Stock for products without tracking
        cls.env["stock.quant"]._update_available_quantity(
            cls.product_none_a, cls.location_shelf_a, 100
        )
        cls.env["stock.quant"]._update_available_quantity(
            cls.product_none_b, cls.location_shelf_a, 100
        )
        cls.env["stock.quant"]._update_available_quantity(
            cls.product_none_c, cls.location_shelf_a, 100
        )

        # Stock for products with lot tracking
        cls.env["stock.quant"]._update_available_quantity(
            cls.product_lot_a, cls.location_shelf_a, 50, lot_id=cls.lot_a1
        )
        cls.env["stock.quant"]._update_available_quantity(
            cls.product_lot_a, cls.location_shelf_a, 50, lot_id=cls.lot_a2
        )
        cls.env["stock.quant"]._update_available_quantity(
            cls.product_lot_b, cls.location_shelf_a, 50, lot_id=cls.lot_b1
        )
        cls.env["stock.quant"]._update_available_quantity(
            cls.product_lot_b, cls.location_shelf_a, 50, lot_id=cls.lot_b2
        )
        cls.env["stock.quant"]._update_available_quantity(
            cls.product_lot_c, cls.location_shelf_a, 50, lot_id=cls.lot_c1
        )
        cls.env["stock.quant"]._update_available_quantity(
            cls.product_lot_c, cls.location_shelf_a, 50, lot_id=cls.lot_c2
        )

        # Stock for products with serial tracking
        cls.env["stock.quant"]._update_available_quantity(
            cls.product_serial_a, cls.location_shelf_a, 1, lot_id=cls.serial_a1
        )
        cls.env["stock.quant"]._update_available_quantity(
            cls.product_serial_a, cls.location_shelf_a, 1, lot_id=cls.serial_a2
        )
        cls.env["stock.quant"]._update_available_quantity(
            cls.product_serial_a, cls.location_shelf_a, 1, lot_id=cls.serial_a3
        )
        cls.env["stock.quant"]._update_available_quantity(
            cls.product_serial_b, cls.location_shelf_a, 1, lot_id=cls.serial_b1
        )
        cls.env["stock.quant"]._update_available_quantity(
            cls.product_serial_b, cls.location_shelf_a, 1, lot_id=cls.serial_b2
        )
        cls.env["stock.quant"]._update_available_quantity(
            cls.product_serial_b, cls.location_shelf_a, 1, lot_id=cls.serial_b3
        )
        cls.env["stock.quant"]._update_available_quantity(
            cls.product_serial_c, cls.location_shelf_a, 1, lot_id=cls.serial_c1
        )
        cls.env["stock.quant"]._update_available_quantity(
            cls.product_serial_c, cls.location_shelf_a, 1, lot_id=cls.serial_c2
        )
        cls.env["stock.quant"]._update_available_quantity(
            cls.product_serial_c, cls.location_shelf_a, 1, lot_id=cls.serial_c3
        )

    def _create_internal_transfer(self, products_and_quantities):
        """Create an internal transfer picking with specified products

        Args:
            products_and_quantities: list of tuples (product, qty)
        """
        picking = self.env["stock.picking"].create(
            {
                "picking_type_id": self.picking_type_internal.id,
                "location_id": self.location_shelf_a.id,
                "location_dest_id": self.location_shelf_b.id,
            }
        )

        for product, qty in products_and_quantities:
            self._create_move(picking, product, qty)

        picking.action_confirm()
        return picking

    # ========================================
    # Test all products type 'none' (NNN)
    # ========================================
    def test_01_internal_nnn_sequential(self):
        """Internal Transfer: 3 products tracking='none', scanned sequentially"""
        picking = self._create_internal_transfer(
            [
                (self.product_none_a, 2),
                (self.product_none_b, 3),
                (self.product_none_c, 1),
            ]
        )

        # Optional: scan source location
        result = picking.process_scanned_barcode("LOC-SHELF-A")
        self._assert_scan_success(result, "source")

        # Scan products
        result = picking.process_scanned_barcode("PROD-NONE-A")
        self._assert_scan_success(result)
        result = picking.process_scanned_barcode("PROD-NONE-A")
        self._assert_scan_success(result)
        self._assert_quantity_picked(picking, self.product_none_a, 2)

        result = picking.process_scanned_barcode("PROD-NONE-B")
        self._assert_scan_success(result)
        result = picking.process_scanned_barcode("PROD-NONE-B")
        self._assert_scan_success(result)
        result = picking.process_scanned_barcode("PROD-NONE-B")
        self._assert_scan_success(result)
        self._assert_quantity_picked(picking, self.product_none_b, 3)

        result = picking.process_scanned_barcode("PROD-NONE-C")
        self._assert_scan_success(result)
        self._assert_quantity_picked(picking, self.product_none_c, 1)

        self._assert_step_is_final(picking)

        # Scan destination
        result = picking.process_scanned_barcode("LOC-SHELF-B")
        self._assert_scan_success(result, "destination")

    def test_02_internal_nnn_without_source_scan(self):
        """Internal Transfer: Skip optional source location scan"""
        picking = self._create_internal_transfer(
            [
                (self.product_none_a, 1),
                (self.product_none_b, 1),
                (self.product_none_c, 1),
            ]
        )

        # Skip source location, go directly to products
        result = picking.process_scanned_barcode("PROD-NONE-A")
        self._assert_scan_success(result)
        result = picking.process_scanned_barcode("PROD-NONE-B")
        self._assert_scan_success(result)
        result = picking.process_scanned_barcode("PROD-NONE-C")
        self._assert_scan_success(result)

        self._assert_step_is_final(picking)

    # ========================================
    # Test all products type 'lot' (LLL)
    # ========================================
    def test_03_internal_lll_sequential(self):
        """Internal Transfer: 3 products tracking='lot', scanned sequentially"""
        picking = self._create_internal_transfer(
            [
                (self.product_lot_a, 3),
                (self.product_lot_b, 2),
                (self.product_lot_c, 2),
            ]
        )

        # Product A with LOT-A-001 (3 times)
        result = picking.process_scanned_barcode("PROD-LOT-A")
        self._assert_scan_success(result)
        result = picking.process_scanned_barcode("LOT-A-001")
        self._assert_scan_success(result, "lot")
        result = picking.process_scanned_barcode("PROD-LOT-A")
        self._assert_scan_success(result)
        result = picking.process_scanned_barcode("LOT-A-001")
        self._assert_scan_success(result)
        result = picking.process_scanned_barcode("PROD-LOT-A")
        self._assert_scan_success(result)
        result = picking.process_scanned_barcode("LOT-A-001")
        self._assert_scan_success(result)
        self._assert_quantity_picked(picking, self.product_lot_a, 3)

        # Product B with LOT-B-001 (2 times)
        result = picking.process_scanned_barcode("PROD-LOT-B")
        self._assert_scan_success(result)
        result = picking.process_scanned_barcode("LOT-B-001")
        self._assert_scan_success(result)
        result = picking.process_scanned_barcode("PROD-LOT-B")
        self._assert_scan_success(result)
        result = picking.process_scanned_barcode("LOT-B-001")
        self._assert_scan_success(result)
        self._assert_quantity_picked(picking, self.product_lot_b, 2)

        # Product C with LOT-C-001 (2 times)
        result = picking.process_scanned_barcode("PROD-LOT-C")
        self._assert_scan_success(result)
        result = picking.process_scanned_barcode("LOT-C-001")
        self._assert_scan_success(result)
        result = picking.process_scanned_barcode("PROD-LOT-C")
        self._assert_scan_success(result)
        result = picking.process_scanned_barcode("LOT-C-001")
        self._assert_scan_success(result)
        self._assert_quantity_picked(picking, self.product_lot_c, 2)

        self._assert_step_is_final(picking)

    def test_04_internal_lll_mixed_lots(self):
        """Internal Transfer: 3 products tracking='lot' with different lots"""
        picking = self._create_internal_transfer(
            [
                (self.product_lot_a, 2),
                (self.product_lot_b, 2),
                (self.product_lot_c, 2),
            ]
        )

        # Product A: 1 from LOT-A-001, 1 from LOT-A-002
        result = picking.process_scanned_barcode("PROD-LOT-A")
        self._assert_scan_success(result)
        result = picking.process_scanned_barcode("LOT-A-001")
        self._assert_scan_success(result)
        result = picking.process_scanned_barcode("PROD-LOT-A")
        self._assert_scan_success(result)
        result = picking.process_scanned_barcode("LOT-A-002")
        self._assert_scan_success(result)

        # Product B: 1 from LOT-B-001, 1 from LOT-B-002
        result = picking.process_scanned_barcode("PROD-LOT-B")
        self._assert_scan_success(result)
        result = picking.process_scanned_barcode("LOT-B-001")
        self._assert_scan_success(result)
        result = picking.process_scanned_barcode("PROD-LOT-B")
        self._assert_scan_success(result)
        result = picking.process_scanned_barcode("LOT-B-002")
        self._assert_scan_success(result)

        # Product C: 1 from LOT-C-001, 1 from LOT-C-002
        result = picking.process_scanned_barcode("PROD-LOT-C")
        self._assert_scan_success(result)
        result = picking.process_scanned_barcode("LOT-C-001")
        self._assert_scan_success(result)
        result = picking.process_scanned_barcode("PROD-LOT-C")
        self._assert_scan_success(result)
        result = picking.process_scanned_barcode("LOT-C-002")
        self._assert_scan_success(result)

        self._assert_quantity_picked(picking, self.product_lot_a, 2)
        self._assert_quantity_picked(picking, self.product_lot_b, 2)
        self._assert_quantity_picked(picking, self.product_lot_c, 2)
        self._assert_step_is_final(picking)

    # ========================================
    # Test all products type 'serial' (SSS)
    # ========================================
    def test_05_internal_sss_sequential(self):
        """Internal Transfer: 3 products tracking='serial', scanned sequentially"""
        picking = self._create_internal_transfer(
            [
                (self.product_serial_a, 2),
                (self.product_serial_b, 2),
                (self.product_serial_c, 2),
            ]
        )

        # Product A with 2 different serials
        result = picking.process_scanned_barcode("PROD-SERIAL-A")
        self._assert_scan_success(result)
        result = picking.process_scanned_barcode("SN-A-001")
        self._assert_scan_success(result, "serial")
        result = picking.process_scanned_barcode("PROD-SERIAL-A")
        self._assert_scan_success(result)
        result = picking.process_scanned_barcode("SN-A-002")
        self._assert_scan_success(result)
        self._assert_quantity_picked(picking, self.product_serial_a, 2)

        # Product B with 2 different serials
        result = picking.process_scanned_barcode("PROD-SERIAL-B")
        self._assert_scan_success(result)
        result = picking.process_scanned_barcode("SN-B-001")
        self._assert_scan_success(result)
        result = picking.process_scanned_barcode("PROD-SERIAL-B")
        self._assert_scan_success(result)
        result = picking.process_scanned_barcode("SN-B-002")
        self._assert_scan_success(result)
        self._assert_quantity_picked(picking, self.product_serial_b, 2)

        # Product C with 2 different serials
        result = picking.process_scanned_barcode("PROD-SERIAL-C")
        self._assert_scan_success(result)
        result = picking.process_scanned_barcode("SN-C-001")
        self._assert_scan_success(result)
        result = picking.process_scanned_barcode("PROD-SERIAL-C")
        self._assert_scan_success(result)
        result = picking.process_scanned_barcode("SN-C-002")
        self._assert_scan_success(result)
        self._assert_quantity_picked(picking, self.product_serial_c, 2)

        self._assert_step_is_final(picking)

    def test_06_internal_sss_validate_existing_serials(self):
        """Internal Transfer: Can only use existing serials in stock"""
        picking = self._create_internal_transfer([(self.product_serial_a, 2)])

        # Try to scan a serial that doesn't exist in stock - should fail
        result = picking.process_scanned_barcode("PROD-SERIAL-A")
        self._assert_scan_success(result)
        result = picking.process_scanned_barcode("SN-A-999-NOT-EXISTS")
        self._assert_scan_failed(result)

    # ========================================
    # Test combinations: NLS, NSL, LNS, LSN, SNL, SLN
    # ========================================
    def test_07_internal_nls_combination(self):
        """Internal Transfer: Combination tracking='none', 'lot', 'serial'"""
        picking = self._create_internal_transfer(
            [
                (self.product_none_a, 2),
                (self.product_lot_a, 2),
                (self.product_serial_a, 2),
            ]
        )

        # None
        result = picking.process_scanned_barcode("PROD-NONE-A")
        self._assert_scan_success(result)
        result = picking.process_scanned_barcode("PROD-NONE-A")
        self._assert_scan_success(result)

        # Lot
        result = picking.process_scanned_barcode("PROD-LOT-A")
        self._assert_scan_success(result)
        result = picking.process_scanned_barcode("LOT-A-001")
        self._assert_scan_success(result)
        result = picking.process_scanned_barcode("PROD-LOT-A")
        self._assert_scan_success(result)
        result = picking.process_scanned_barcode("LOT-A-001")
        self._assert_scan_success(result)

        # Serial
        result = picking.process_scanned_barcode("PROD-SERIAL-A")
        self._assert_scan_success(result)
        result = picking.process_scanned_barcode("SN-A-001")
        self._assert_scan_success(result)
        result = picking.process_scanned_barcode("PROD-SERIAL-A")
        self._assert_scan_success(result)
        result = picking.process_scanned_barcode("SN-A-002")
        self._assert_scan_success(result)

        self._assert_step_is_final(picking)

    def test_08_internal_nsl_combination(self):
        """Internal Transfer: Combination tracking='none', 'serial', 'lot'"""
        picking = self._create_internal_transfer(
            [
                (self.product_none_a, 1),
                (self.product_serial_a, 1),
                (self.product_lot_a, 1),
            ]
        )

        result = picking.process_scanned_barcode("PROD-NONE-A")
        self._assert_scan_success(result)

        result = picking.process_scanned_barcode("PROD-SERIAL-A")
        self._assert_scan_success(result)
        result = picking.process_scanned_barcode("SN-A-001")
        self._assert_scan_success(result)

        result = picking.process_scanned_barcode("PROD-LOT-A")
        self._assert_scan_success(result)
        result = picking.process_scanned_barcode("LOT-A-001")
        self._assert_scan_success(result)

        self._assert_step_is_final(picking)

    def test_09_internal_lns_combination(self):
        """Internal Transfer: Combination tracking='lot', 'none', 'serial'"""
        picking = self._create_internal_transfer(
            [
                (self.product_lot_a, 1),
                (self.product_none_a, 1),
                (self.product_serial_a, 1),
            ]
        )

        result = picking.process_scanned_barcode("PROD-LOT-A")
        self._assert_scan_success(result)
        result = picking.process_scanned_barcode("LOT-A-001")
        self._assert_scan_success(result)

        result = picking.process_scanned_barcode("PROD-NONE-A")
        self._assert_scan_success(result)

        result = picking.process_scanned_barcode("PROD-SERIAL-A")
        self._assert_scan_success(result)
        result = picking.process_scanned_barcode("SN-A-001")
        self._assert_scan_success(result)

        self._assert_step_is_final(picking)

    def test_10_internal_lsn_combination(self):
        """Internal Transfer: Combination tracking='lot', 'serial', 'none'"""
        picking = self._create_internal_transfer(
            [
                (self.product_lot_a, 1),
                (self.product_serial_a, 1),
                (self.product_none_a, 1),
            ]
        )

        result = picking.process_scanned_barcode("PROD-LOT-A")
        self._assert_scan_success(result)
        result = picking.process_scanned_barcode("LOT-A-001")
        self._assert_scan_success(result)

        result = picking.process_scanned_barcode("PROD-SERIAL-A")
        self._assert_scan_success(result)
        result = picking.process_scanned_barcode("SN-A-001")
        self._assert_scan_success(result)

        result = picking.process_scanned_barcode("PROD-NONE-A")
        self._assert_scan_success(result)

        self._assert_step_is_final(picking)

    def test_11_internal_snl_combination(self):
        """Internal Transfer: Combination tracking='serial', 'none', 'lot'"""
        picking = self._create_internal_transfer(
            [
                (self.product_serial_a, 1),
                (self.product_none_a, 1),
                (self.product_lot_a, 1),
            ]
        )

        result = picking.process_scanned_barcode("PROD-SERIAL-A")
        self._assert_scan_success(result)
        result = picking.process_scanned_barcode("SN-A-001")
        self._assert_scan_success(result)

        result = picking.process_scanned_barcode("PROD-NONE-A")
        self._assert_scan_success(result)

        result = picking.process_scanned_barcode("PROD-LOT-A")
        self._assert_scan_success(result)
        result = picking.process_scanned_barcode("LOT-A-001")
        self._assert_scan_success(result)

        self._assert_step_is_final(picking)

    def test_12_internal_sln_combination(self):
        """Internal Transfer: Combination tracking='serial', 'lot', 'none'"""
        picking = self._create_internal_transfer(
            [
                (self.product_serial_a, 1),
                (self.product_lot_a, 1),
                (self.product_none_a, 1),
            ]
        )

        result = picking.process_scanned_barcode("PROD-SERIAL-A")
        self._assert_scan_success(result)
        result = picking.process_scanned_barcode("SN-A-001")
        self._assert_scan_success(result)

        result = picking.process_scanned_barcode("PROD-LOT-A")
        self._assert_scan_success(result)
        result = picking.process_scanned_barcode("LOT-A-001")
        self._assert_scan_success(result)

        result = picking.process_scanned_barcode("PROD-NONE-A")
        self._assert_scan_success(result)

        self._assert_step_is_final(picking)

    # ========================================
    # Additional validation tests
    # ========================================
    def test_13_internal_lot_must_exist(self):
        """Internal Transfer: Lot must exist in inventory (cannot create new)"""
        picking = self._create_internal_transfer([(self.product_lot_a, 1)])

        result = picking.process_scanned_barcode("PROD-LOT-A")
        self._assert_scan_success(result)

        # Try to scan non-existing lot - should fail
        result = picking.process_scanned_barcode("LOT-A-999-NOT-EXISTS")
        self._assert_scan_failed(result)

    def test_14_internal_serial_cannot_repeat(self):
        """Internal Transfer: Cannot scan same serial twice"""
        picking = self._create_internal_transfer([(self.product_serial_a, 2)])

        result = picking.process_scanned_barcode("PROD-SERIAL-A")
        self._assert_scan_success(result)
        result = picking.process_scanned_barcode("SN-A-001")
        self._assert_scan_success(result)

        # Try to scan same serial again
        result = picking.process_scanned_barcode("PROD-SERIAL-A")
        self._assert_scan_success(result)
        result = picking.process_scanned_barcode("SN-A-001")
        self._assert_scan_failed(result, "already used")
