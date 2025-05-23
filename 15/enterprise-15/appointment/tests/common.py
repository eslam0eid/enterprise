# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from contextlib import contextmanager
from datetime import date, datetime
from unittest.mock import patch

from odoo.addons.appointment.models.res_partner import Partner
from odoo.addons.calendar.models.calendar_event import Meeting
from odoo.addons.resource.models.resource import ResourceCalendar
from odoo.addons.mail.tests.common import mail_new_test_user, MailCommon


class AppointmentCommon(MailCommon):

    @classmethod
    def setUpClass(cls):
        super(AppointmentCommon, cls).setUpClass()

        # give default values for all email aliases and domain
        cls._init_mail_gateway()
        # ensure admin configuration
        cls.admin_user = cls.env.ref('base.user_admin')
        cls.admin_user.write({
            'country_id': cls.env.ref('base.be').id,
            'login': 'admin',
            'notification_type': 'inbox',
            'tz': "Europe/Brussels",
        })
        cls.company_admin = cls.admin_user.company_id
        # set country in order to format Belgian numbers
        cls.company_admin.write({
            'country_id': cls.env.ref('base.be').id,
        })

        # reference dates to have reproducible tests (sunday evening, allowing full week)
        cls.reference_now = datetime(2022, 2, 13, 20, 0, 0)
        cls.reference_monday = datetime(2022, 2, 14, 7, 0, 0)
        cls.reference_now_monthweekstart = date(2022, 1, 31)  # starts on a Monday, first week containing Feb day

        cls.apt_manager = mail_new_test_user(
            cls.env,
            company_id=cls.company_admin.id,
            email='apt_manager@test.example.com',
            groups='base.group_user,appointment.group_calendar_manager',
            name='Appointment Manager',
            notification_type='email',
            login='apt_manager',
            tz='Europe/Brussels'
        )
        cls.apt_manager_employee = cls.env['hr.employee'].create({
            'company_id': cls.apt_manager.company_id.id,
            'user_id': cls.apt_manager.id,
        })
        cls.staff_user_bxls = mail_new_test_user(
            cls.env,
            company_id=cls.company_admin.id,
            email='brussels@test.example.com',
            groups='base.group_user',
            name='Employee Brussels',
            notification_type='email',
            login='staff_user_bxls',
            tz='Europe/Brussels'  # UTC + 1 (at least in February)
        )
        cls.staff_user_aust = mail_new_test_user(
            cls.env,
            company_id=cls.company_admin.id,
            email='australia@test.example.com',
            groups='base.group_user',
            name='Employee Australian',
            notification_type='email',
            login='staff_user_aust',
            tz='Australia/West'  # UTC + 8 (at least in February)
        )

        # Move to appointment_hr in post 15.2
        # ------------------------------------------------------------

        # Calendars: 8-12, 13-17 (UTC + 1)
        cls.resource_calendar_2days = cls.env['resource.calendar'].create({
            'attendance_ids': [
                (0, 0, {'dayofweek': weekday,
                        'day_period': 'morning',
                        'hour_from': hour,
                        'hour_to': hour + 4,
                        'name': 'Day %s H %d %d' % (weekday, hour, hour + 4),
                       })
                for weekday in ['0', '1']
                for hour in [8, 13]
            ],
            'company_id': cls.company_admin.id,
            'name': 'Light Calendars',
            'tz': 'Europe/Brussels',
        })

        # User resources and employees for work intervals
        cls.staff_resources = cls.env['resource.resource'].create([
            {'calendar_id': cls.resource_calendar_2days.id,
             'company_id': cls.staff_user_bxls.company_id.id,
             'name': cls.staff_user_bxls.name,
             'user_id': cls.staff_user_bxls.id,
             'tz': cls.staff_user_bxls.tz,
            },
            {'calendar_id': cls.resource_calendar_2days.id,
             'company_id': cls.staff_user_aust.company_id.id,
             'name': cls.staff_user_aust.name,
             'user_id': cls.staff_user_aust.id,
             'tz': cls.staff_user_aust.tz,
            }
        ])
        cls.staff_employees = cls.env['hr.employee'].create([
            {'company_id': cls.staff_user_bxls.company_id.id,
             'resource_calendar_id': cls.resource_calendar_2days.id,
             'resource_id': cls.staff_resources[0].id,
            },
            {'company_id': cls.staff_user_aust.company_id.id,
             'resource_calendar_id': cls.resource_calendar_2days.id,
             'resource_id': cls.staff_resources[1].id,
            }
        ])
        cls.staff_resource_bxls, cls.staff_resource_aust = cls.staff_resources[0], cls.staff_resources[1]
        cls.staff_employee_bxls, cls.staff_employee_aust = cls.staff_employees[0], cls.staff_employees[1]

        # Default (test) appointment type
        # Slots are each hours from 8 to 13 (UTC + 1)
        # -> working hours: 7, 8, 9, 10 and 12 UTC as 11 is lunch time in working hours
        cls.apt_type_bxls_2days = cls.env['calendar.appointment.type'].create({
            'appointment_tz': 'Europe/Brussels',
            'appointment_duration': 1,
            'assign_method': 'random',
            'category': 'website',
            'employee_ids': [(4, cls.staff_employee_bxls.id)],
            'location': 'Bxls Office',
            'name': 'Bxls Appt Type',
            'max_schedule_days': 15,
            'min_cancellation_hours': 1,
            'min_schedule_hours': 1,
            'slot_ids': [
                (0, False, {'weekday': weekday,
                            'start_hour': hour,
                            'end_hour': hour + 1,
                           })
                for weekday in ['1', '2']
                for hour in range(8, 14)
            ],
        })

    def _create_meetings(self, user, time_info):
        return self.env['calendar.event'].with_context(self._test_context).create([
            {'allday': allday,
             'attendee_ids': [(0, 0, {'partner_id': user.partner_id.id})],
             'name': 'Event for %s (%s / %s - %s)' % (user.name, allday, start, stop),
             'partner_ids': [(4, user.partner_id.id)],
             'start': start,
             'stop': stop,
             'user_id': user.id,
            }
            for start, stop, allday in time_info
        ])

    def _create_leaves(self, user, time_info, **kw):
        return self.env['resource.calendar.leaves'].sudo().with_context(self._test_context).create([
            {'calendar_id': kw['calendar'].id if 'calendar' in kw else user.resource_calendar_id.id,
             'company_id': user.company_id.id,
             'date_from': date_from,
             'date_to': date_to,
             'name': 'Leave for %s (%s - %s)' % (user.name, date_from, date_to),
             'resource_id': kw['resource'].id if 'resource' in kw else (user.resource_ids and user.resource_ids[0].id or False),
             'time_type': 'leave',
            }
            for date_from, date_to in time_info
        ])

    def _filter_appointment_slots(self, slots, filter_months=False, filter_weekdays=False, filter_employees=False):
        """ Get all the slots info computed.
        Can target a part of slots by referencing the expected months or days we want.
        :param list slots: slots content computed from _get_appointment_slots() method.
        :param list filter_months: list of tuples representing months we want to check
            [(2, 2022), ...] where (2, 2022) represents February 2022
        :param list filter_weekdays: list of integers of the weekdays we want to check 0 = monday and 6 = sunday
            [0, 1, 3] to filter only monday, tuesday and thursday slots
        :param recordset filter_employees: recordset of employees for which we want to get slots when they are available
        :return list: [{
            'datetime': '2022-02-14 08:00:00',
            'duration': '1.0',
            'employee_id': 21,
            'hours': '08:00 - 09:00',
        }, ...] """
        slots_info = []
        for month in slots:
            # We use the last day of the first week to be sure that we use the correct month
            last_day_first_week = month['weeks'][0][-1]['day']
            month_tuple = (last_day_first_week.month, last_day_first_week.year)
            if filter_months and month_tuple not in filter_months:
                continue
            for week in month['weeks']:
                for day in week:
                    if not day['slots'] or (filter_weekdays and day['day'].weekday() not in filter_weekdays):
                        continue
                    for slot in day['slots']:
                        if filter_employees and slot.get('employee_id') not in filter_employees.ids:
                            continue
                        slots_info.append(slot)
        return slots_info

    def _flush_tracking(self):
        """ Force the creation of tracking values notably, and ensure tests are
        reproducible. """
        self.env['base'].flush()
        self.cr.flush()

    def assertSlots(self, slots, exp_months, slots_data):
        """ Check slots content. Method to be improved soon, currently doing
        only basic checks. """
        self.assertEqual(len(slots), len(exp_months), 'Slots: wrong number of covered months')
        self.assertEqual(slots[0]['weeks'][0][0]['day'], slots_data['startdate'], 'Slots: wrong starting date')
        self.assertEqual(slots[-1]['weeks'][-1][-1]['day'], slots_data['enddate'], 'Slots: wrong ending date')
        for month, expected_month in zip(slots, exp_months):
            self.assertEqual(month['month'], expected_month['name_formated'])
            self.assertEqual(len(month['weeks']), expected_month['weeks_count'])
            if not slots_data.get('slots_startdate'):  # not all tests are detailed
                continue

            # global slots configuration
            slots_days_leave = slots_data.get('slots_days_leave', [])
            slots_enddate = slots_data.get('slots_enddate')
            slots_startdate = slots_data.get('slots_startdate')
            slots_weekdays_nowork = slots_data.get('slots_weekdays_nowork', [])

            # slots specific
            slots_start_hours = slots_data.get('slots_start_hours', [])

            for week in month['weeks']:
                for day in week:
                    day_date = day['day']
                    # days linked to "next month" or "previous month" are there for filling but have no slots
                    is_void = day_date.month != expected_month['month_date'].month

                    # before reference date: no slots generated (just there to fill up calendar)
                    is_working = day_date >= slots_startdate
                    if is_working and slots_enddate:
                        is_working = day_date <= slots_enddate
                    if is_working:
                        is_working = day_date not in slots_days_leave
                    if is_working:
                        is_working = day_date.weekday() not in slots_weekdays_nowork
                    # after end date: no slots generated (just there to fill up calendar)

                    # standard day: should have slots according to apt type slots hours
                    if not is_void and is_working:
                        if day_date in slots_data.get('slots_day_specific', {}):
                            slot_count = len(slots_data['slots_day_specific'][day_date])
                            slot_start_hours = [slot['start'] for slot in slots_data['slots_day_specific'][day_date]]
                        else:
                            slot_count = len(slots_start_hours)
                            slot_start_hours = slots_start_hours
                        self.assertEqual(
                            len(day['slots']), slot_count,
                            'Slot: wrong number of slots for %s' % day
                        )
                        self.assertEqual(
                            [datetime.strptime(slot['datetime'], '%Y-%m-%d %H:%M:%S').hour for slot in day['slots']],
                            slot_start_hours,
                            'Slot: wrong starting hours'
                        )
                    elif is_void:
                        self.assertFalse(len(day['slots']), 'Slot: out of range should have no slot for %s' % day)
                    else:
                        self.assertFalse(len(day['slots']), 'Slot: not worked should have no slot for %s' % day)

    @contextmanager
    def mockAppointmentCalls(self):
        _original_search = Meeting.search
        _original_search_count = Meeting.search_count
        _original_calendar_verify_availability = Partner.calendar_verify_availability
        _original_work_intervals_batch = ResourceCalendar._work_intervals_batch
        with patch.object(Meeting, 'search',
                          autospec=True, side_effect=_original_search) as mock_ce_search, \
             patch.object(Meeting, 'search_count',
                          autospec=True, side_effect=_original_search_count) as mock_ce_sc, \
             patch.object(Partner, 'calendar_verify_availability',
                          autospec=True, side_effect=_original_calendar_verify_availability) as mock_partner_cal, \
             patch.object(ResourceCalendar, '_work_intervals_batch',
                          autospec=True, side_effect=_original_work_intervals_batch) as mock_cal_wit:
            self._mock_calevent_search = mock_ce_search
            self._mock_calevent_search_count = mock_ce_sc
            self._mock_partner_calendar_check = mock_partner_cal
            self._mock_cal_work_intervals = mock_cal_wit
            yield
