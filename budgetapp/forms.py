from django import forms
from django.core.exceptions import ValidationError
from .models import Expense, Income, Saving, BalanceTransfer, SavingsGoal


class SavingsGoalForm(forms.ModelForm):
    class Meta:
        model  = SavingsGoal
        fields = ['name', 'target_amount', 'deadline']
        labels = {
            'name':          'Goal Name',
            'target_amount': 'Target Amount (₱)',
            'deadline':      'Deadline (optional)',
        }
        widgets = {
            'name':          forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g. Vacation, Emergency Fund',
                'autofocus': True,
            }),
            'target_amount': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min':  '0.01',
                'placeholder': '0.00',
            }),
            'deadline':      forms.DateInput(attrs={
                'class': 'form-control',
                'type':  'date',
            }),
        }

    def clean_target_amount(self):
        amount = self.cleaned_data.get('target_amount')
        if amount is not None and amount <= 0:
            raise ValidationError("Target amount must be greater than zero.")
        return amount


class ExpenseForm(forms.ModelForm):
    class Meta:
        model  = Expense
        fields = ['item', 'quantity', 'amount', 'date']
        labels = {
            'item':     'Item Name',
            'quantity': 'Quantity',
            'amount':   'Price per Unit (₱)',
            'date':     'Date',
        }
        widgets = {
            'item':     forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g. Groceries, Transport',
                'autofocus': True,
            }),
            'quantity': forms.NumberInput(attrs={
                'class': 'form-control',
                'min':   '1',
                'placeholder': '1',
            }),
            'amount':   forms.NumberInput(attrs={
                'class': 'form-control',
                'step':  '0.01',
                'min':   '0.01',
                'placeholder': '0.00',
            }),
            'date':     forms.DateInput(attrs={
                'class': 'form-control',
                'type':  'date',
            }),
        }

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)

    def clean_quantity(self):
        quantity = self.cleaned_data.get('quantity')
        if quantity is not None and quantity <= 0:
            raise ValidationError("Quantity must be at least 1.")
        return quantity

    def clean_amount(self):
        amount = self.cleaned_data.get('amount')
        if amount is not None and amount <= 0:
            raise ValidationError("Amount must be greater than zero.")
        return amount


class IncomeForm(forms.ModelForm):
    class Meta:
        model  = Income
        fields = ['source', 'amount', 'date']
        labels = {
            'source': 'Source',
            'amount': 'Amount (₱)',
            'date':   'Date',
        }
        widgets = {
            'source': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g. Salary, Allowance',
                'autofocus': True,
            }),
            'amount': forms.NumberInput(attrs={
                'class': 'form-control',
                'step':  '0.01',
                'min':   '0.01',
                'placeholder': '0.00',
            }),
            'date':   forms.DateInput(attrs={
                'class': 'form-control',
                'type':  'date',
            }),
        }

    def clean_amount(self):
        amount = self.cleaned_data.get('amount')
        if amount is not None and amount <= 0:
            raise ValidationError("Amount must be greater than zero.")
        return amount


class SavingForm(forms.ModelForm):
    class Meta:
        model  = Saving
        fields = ['goal', 'purpose', 'amount', 'source', 'date']
        labels = {
            'goal':    'Savings Goal (optional)',
            'purpose': 'Description',
            'amount':  'Amount (₱)',
            'source':  'Deduct From',
            'date':    'Date',
        }
        widgets = {
            'goal':    forms.Select(attrs={'class': 'form-select'}),
            'purpose': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g. Monthly savings',
            }),
            'amount':  forms.NumberInput(attrs={
                'class': 'form-control',
                'step':  '0.01',
                'min':   '0.01',
                'placeholder': '0.00',
            }),
            'source':  forms.Select(attrs={'class': 'form-select'}),
            'date':    forms.DateInput(attrs={
                'class': 'form-control',
                'type':  'date',
            }),
        }

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        if self.user:
            self.fields['goal'].queryset  = SavingsGoal.objects.filter(user=self.user)
            self.fields['goal'].empty_label = '— No specific goal —'

    def clean_amount(self):
        amount = self.cleaned_data.get('amount')
        if amount is not None and amount <= 0:
            raise ValidationError("Amount must be greater than zero.")
        return amount


class BalanceTransferForm(forms.ModelForm):
    class Meta:
        model  = BalanceTransfer
        fields = ['amount', 'date']
        labels = {
            'amount': 'Transfer Amount (₱)',
            'date':   'Date',
        }
        widgets = {
            'amount': forms.NumberInput(attrs={
                'class': 'form-control',
                'step':  '0.01',
                'min':   '0.01',
                'placeholder': '0.00',
                'autofocus': True,
            }),
            'date':   forms.DateInput(attrs={
                'class': 'form-control',
                'type':  'date',
            }),
        }

    def clean_amount(self):
        amount = self.cleaned_data.get('amount')
        if amount is not None and amount <= 0:
            raise ValidationError("Transfer amount must be greater than zero.")
        return amount
