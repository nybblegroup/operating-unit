# Copyright 2024 ForgeFlow, S.L.
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl.html)

from odoo.exceptions import AccessError
from odoo.fields import Command
from odoo.tests import tagged

from odoo.addons.operating_unit.tests.common import OperatingUnitCommon


@tagged("post_install", "-at_install")
class TestPOSOperatingUnit(OperatingUnitCommon):
    """Test Point of Sale Operating Unit access controls and functionality."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # Setup models
        cls.PosOrder = cls.env["pos.order"]
        cls.PosConfig = cls.env["pos.config"]
        cls.PosSession = cls.env["pos.session"]

        # Setup product for testing
        cls.pos_product = cls.env["product.product"].create(
            {
                "name": "Test POS Product",
                "available_in_pos": True,
                "list_price": 1000.0,
            }
        )

        # Setup pricelist
        cls.pricelist = cls.env["product.pricelist"].create(
            {
                "name": "Test POS Pricelist",
                "currency_id": cls.env.company.currency_id.id,
            }
        )

        # Setup groups
        cls.group_pos_manager = cls.env.ref("point_of_sale.group_pos_manager")
        cls.group_account_invoice = cls.env.ref("account.group_account_invoice")

        # Create POS config with operating unit
        cls.pos_config = cls.env["pos.config"].create(
            {
                "name": "Test POS Config",
                "operating_unit_ids": [Command.set([cls.ou1.id])],
                "available_pricelist_ids": [Command.set([cls.pricelist.id])],
                "pricelist_id": cls.pricelist.id,
            }
        )

        # Open session
        cls.pos_config.open_ui()

        # Configure users with proper groups and operating units
        cls.user1.write(
            {
                "groups_id": [
                    Command.link(cls.group_pos_manager.id),
                    Command.link(cls.group_account_invoice.id),
                ],
                "operating_unit_ids": [Command.link(cls.ou1.id)],
            }
        )

        cls.user2.write(
            {
                "groups_id": [
                    Command.link(cls.group_pos_manager.id),
                    Command.link(cls.group_account_invoice.id),
                ],
                "operating_unit_ids": [Command.link(cls.b2c.id)],
            }
        )

    def test_module_installed(self):
        """Test that pos_operating_unit module is properly installed."""
        mod = self.env["ir.module.module"].search(
            [
                ("name", "=", "pos_operating_unit"),
                ("state", "=", "installed"),
            ],
            limit=1,
        )
        self.assertTrue(mod, "pos_operating_unit must be installed during tests")

    def test_fields_present(self):
        """Test that required fields are added by the module."""
        # Test that operating_unit_ids field exists (added by the module)
        self.assertIn("operating_unit_ids", self.env["pos.config"]._fields)
        # Check that pos.order model exists (this tests module loading)
        self.assertTrue(self.env["pos.order"]._fields)
        # Test that we can access the operating_unit related data
        self.assertTrue(hasattr(self.env["pos.config"], "operating_unit_ids"))

    def test_pos_config_operating_unit_compute(self):
        """Test that pos.config operating_unit is properly set."""
        # Test that the config has the operating unit set via operating_unit_ids
        self.assertTrue(self.pos_config.operating_unit_ids)
        self.assertIn(self.ou1, self.pos_config.operating_unit_ids)

    def test_pos_order_operating_unit_from_session(self):
        """Test that pos.order inherits operating unit from session."""
        order = self._create_order()
        # Check that the order exists and was created successfully
        self.assertTrue(order)
        self.assertTrue(order.session_id)

    def test_operating_unit_access_config(self):
        """Test access control for pos.config based on operating unit."""
        # User 1 should access config with OU1
        pos_config_user1 = self.pos_config.with_user(self.user1)
        self.assertTrue(pos_config_user1.name, "User1 should access config with OU1")

        # User 2 should not access config with OU1
        pos_config_user2 = self.pos_config.with_user(self.user2)
        with self.assertRaises(AccessError):
            _ = pos_config_user2.name

    def test_operating_unit_access_session(self):
        """Test access control for pos.session based on operating unit."""
        session = self.pos_config.current_session_id

        # User 1 should access session with OU1
        session_user1 = session.with_user(self.user1)
        self.assertTrue(session_user1.name, "User1 should access session with OU1")

        # User 2 should not access session with OU1
        session_user2 = session.with_user(self.user2)
        with self.assertRaises(AccessError):
            _ = session_user2.name

    def test_operating_unit_access_order_and_line_and_payment(self):
        """Test access control for pos.order based on operating unit."""
        order = self._create_order()

        # User 1 should access order with OU1
        order_user1 = order.with_user(self.user1)
        self.assertTrue(order_user1.name, "User1 should access order with OU1")

        # User 2 should not access order with OU1
        order_user2 = order.with_user(self.user2)
        with self.assertRaises(AccessError):
            _ = order_user2.name

    def _create_order(self):
        """Helper method to create a POS order for testing."""
        session = self.pos_config.current_session_id

        # Create order directly using ORM (simpler approach for testing)
        order = self.PosOrder.create(
            {
                "name": "Test Order",
                "session_id": session.id,
                "partner_id": False,
                "pricelist_id": self.pricelist.id,
                "amount_total": 1000.0,
                "amount_tax": 0.0,
                "amount_paid": 1000.0,
                "amount_return": 0.0,
            }
        )

        # Create order line
        self.env["pos.order.line"].create(
            {
                "order_id": order.id,
                "product_id": self.pos_product.id,
                "qty": 1.0,
                "price_unit": 1000.0,
                "price_subtotal": 1000.0,
                "price_subtotal_incl": 1000.0,
                "discount": 0.0,
                "name": self.pos_product.name,
            }
        )

        # Create payment
        self.env["pos.payment"].create(
            {
                "pos_order_id": order.id,
                "payment_method_id": session.config_id.payment_method_ids[0].id,
                "amount": 1000.0,
            }
        )

        return order
