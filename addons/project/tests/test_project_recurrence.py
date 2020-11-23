# -*- coding: utf-8 -*-


from odoo.tests.common import TransactionCase, Form
from odoo.exceptions import ValidationError
from odoo import fields

from datetime import date, datetime
from dateutil.rrule import MO, TU, WE, TH, FR, SA, SU

from unittest.mock import patch

class TestProjectrecurrence(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super(TestProjectrecurrence, cls).setUpClass()

        cls.env.user.groups_id += cls.env.ref('project.group_project_recurring_tasks')

        cls.stage_a = cls.env['project.task.type'].create({'name': 'a'})
        cls.stage_b = cls.env['project.task.type'].create({'name': 'b'})
        cls.project_recurring = cls.env['project.project'].with_context({'mail_create_nolog': True}).create({
            'name': 'Recurring',
            'allow_recurring_tasks': True,
            'type_ids': [
                (4, cls.stage_a.id),
                (4, cls.stage_b.id),
            ]
        })

    def set_task_create_date(self, task_id, create_date):
        self.env.cr.execute("UPDATE project_task SET create_date=%s WHERE id=%s", (create_date, task_id))

    def test_recurrence_simple(self):
        with patch.object(fields.Date, 'today', lambda: datetime(2020, 2, 1)):
            with Form(self.env['project.task']) as form:
                form.name = 'test recurring task'
                form.project_id = self.project_recurring

                form.recurring_task = True
                form.repeat_interval = 5
                form.repeat_unit = 'month'
                form.repeat_type = 'after'
                form.repeat_number = 10
                form.repeat_on_month = 'date'
                form.repeat_day = '31'
            task = form.save()
            self.assertTrue(bool(task.recurrence_id), 'should create a recurrence')

            task.write(dict(repeat_interval=2, repeat_number=11))
            self.assertEqual(task.recurrence_id.repeat_interval, 2, 'recurrence should be updated')
            self.assertEqual(task.recurrence_id.repeat_number, 11, 'recurrence should be updated')
            self.assertEqual(task.recurrence_id.recurrence_left, 11)
            self.assertEqual(task.recurrence_id.next_recurrence_date, date(2020, 2, 29))

            task.recurring_task = False
            self.assertFalse(bool(task.recurrence_id), 'the recurrence should be deleted')

    def test_recurrence_cron(self):
        with patch.object(fields.Date, 'today', lambda: datetime(2020, 1, 1)):
            form = Form(self.env['project.task'])
            form.name = 'test recurring task'
            form.description = 'my super recurring task bla bla bla'
            form.project_id = self.project_recurring
            form.date_deadline = datetime(2020, 2, 1)

            form.recurring_task = True
            form.repeat_interval = 1
            form.repeat_unit = 'month'
            form.repeat_type = 'after'
            form.repeat_number = 2
            form.repeat_on_month = 'date'
            form.repeat_day = '15'
            task = form.save()
            task.planned_hours = 2

            self.assertEqual(task.recurrence_id.next_recurrence_date, date(2020, 1, 15))
            self.assertEqual(self.env['project.task'].search_count([('project_id', '=', self.project_recurring.id)]), 1)
            self.env['project.task.recurrence']._cron_create_recurring_tasks()
            self.assertEqual(self.env['project.task'].search_count([('project_id', '=', self.project_recurring.id)]), 1, 'no extra task should be created')
            self.assertEqual(task.recurrence_id.recurrence_left, 2)

        with patch.object(fields.Date, 'today', lambda: datetime(2020, 1, 15)):
            self.assertEqual(self.env['project.task'].search_count([('project_id', '=', self.project_recurring.id)]), 1)
            self.env['project.task.recurrence']._cron_create_recurring_tasks()
            self.assertEqual(self.env['project.task'].search_count([('project_id', '=', self.project_recurring.id)]), 2)
            self.assertEqual(task.recurrence_id.recurrence_left, 1)

        with patch.object(fields.Date, 'today', lambda: datetime(2020, 2, 15)):
            self.env['project.task.recurrence']._cron_create_recurring_tasks()
            self.assertEqual(task.recurrence_id.recurrence_left, 0)

        tasks = self.env['project.task'].search([('project_id', '=', self.project_recurring.id)])
        self.assertEqual(len(tasks), 3)

        self.assertTrue(bool(tasks[2].date_deadline))
        self.assertFalse(tasks[1].date_deadline, "Deadline should not be copied")

        for f in self.env['project.task.recurrence']._get_recurring_fields():
            self.assertTrue(tasks[0][f] == tasks[1][f] == tasks[2][f], "Field %s should have been copied" % f)

    def test_recurrence_update_task(self):
        with patch.object(fields.Date, 'today', lambda: datetime(2020, 1, 1)):
            task = self.env['project.task'].create({
                    'name': 'test recurring task',
                    'project_id': self.project_recurring.id,
                    'recurring_task': True,
                    'repeat_interval': 1,
                    'repeat_unit': 'week',
                    'repeat_type': 'after',
                    'repeat_number': 2,
                    'mon': True,
                })

        with patch.object(fields.Date, 'today', lambda: datetime(2020, 1, 6)):
            self.env['project.task.recurrence']._cron_create_recurring_tasks()

        with patch.object(fields.Date, 'today', lambda: datetime(2020, 1, 13)):
            self.env['project.task.recurrence']._cron_create_recurring_tasks()

        task_c, task_b, task_a = self.env['project.task'].search([('project_id', '=', self.project_recurring.id)])

        self.set_task_create_date(task_a.id, datetime(2020, 1, 1))
        self.set_task_create_date(task_b.id, datetime(2020, 1, 6))
        self.set_task_create_date(task_c.id, datetime(2020, 1, 13))
        (task_a+task_b+task_c).invalidate_cache()

        task_c.write({
            'name': 'my super updated task',
            'recurrence_update': 'all',
        })

        self.assertEqual(task_a.name, 'my super updated task')
        self.assertEqual(task_b.name, 'my super updated task')
        self.assertEqual(task_c.name, 'my super updated task')

        task_a.write({
            'name': 'don\'t you dare change my title',
            'recurrence_update': 'this',
        })

        self.assertEqual(task_a.name, 'don\'t you dare change my title')
        self.assertEqual(task_b.name, 'my super updated task')
        self.assertEqual(task_c.name, 'my super updated task')

        task_b.write({
            'description': 'hello!',
            'recurrence_update': 'subsequent',
        })

        self.assertEqual(task_a.description, False)
        self.assertEqual(task_b.description, '<p>hello!</p>')
        self.assertEqual(task_c.description, '<p>hello!</p>')

    def test_recurrence_fields_visibility(self):
        form = Form(self.env['project.task'])

        form.name = 'test recurring task'
        form.project_id = self.project_recurring
        form.recurring_task = True

        form.repeat_unit = 'week'
        self.assertTrue(form.repeat_show_dow)
        self.assertFalse(form.repeat_show_day)
        self.assertFalse(form.repeat_show_week)
        self.assertFalse(form.repeat_show_month)

        form.repeat_unit = 'month'
        form.repeat_on_month = 'date'
        self.assertFalse(form.repeat_show_dow)
        self.assertTrue(form.repeat_show_day)
        self.assertFalse(form.repeat_show_week)
        self.assertFalse(form.repeat_show_month)

        form.repeat_unit = 'month'
        form.repeat_on_month = 'day'
        self.assertFalse(form.repeat_show_dow)
        self.assertFalse(form.repeat_show_day)
        self.assertTrue(form.repeat_show_week)
        self.assertFalse(form.repeat_show_month)

        form.repeat_unit = 'year'
        form.repeat_on_year = 'date'
        self.assertFalse(form.repeat_show_dow)
        self.assertTrue(form.repeat_show_day)
        self.assertFalse(form.repeat_show_week)
        self.assertTrue(form.repeat_show_month)

        form.repeat_unit = 'year'
        form.repeat_on_year = 'day'
        self.assertFalse(form.repeat_show_dow)
        self.assertFalse(form.repeat_show_day)
        self.assertTrue(form.repeat_show_week)
        self.assertTrue(form.repeat_show_month)

        form.recurring_task = False
        self.assertFalse(form.repeat_show_dow)
        self.assertFalse(form.repeat_show_day)
        self.assertFalse(form.repeat_show_week)
        self.assertFalse(form.repeat_show_month)

    def test_recurrence_week_day(self):
        form = Form(self.env['project.task'])

        form.name = 'test recurring task'
        form.project_id = self.project_recurring
        form.recurring_task = True
        form.repeat_unit = 'week'

        form.mon = False
        form.tue = False
        form.wed = False
        form.thu = False
        form.fri = False
        form.sat = False
        form.sun = False

        with self.assertRaises(ValidationError), self.cr.savepoint():
            form.save()

    def test_recurrence_next_dates_week(self):
        dates = self.env['project.task.recurrence']._get_next_recurring_dates(
            date_start=date(2020, 1, 1),
            repeat_interval=1,
            repeat_unit='week',
            repeat_type=False,
            repeat_until=False,
            repeat_on_month=False,
            repeat_on_year=False,
            weekdays=False,
            repeat_day=False,
            repeat_week=False,
            repeat_month=False,
            count=5)

        self.assertEqual(dates[0], datetime(2020, 1, 6, 0, 0))
        self.assertEqual(dates[1], datetime(2020, 1, 13, 0, 0))
        self.assertEqual(dates[2], datetime(2020, 1, 20, 0, 0))
        self.assertEqual(dates[3], datetime(2020, 1, 27, 0, 0))
        self.assertEqual(dates[4], datetime(2020, 2, 3, 0, 0))

        dates = self.env['project.task.recurrence']._get_next_recurring_dates(
            date_start=date(2020, 1, 1),
            repeat_interval=3,
            repeat_unit='week',
            repeat_type='until',
            repeat_until=date(2020, 2, 1),
            repeat_on_month=False,
            repeat_on_year=False,
            weekdays=[MO, FR],
            repeat_day=False,
            repeat_week=False,
            repeat_month=False,
            count=100)

        self.assertEqual(len(dates), 3)
        self.assertEqual(dates[0], datetime(2020, 1, 3, 0, 0))
        self.assertEqual(dates[1], datetime(2020, 1, 20, 0, 0))
        self.assertEqual(dates[2], datetime(2020, 1, 24, 0, 0))

    def test_recurrence_next_dates_month(self):
        dates = self.env['project.task.recurrence']._get_next_recurring_dates(
            date_start=date(2020, 1, 15),
            repeat_interval=1,
            repeat_unit='month',
            repeat_type=False, # Forever
            repeat_until=False,
            repeat_on_month='date',
            repeat_on_year=False,
            weekdays=False,
            repeat_day=31,
            repeat_week=False,
            repeat_month=False,
            count=12)

        # should take the last day of each month
        self.assertEqual(dates[0], date(2020, 1, 31))
        self.assertEqual(dates[1], date(2020, 2, 29))
        self.assertEqual(dates[2], date(2020, 3, 31))
        self.assertEqual(dates[3], date(2020, 4, 30))
        self.assertEqual(dates[4], date(2020, 5, 31))
        self.assertEqual(dates[5], date(2020, 6, 30))
        self.assertEqual(dates[6], date(2020, 7, 31))
        self.assertEqual(dates[7], date(2020, 8, 31))
        self.assertEqual(dates[8], date(2020, 9, 30))
        self.assertEqual(dates[9], date(2020, 10, 31))
        self.assertEqual(dates[10], date(2020, 11, 30))
        self.assertEqual(dates[11], date(2020, 12, 31))

        dates = self.env['project.task.recurrence']._get_next_recurring_dates(
            date_start=date(2020, 2, 20),
            repeat_interval=3,
            repeat_unit='month',
            repeat_type=False, # Forever
            repeat_until=False,
            repeat_on_month='date',
            repeat_on_year=False,
            weekdays=False,
            repeat_day=29,
            repeat_week=False,
            repeat_month=False,
            count=5)

        self.assertEqual(dates[0], date(2020, 2, 29))
        self.assertEqual(dates[1], date(2020, 5, 29))
        self.assertEqual(dates[2], date(2020, 8, 29))
        self.assertEqual(dates[3], date(2020, 11, 29))
        self.assertEqual(dates[4], date(2021, 2, 28))

        dates = self.env['project.task.recurrence']._get_next_recurring_dates(
            date_start=date(2020, 1, 10),
            repeat_interval=1,
            repeat_unit='month',
            repeat_type='until',
            repeat_until=datetime(2020, 5, 31),
            repeat_on_month='day',
            repeat_on_year=False,
            weekdays=[SA(4), ], # 4th Saturday
            repeat_day=29,
            repeat_week=False,
            repeat_month=False,
            count=6)

        self.assertEqual(len(dates), 5)
        self.assertEqual(dates[0], datetime(2020, 1, 25))
        self.assertEqual(dates[1], datetime(2020, 2, 22))
        self.assertEqual(dates[2], datetime(2020, 3, 28))
        self.assertEqual(dates[3], datetime(2020, 4, 25))
        self.assertEqual(dates[4], datetime(2020, 5, 23))

    def test_recurrence_next_dates_year(self):
        dates = self.env['project.task.recurrence']._get_next_recurring_dates(
            date_start=date(2020, 12, 1),
            repeat_interval=1,
            repeat_unit='year',
            repeat_type='until',
            repeat_until=datetime(2026, 1, 1),
            repeat_on_month=False,
            repeat_on_year='date',
            weekdays=False,
            repeat_day=31,
            repeat_week=False,
            repeat_month='november',
            count=10)

        self.assertEqual(len(dates), 5)
        self.assertEqual(dates[0], datetime(2021, 11, 30))
        self.assertEqual(dates[1], datetime(2022, 11, 30))
        self.assertEqual(dates[2], datetime(2023, 11, 30))
        self.assertEqual(dates[3], datetime(2024, 11, 30))
        self.assertEqual(dates[4], datetime(2025, 11, 30))
