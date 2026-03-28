from decimal import Decimal
from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.urls import reverse
from django.core.exceptions import ValidationError

from .models import Expense, Income, Saving, BalanceTransfer, SavingsGoal
from .forms import ExpenseForm, IncomeForm, SavingForm, BalanceTransferForm, SavingsGoalForm


# ---------------------------------------------------------------------------
# Model validator tests
# ---------------------------------------------------------------------------
class ExpenseModelValidatorTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('tester', password='pass')

    def test_negative_amount_raises(self):
        e = Expense(user=self.user, item='Test', quantity=1, amount=Decimal('-1'))
        with self.assertRaises(ValidationError):
            e.full_clean()

    def test_zero_amount_raises(self):
        e = Expense(user=self.user, item='Test', quantity=1, amount=Decimal('0'))
        with self.assertRaises(ValidationError):
            e.full_clean()

    def test_zero_quantity_raises(self):
        e = Expense(user=self.user, item='Test', quantity=0, amount=Decimal('10'))
        with self.assertRaises(ValidationError):
            e.full_clean()

    def test_valid_expense_passes(self):
        e = Expense(user=self.user, item='Test', quantity=2, amount=Decimal('5.00'))
        e.full_clean()  # should not raise


class IncomeValidatorTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('tester2', password='pass')

    def test_zero_income_raises(self):
        i = Income(user=self.user, source='Salary', amount=Decimal('0'))
        with self.assertRaises(ValidationError):
            i.full_clean()

    def test_negative_income_raises(self):
        i = Income(user=self.user, source='Salary', amount=Decimal('-100'))
        with self.assertRaises(ValidationError):
            i.full_clean()


class SavingsGoalValidatorTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('tester3', password='pass')

    def test_zero_target_raises(self):
        g = SavingsGoal(user=self.user, name='Emergency', target_amount=Decimal('0'))
        with self.assertRaises(ValidationError):
            g.full_clean()

    def test_valid_goal_passes(self):
        g = SavingsGoal(user=self.user, name='Emergency', target_amount=Decimal('5000'))
        g.full_clean()


class SavingValidatorTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('tester4', password='pass')

    def test_zero_saving_raises(self):
        s = Saving(user=self.user, purpose='Test', amount=Decimal('0'), source='balance')
        with self.assertRaises(ValidationError):
            s.full_clean()


# ---------------------------------------------------------------------------
# Form validation tests
# ---------------------------------------------------------------------------
class ExpenseFormTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('formtester', password='pass')

    def test_zero_quantity_invalid(self):
        form = ExpenseForm({'item': 'Food', 'quantity': 0, 'amount': '50'}, user=self.user)
        self.assertFalse(form.is_valid())
        self.assertIn('quantity', form.errors)

    def test_negative_amount_invalid(self):
        form = ExpenseForm({'item': 'Food', 'quantity': 1, 'amount': '-10'}, user=self.user)
        self.assertFalse(form.is_valid())
        self.assertIn('amount', form.errors)

    def test_valid_data_passes(self):
        import datetime
        form = ExpenseForm({
            'item': 'Lunch', 'quantity': 2, 'amount': '75.00',
            'date': datetime.date.today().isoformat()
        }, user=self.user)
        self.assertTrue(form.is_valid(), form.errors)


class IncomeFormTests(TestCase):
    def test_negative_amount_invalid(self):
        import datetime
        form = IncomeForm({'source': 'Salary', 'amount': '-500', 'date': datetime.date.today().isoformat()})
        self.assertFalse(form.is_valid())
        self.assertIn('amount', form.errors)


class SavingsGoalFormTests(TestCase):
    def test_zero_target_invalid(self):
        form = SavingsGoalForm({'name': 'Bike', 'target_amount': '0'})
        self.assertFalse(form.is_valid())
        self.assertIn('target_amount', form.errors)


# ---------------------------------------------------------------------------
# User isolation / security tests
# ---------------------------------------------------------------------------
class UserIsolationTests(TestCase):
    def setUp(self):
        self.client  = Client()
        self.user_a  = User.objects.create_user('user_a', password='passA')
        self.user_b  = User.objects.create_user('user_b', password='passB')
        # Create an expense owned by user_a
        self.exp = Expense.objects.create(
            user=self.user_a, item='A Expense', quantity=1,
            amount=Decimal('100'), total=Decimal('100')
        )

    def test_user_b_cannot_delete_user_a_expense(self):
        self.client.login(username='user_b', password='passB')
        response = self.client.post(reverse('expense_delete', args=[self.exp.pk]))
        # Should return 404, not delete it
        self.assertEqual(response.status_code, 404)
        self.assertTrue(Expense.objects.filter(pk=self.exp.pk).exists())

    def test_user_b_cannot_edit_user_a_expense(self):
        self.client.login(username='user_b', password='passB')
        response = self.client.get(reverse('expense_update', args=[self.exp.pk]))
        self.assertEqual(response.status_code, 404)

    def test_unauthenticated_redirected_to_login(self):
        response = self.client.get(reverse('dashboard'))
        self.assertRedirects(response, '/accounts/login/?next=/', fetch_redirect_response=False)

    def test_user_a_sees_only_own_expenses(self):
        # Create expense for user_b
        Expense.objects.create(
            user=self.user_b, item='B Expense', quantity=1,
            amount=Decimal('200'), total=Decimal('200')
        )
        self.client.login(username='user_a', password='passA')
        response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.status_code, 200)
        expense_items = [e.item for e in response.context['expenses']]
        self.assertIn('A Expense', expense_items)
        self.assertNotIn('B Expense', expense_items)


# ---------------------------------------------------------------------------
# Dashboard view basic tests
# ---------------------------------------------------------------------------
class DashboardViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user   = User.objects.create_user('dash_user', password='pass')
        self.client.login(username='dash_user', password='pass')

    def test_dashboard_loads(self):
        response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'budgetapp/dashboard.html')

    def test_dashboard_period_filter_weekly(self):
        response = self.client.get(reverse('dashboard') + '?period=weekly')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['period'], 'weekly')

    def test_dashboard_period_filter_monthly(self):
        response = self.client.get(reverse('dashboard') + '?period=monthly')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['period'], 'monthly')
