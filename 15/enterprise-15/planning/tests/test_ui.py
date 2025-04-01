# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import logging

from odoo.tests import HttpCase, tagged, loaded_demo_data

_logger = logging.getLogger(__name__)


@tagged('-at_install', 'post_install')
class TestUi(HttpCase):
    def test_01_ui(self):
        if not loaded_demo_data(self.env):
            _logger.warning("This test relies on demo data. To be rewritten independently of demo data for accurate and reliable results.")
            return
        self.start_tour("/", 'planning_test_tour', login='admin')
