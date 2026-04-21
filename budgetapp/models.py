from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator
from django.utils import timezone
from decimal import Decimal
import datetime


class Expense(models.Model):
    user     = models.ForeignKey(User, on_delete=models.CASCADE)
    item     = models.CharField(max_length=200)
    quantity = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    amount   = models.DecimalField(max_digits=10, decimal_places=2,
    validators=[MinValueValidator(Decimal('0.01'))])
    total    = models.DecimalField(max_digits=12, decimal_places=2, blank=True, null=True)
    date     = models.DateField(default=datetime.date.today)

    def save(self, *args, **kwargs):
        self.total = self.quantity * self.amount
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.item} - {self.total}"


class Income(models.Model):
    user   = models.ForeignKey(User, on_delete=models.CASCADE)
    source = models.CharField(max_length=200, default='Starting Balance')
    amount = models.DecimalField(max_digits=12, decimal_places=2,
    validators=[MinValueValidator(Decimal('0.01'))])
    date   = models.DateField(default=datetime.date.today)

    def __str__(self):
        return f"{self.source} - ₱{self.amount}"


class SavingsGoal(models.Model):
    user          = models.ForeignKey(User, on_delete=models.CASCADE)
    name          = models.CharField(max_length=200)
    target_amount = models.DecimalField(max_digits=12, decimal_places=2,
                                        validators=[MinValueValidator(Decimal('0.01'))])
    deadline      = models.DateField(null=True, blank=True)

    def __str__(self):
        return f"{self.name} - ₱{self.target_amount}"


class Saving(models.Model):
    SOURCE_CHOICES = [
        ('funds',   'Funds'),
        ('balance', 'Balance'),
    ]
    user    = models.ForeignKey(User, on_delete=models.CASCADE)
    goal    = models.ForeignKey(SavingsGoal, on_delete=models.SET_NULL, null=True, blank=True)
    source  = models.CharField(max_length=20, choices=SOURCE_CHOICES, default='balance')
    purpose = models.CharField(max_length=200, default='General Savings')
    amount  = models.DecimalField(max_digits=12, decimal_places=2,
                                  validators=[MinValueValidator(Decimal('0.01'))])
    date    = models.DateField(default=datetime.date.today)

    def __str__(self):
        return f"{self.purpose} - ₱{self.amount} ({self.source})"


class BalanceTransfer(models.Model):
    user   = models.ForeignKey(User, on_delete=models.CASCADE)
    # Allows negative (for balance→funds reversals); enforce positive only on normal entry via forms
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    date   = models.DateField(default=datetime.date.today)

    def __str__(self):
        return f"Transfer to Balance - ₱{self.amount}"


class PasswordResetOTP(models.Model):
    user       = models.ForeignKey(User, on_delete=models.CASCADE)
    otp        = models.CharField(max_length=6)
    created_at = models.DateTimeField(auto_now_add=True)
    is_used    = models.BooleanField(default=False)

    def is_valid(self):
        """OTP is valid if not used and created less than 10 minutes ago."""
        age = (timezone.now() - self.created_at).total_seconds()
        return not self.is_used and age < 600

    def __str__(self):
        return f"OTP for {self.user.username} — {'used' if self.is_used else 'active'}"
