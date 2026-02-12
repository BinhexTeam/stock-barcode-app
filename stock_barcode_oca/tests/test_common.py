"""Common test utilities for barcode scanning tests"""
from odoo.tests.common import TransactionCase


class BarcodeTestCommon(TransactionCase):
    """Base class for barcode scanning tests with common setup"""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._setup_locations()
        cls._setup_products()
        cls._setup_lots_and_serials()
        cls._setup_targets()
        cls._setup_nomenclature()

    @classmethod
    def _setup_locations(cls):
        """Create common test locations"""
        cls.location_supplier = cls.env["stock.location"].create(
            {
                "name": "Test Supplier Location",
                "barcode": "LOC-SUPPLIER-001",
                "usage": "supplier",
            }
        )
        cls.location_stock = cls.env["stock.location"].create(
            {
                "name": "Test Stock Location",
                "barcode": "LOC-STOCK-001",
                "usage": "internal",
            }
        )
        cls.location_shelf_a = cls.env["stock.location"].create(
            {
                "name": "Test Shelf A",
                "barcode": "LOC-SHELF-A",
                "usage": "internal",
                "location_id": cls.location_stock.id,
            }
        )
        cls.location_shelf_b = cls.env["stock.location"].create(
            {
                "name": "Test Shelf B",
                "barcode": "LOC-SHELF-B",
                "usage": "internal",
                "location_id": cls.location_stock.id,
            }
        )
        cls.location_customer = cls.env["stock.location"].create(
            {
                "name": "Test Customer Location",
                "barcode": "LOC-CUSTOMER-001",
                "usage": "customer",
            }
        )

    @classmethod
    def _setup_products(cls):
        """Create products with different tracking types"""
        cls.product_none_a = cls.env["product.product"].create(
            {
                "name": "Product No Tracking A",
                "type": "product",
                "tracking": "none",
                "barcode": "PROD-NONE-A",
            }
        )
        cls.product_none_b = cls.env["product.product"].create(
            {
                "name": "Product No Tracking B",
                "type": "product",
                "tracking": "none",
                "barcode": "PROD-NONE-B",
            }
        )
        cls.product_none_c = cls.env["product.product"].create(
            {
                "name": "Product No Tracking C",
                "type": "product",
                "tracking": "none",
                "barcode": "PROD-NONE-C",
            }
        )

        cls.product_lot_a = cls.env["product.product"].create(
            {
                "name": "Product Lot Tracking A",
                "type": "product",
                "tracking": "lot",
                "barcode": "PROD-LOT-A",
            }
        )
        cls.product_lot_b = cls.env["product.product"].create(
            {
                "name": "Product Lot Tracking B",
                "type": "product",
                "tracking": "lot",
                "barcode": "PROD-LOT-B",
            }
        )
        cls.product_lot_c = cls.env["product.product"].create(
            {
                "name": "Product Lot Tracking C",
                "type": "product",
                "tracking": "lot",
                "barcode": "PROD-LOT-C",
            }
        )

        cls.product_serial_a = cls.env["product.product"].create(
            {
                "name": "Product Serial Tracking A",
                "type": "product",
                "tracking": "serial",
                "barcode": "PROD-SERIAL-A",
            }
        )
        cls.product_serial_b = cls.env["product.product"].create(
            {
                "name": "Product Serial Tracking B",
                "type": "product",
                "tracking": "serial",
                "barcode": "PROD-SERIAL-B",
            }
        )
        cls.product_serial_c = cls.env["product.product"].create(
            {
                "name": "Product Serial Tracking C",
                "type": "product",
                "tracking": "serial",
                "barcode": "PROD-SERIAL-C",
            }
        )

    @classmethod
    def _setup_lots_and_serials(cls):
        """Create lots and serials for tracked products"""
        # Lots for product A
        cls.lot_a1 = cls.env["stock.lot"].create(
            {
                "name": "LOT-A-001",
                "product_id": cls.product_lot_a.id,
                "company_id": cls.env.company.id,
            }
        )
        cls.lot_a2 = cls.env["stock.lot"].create(
            {
                "name": "LOT-A-002",
                "product_id": cls.product_lot_a.id,
                "company_id": cls.env.company.id,
            }
        )

        # Lots for product B
        cls.lot_b1 = cls.env["stock.lot"].create(
            {
                "name": "LOT-B-001",
                "product_id": cls.product_lot_b.id,
                "company_id": cls.env.company.id,
            }
        )
        cls.lot_b2 = cls.env["stock.lot"].create(
            {
                "name": "LOT-B-002",
                "product_id": cls.product_lot_b.id,
                "company_id": cls.env.company.id,
            }
        )

        # Lots for product C
        cls.lot_c1 = cls.env["stock.lot"].create(
            {
                "name": "LOT-C-001",
                "product_id": cls.product_lot_c.id,
                "company_id": cls.env.company.id,
            }
        )
        cls.lot_c2 = cls.env["stock.lot"].create(
            {
                "name": "LOT-C-002",
                "product_id": cls.product_lot_c.id,
                "company_id": cls.env.company.id,
            }
        )

        # Serials for product A
        cls.serial_a1 = cls.env["stock.lot"].create(
            {
                "name": "SN-A-001",
                "product_id": cls.product_serial_a.id,
                "company_id": cls.env.company.id,
            }
        )
        cls.serial_a2 = cls.env["stock.lot"].create(
            {
                "name": "SN-A-002",
                "product_id": cls.product_serial_a.id,
                "company_id": cls.env.company.id,
            }
        )
        cls.serial_a3 = cls.env["stock.lot"].create(
            {
                "name": "SN-A-003",
                "product_id": cls.product_serial_a.id,
                "company_id": cls.env.company.id,
            }
        )

        # Serials for product B
        cls.serial_b1 = cls.env["stock.lot"].create(
            {
                "name": "SN-B-001",
                "product_id": cls.product_serial_b.id,
                "company_id": cls.env.company.id,
            }
        )
        cls.serial_b2 = cls.env["stock.lot"].create(
            {
                "name": "SN-B-002",
                "product_id": cls.product_serial_b.id,
                "company_id": cls.env.company.id,
            }
        )
        cls.serial_b3 = cls.env["stock.lot"].create(
            {
                "name": "SN-B-003",
                "product_id": cls.product_serial_b.id,
                "company_id": cls.env.company.id,
            }
        )

        # Serials for product C
        cls.serial_c1 = cls.env["stock.lot"].create(
            {
                "name": "SN-C-001",
                "product_id": cls.product_serial_c.id,
                "company_id": cls.env.company.id,
            }
        )
        cls.serial_c2 = cls.env["stock.lot"].create(
            {
                "name": "SN-C-002",
                "product_id": cls.product_serial_c.id,
                "company_id": cls.env.company.id,
            }
        )
        cls.serial_c3 = cls.env["stock.lot"].create(
            {
                "name": "SN-C-003",
                "product_id": cls.product_serial_c.id,
                "company_id": cls.env.company.id,
            }
        )

    @classmethod
    def _setup_targets(cls):
        """Get or create barcode targets"""
        cls.target_product = cls.env.ref(
            "stock_barcode_oca.target_product", raise_if_not_found=False
        )
        if not cls.target_product:
            cls.target_product = cls.env["stock.barcode.app.target"].create(
                {
                    "name": "Product",
                    "technical_name": "product",
                    "description": "Product to scan",
                }
            )

        cls.target_lot = cls.env.ref(
            "stock_barcode_oca.target_lot", raise_if_not_found=False
        )
        if not cls.target_lot:
            cls.target_lot = cls.env["stock.barcode.app.target"].create(
                {
                    "name": "Lot/Serial",
                    "technical_name": "lot",
                    "description": "Lot or serial number",
                }
            )

        cls.target_source_location = cls.env.ref(
            "stock_barcode_oca.target_source_location", raise_if_not_found=False
        )
        if not cls.target_source_location:
            cls.target_source_location = cls.env["stock.barcode.app.target"].create(
                {
                    "name": "Source Location",
                    "technical_name": "source_location",
                    "description": "Source location",
                }
            )

        cls.target_dest_location = cls.env.ref(
            "stock_barcode_oca.target_destination_location", raise_if_not_found=False
        )
        if not cls.target_dest_location:
            cls.target_dest_location = cls.env["stock.barcode.app.target"].create(
                {
                    "name": "Destination Location",
                    "technical_name": "destination_location",
                    "description": "Destination location",
                }
            )

        cls.target_package = cls.env.ref(
            "stock_barcode_oca.target_package", raise_if_not_found=False
        )
        if not cls.target_package:
            cls.target_package = cls.env["stock.barcode.app.target"].create(
                {
                    "name": "Package",
                    "technical_name": "package",
                    "description": "Package identifier",
                }
            )

    @classmethod
    def _setup_nomenclature(cls):
        """Get default nomenclature"""
        cls.nomenclature = cls.env.ref("barcodes.default_barcode_nomenclature")

    def _create_move(self, picking, product, quantity):
        """Helper to create a stock move"""
        return self.env["stock.move"].create(
            {
                "name": product.name,
                "product_id": product.id,
                "product_uom_qty": quantity,
                "product_uom": product.uom_id.id,
                "picking_id": picking.id,
                "location_id": picking.location_id.id,
                "location_dest_id": picking.location_dest_id.id,
            }
        )

    @classmethod
    def _create_quant_for_serial(cls, serial, location, quantity=1.0):
        """Helper: creates stock quant for a serial in a location"""
        return cls.env["stock.quant"].create(
            {
                "product_id": serial.product_id.id,
                "location_id": location.id,
                "lot_id": serial.id,
                "quantity": quantity,
                "reserved_quantity": 0.0,
            }
        )

    @classmethod
    def _create_quants_for_serials(cls, serials, location):
        """Helper: creates quants for multiple serials"""
        for serial in serials:
            cls._create_quant_for_serial(serial, location)

    def _assert_scan_success(self, result, message_fragment=None):
        """Assert scan was successful"""
        self.assertTrue(
            result.get("success"),
            f"Scan failed: {result.get('message', 'No message')}",
        )
        if message_fragment:
            self.assertIn(
                message_fragment.lower(),
                result.get("message", "").lower(),
                f"Expected '{message_fragment}' in message: {result.get('message')}",
            )

    def _assert_scan_failed(self, result, expected_error=None):
        """Assert scan failed with expected error"""
        self.assertFalse(
            result.get("success"), f"Scan should have failed but succeeded: {result}"
        )
        if expected_error:
            self.assertIn(
                expected_error.lower(),
                result.get("message", "").lower(),
                f"Expected error '{expected_error}' not in message: "
                f"{result.get('message')}",
            )

    def _assert_quantity_picked(self, picking, product, expected_qty):
        """Assert picked quantity for a product"""
        state = picking._get_scan_state()
        picked_quantities = state.get("scanned_context", {}).get(
            "picked_quantities", {}
        )
        move = picking.move_ids.filtered(lambda m: m.product_id == product)
        self.assertEqual(
            len(move),
            1,
            f"Expected exactly one move for product {product.name}",
        )
        actual_qty = picked_quantities.get(str(move.id), 0.0)
        self.assertEqual(
            actual_qty,
            expected_qty,
            f"Expected {expected_qty} for {product.name}, got {actual_qty}",
        )

    def _assert_context_product(self, picking, expected_product):
        """Assert context has expected product"""
        state = picking._get_scan_state()
        context_product_id = state.get("scanned_context", {}).get("product_id")
        self.assertEqual(
            context_product_id,
            expected_product.id if expected_product else None,
            f"Expected product"
            f"{expected_product.name if expected_product else None} in context",
        )

    def _assert_context_lot(self, picking, expected_lot):
        """Assert context has expected lot"""
        state = picking._get_scan_state()
        context_lot_id = state.get("scanned_context", {}).get("lot_id")
        self.assertEqual(
            context_lot_id,
            expected_lot.id if expected_lot else None,
            f"Expected lot {expected_lot.name if expected_lot else None} in context",
        )

    def _assert_step_is_final(self, picking):
        """Assert current step is final"""
        state = picking._get_scan_state()
        current_step = self.env["stock.barcode.app.profile.target.line"].browse(
            state.get("current_step_id")
        )
        self.assertEqual(
            current_step.step_type,
            "final",
            f"Expected final step, got {current_step.step_type}",
        )
