# Copyright 2024 Ariel Loustaunau
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo.exceptions import UserError
from odoo.tests import tagged

from .test_common import BarcodeTestCommon


@tagged("post_install", "-at_install")
class TestButtonValidate(BarcodeTestCommon):
    """Test button_validate after barcode scanning"""

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

    def test_button_validate_after_scanning_products_no_tracking(self):
        """Test: Scan products without tracking, then validate picking"""
        picking = self._create_reception(
            [
                (self.product_none_a, 2),
                (self.product_none_b, 1),
            ]
        )

        # Scan Product A twice
        result = picking.process_scanned_barcode("PROD-NONE-A")
        self.assertTrue(result["success"])
        result = picking.process_scanned_barcode("PROD-NONE-A")
        self.assertTrue(result["success"])

        # Scan Product B once
        result = picking.process_scanned_barcode("PROD-NONE-B")
        self.assertTrue(result["success"])

        # Check quantities are correct
        self._assert_quantity_picked(picking, self.product_none_a, 2)
        self._assert_quantity_picked(picking, self.product_none_b, 1)

        # Verify move_lines
        self.assertEqual(len(picking.move_line_ids), 2, "Should have 2 move lines")

        # Try to validate picking
        try:
            picking.button_validate()
            self.assertEqual(picking.state, "done", "Picking should be validated")
        except Exception as e:
            self.fail(f"button_validate failed for products without tracking: {e}")

    def test_button_validate_after_scanning_lots(self):
        """Test: Scan products with lot tracking, then validate picking"""
        picking = self._create_reception(
            [
                (self.product_lot_a, 3),
                (self.product_lot_b, 2),
            ]
        )

        # Scan Product A with LOT-A-001 (3 times)
        result = picking.process_scanned_barcode("PROD-LOT-A")
        self.assertTrue(result["success"])
        result = picking.process_scanned_barcode("LOT-A-NEW-001")
        self.assertTrue(result["success"])

        result = picking.process_scanned_barcode("PROD-LOT-A")
        self.assertTrue(result["success"])
        result = picking.process_scanned_barcode("LOT-A-NEW-001")
        self.assertTrue(result["success"])

        result = picking.process_scanned_barcode("PROD-LOT-A")
        self.assertTrue(result["success"])
        result = picking.process_scanned_barcode("LOT-A-NEW-001")
        self.assertTrue(result["success"])

        # Scan Product B with LOT-B-001 (2 times)
        result = picking.process_scanned_barcode("PROD-LOT-B")
        self.assertTrue(result["success"])
        result = picking.process_scanned_barcode("LOT-B-NEW-001")
        self.assertTrue(result["success"])

        result = picking.process_scanned_barcode("PROD-LOT-B")
        self.assertTrue(result["success"])
        result = picking.process_scanned_barcode("LOT-B-NEW-001")
        self.assertTrue(result["success"])

        # Check quantities
        self._assert_quantity_picked(picking, self.product_lot_a, 3)
        self._assert_quantity_picked(picking, self.product_lot_b, 2)

        # CRITICAL: Verify lot_name is set when qty_picked >= 1 for tracked products
        for ml in picking.move_line_ids:
            if ml.qty_picked >= 1 and ml.product_id.tracking in ("lot", "serial"):
                self.assertTrue(
                    ml.lot_name,
                    f"CRITICAL: lot_name must be set "
                    f"when qty_picked={ml.qty_picked} >= 1 "
                    f"for product={ml.product_id.name} with "
                    f"tracking={ml.product_id.tracking}. "
                    f"Found lot_name='{ml.lot_name}' (empty!)",
                )
                # Verify lot_id is also set
                self.assertTrue(
                    ml.lot_id,
                    f"lot_id must be set when qty_picked"
                    f" >= 1 for tracked product {ml.product_id.name}",
                )

        # Check for duplicate lines
        lines_by_product = {}
        for ml in picking.move_line_ids:
            key = (ml.product_id.id, ml.lot_id.id if ml.lot_id else False)
            if key in lines_by_product:
                lines_by_product[key].append(ml)
            else:
                lines_by_product[key] = [ml]

        # Report duplicates
        for _, lines in lines_by_product.items():
            if len(lines) > 1:
                product = lines[0].product_id
                lot = lines[0].lot_id
                self.fail(
                    f"DUPLICATE LINES for product={product.name}, "
                    f"lot={lot.name if lot else 'NO_LOT'}: "
                    f"{len(lines)} lines with ids={[ml.id for ml in lines]}"
                )

        # Try to validate picking
        try:
            picking.button_validate()
            self.assertEqual(picking.state, "done", "Picking should be validated")
        except UserError as e:
            self.fail(f"button_validate failed for lots: {e}")

    def test_button_validate_after_scanning_serials(self):
        """Test: Scan products with serial tracking, then validate picking"""
        picking = self._create_reception(
            [
                (self.product_serial_a, 2),
            ]
        )

        # Scan Product A with SERIAL-A-001
        result = picking.process_scanned_barcode("PROD-SERIAL-A")
        self.assertTrue(result["success"])
        result = picking.process_scanned_barcode("SERIAL-A-NEW-001")
        self.assertTrue(result["success"])

        # Scan Product A with SERIAL-A-002
        result = picking.process_scanned_barcode("PROD-SERIAL-A")
        self.assertTrue(result["success"])
        result = picking.process_scanned_barcode("SERIAL-A-NEW-002")
        self.assertTrue(result["success"])

        # Check quantity
        self._assert_quantity_picked(picking, self.product_serial_a, 2)

        # CRITICAL: Verify lot_name is set when qty_picked >= 1 for serials
        for ml in picking.move_line_ids:
            if ml.qty_picked >= 1 and ml.product_id.tracking == "serial":
                self.assertTrue(
                    ml.lot_name,
                    f"CRITICAL: lot_name must be set "
                    f"when qty_picked={ml.qty_picked} >= 1 "
                    f"for product={ml.product_id.name} with tracking=serial. "
                    f"Found lot_name='{ml.lot_name}' (empty!)",
                )
                # Verify lot_id is also set
                self.assertTrue(
                    ml.lot_id,
                    f"lot_id must be set when qty_picked >= 1 "
                    f"for serial product {ml.product_id.name}",
                )

        # Check for duplicate lines
        lines_by_serial = {}
        for ml in picking.move_line_ids:
            key = (ml.product_id.id, ml.lot_id.id if ml.lot_id else False)
            if key in lines_by_serial:
                lines_by_serial[key].append(ml)
            else:
                lines_by_serial[key] = [ml]

        for _, lines in lines_by_serial.items():
            if len(lines) > 1:
                product = lines[0].product_id
                serial = lines[0].lot_id
                self.fail(
                    f"DUPLICATE LINES for product={product.name}, "
                    f"serial={serial.name if serial else 'NO_SERIAL'}: "
                    f"{len(lines)} lines with ids={[ml.id for ml in lines]}"
                )

        # Try to validate picking
        try:
            picking.button_validate()
            self.assertEqual(picking.state, "done", "Picking should be validated")
        except UserError as e:
            self.fail(f"button_validate failed for serials: {e}")
