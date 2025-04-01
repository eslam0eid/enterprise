# -*- coding: utf-8 -*-

from odoo.tests.common import TransactionCase, Form

from datetime import date
from freezegun import freeze_time

class TestProjectRecurrenceEnterprise(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super(TestProjectRecurrenceEnterprise, cls).setUpClass()
        cls.stage_a, cls.stage_b = cls.env['project.task.type'].create([
            {'name': 'a'},
            {'name': 'b'},
        ])
        cls.project_recurring = cls.env['project.project'].with_context({'mail_create_nolog': True}).create({
            'name': 'Recurring',
            'allow_recurring_tasks': True,
            'type_ids': [
                (4, cls.stage_a.id),
                (4, cls.stage_b.id),
            ]
        })

    def test_recurrence_with_planned_date_01(self):
        """
            Check that the planning date on the task is taken into account
            when calculating the date on which the next recurrence will be generated.
        """
        with freeze_time("2023-10-15"):
            with Form(self.env['project.task']) as form:
                form.name = 'test recurring task'
                form.project_id = self.project_recurring

                form.recurring_task = True
                form.repeat_interval = 6
                form.repeat_unit = 'month'
                form.repeat_type = 'forever'
                form.repeat_on_month = 'date'
                form.repeat_day = '1'
                form.recurrence_update = 'all'

                form.planned_date_begin = '2023-09-12 06:50:00'
                task = form.save()
            self.assertEqual(task.recurrence_id.next_recurrence_date, date(2024, 3, 1)) # And not date(2024, 4, 1) which is the date calculated from the current day

    def test_recurrence_with_planned_date_02(self):
        """
            Check that the planning date on the task is taken into account
            when calculating the date on which the next recurrence will be generated.
        """
        with freeze_time("2023-10-15"):
            with Form(self.env['project.task']) as form:
                form.name = 'test recurring task'
                form.project_id = self.project_recurring

                form.recurring_task = True
                form.repeat_interval = 1
                form.repeat_unit = 'month'
                form.repeat_type = 'until'
                form.repeat_until = '2024-07-11'
                form.repeat_on_month = 'date'
                form.repeat_day = '1'
                form.recurrence_update = 'all'

                form.planned_date_begin = '2023-07-11 06:50:00'
                task = form.save()
            # 08/01/2023
            # 09/01/2023
            # 10/01/2023
            # 11/01/2023 --> first date after tomorrow
            # 12/01/2023
            # ...
            self.assertEqual(task.recurrence_id.next_recurrence_date, date(2023, 11, 1))

    def test_recurrence_with_planned_date_03(self):
        with freeze_time("2023-10-15"):
            with Form(self.env['project.task']) as form:
                form.name = 'test recurring task'
                form.project_id = self.project_recurring

                form.recurring_task = True
                form.repeat_interval = 1
                form.repeat_unit = 'day'
                form.repeat_type = 'until'
                form.repeat_until = '2024-07-11'
                form.repeat_on_month = 'date'
                form.repeat_day = '1'
                form.recurrence_update = 'all'

                form.planned_date_begin = '2023-07-11 06:50:00'
                task = form.save()
            # Tomorrow even if there is an anterior date begin
            self.assertEqual(task.recurrence_id.next_recurrence_date, date(2023, 10, 16))

    def test_recurrence_with_planned_date_04(self):
        """
            Check if there is no error during comparison with tomorrow's date
            to select the next recurrence.
            Note: `freezegun` uses the `FakeDate` or `FakeDatetime` type
            Note 2: no assert because it uses the system date, which will vary
        """
        with Form(self.env['project.task']) as form:
            form.name = 'test recurring task'
            form.project_id = self.project_recurring

            form.recurring_task = True
            form.repeat_interval = 1
            form.repeat_unit = 'day'
            form.repeat_type = 'forever'
            form.recurrence_update = 'all'

            form.planned_date_begin = '2023-07-11 06:50:00'
            form.save()
