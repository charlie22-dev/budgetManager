from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib.auth import password_validation
from django.contrib import messages
from django.db.models import Sum
from django.core.paginator import Paginator
from django.core.mail import send_mail
from .models import Expense, Income, Saving, BalanceTransfer, SavingsGoal, PasswordResetOTP
from .forms import ExpenseForm, IncomeForm, SavingForm, BalanceTransferForm, SavingsGoalForm
import csv
import io
import random
from django.http import HttpResponse, JsonResponse
from datetime import timedelta
from django.utils import timezone
from django.conf import settings

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet


# ---------------------------------------------------------------------------
# Helper: compute all dashboard totals using DB-level aggregation
# ---------------------------------------------------------------------------
def _agg(qs, field='amount'):
    return qs.aggregate(total=Sum(field))['total'] or 0


def get_dashboard_totals(user):
    all_expenses_sum     = _agg(Expense.objects.filter(user=user), 'total')
    total_income         = _agg(Income.objects.filter(user=user))
    savings_from_funds   = _agg(Saving.objects.filter(user=user, source='funds'))
    savings_from_balance = _agg(Saving.objects.filter(user=user, source='balance'))
    total_savings        = _agg(Saving.objects.filter(user=user))
    total_transfers      = _agg(BalanceTransfer.objects.filter(user=user))

    total_funds       = max(float(total_income) - float(total_transfers) - float(savings_from_funds), 0)
    remaining_balance = max(float(total_transfers) - float(all_expenses_sum) - float(savings_from_balance), 0)

    goals         = SavingsGoal.objects.filter(user=user)
    goal_progress = []
    for g in goals:
        saved  = _agg(Saving.objects.filter(user=user, goal=g))
        target = g.target_amount
        if target > 0:
            pct = min((float(saved) / float(target)) * 100, 100)
            goal_progress.append({
                'pk':      g.pk,
                'name':    g.name,
                'saved':   float(saved),
                'target':  float(target),
                'percent': float(pct),
                'status':  'completed' if pct >= 100 else 'in_progress',
            })

    return {
        'total_funds':       float(total_funds),
        'total_expenses':    float(all_expenses_sum),
        'total_savings':     float(total_savings),
        'remaining_balance': float(remaining_balance),
        'goal_progress':     goal_progress,
    }


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------
@login_required
def dashboard(request):
    sort_by = request.GET.get('sort', '-date')
    period  = request.GET.get('period', 'all')
    page    = request.GET.get('page', 1)

    valid_sorts = ['item', '-item', 'amount', '-amount', 'total', '-total', 'date', '-date']
    if sort_by not in valid_sorts:
        sort_by = '-date'

    expenses_qs = Expense.objects.filter(user=request.user)

    today = timezone.localtime().date()
    if period == 'weekly':
        start_date  = today - timedelta(days=today.weekday())
        expenses_qs = expenses_qs.filter(date__gte=start_date)
    elif period == 'monthly':
        start_date  = today.replace(day=1)
        expenses_qs = expenses_qs.filter(date__gte=start_date)

    expenses_qs = expenses_qs.order_by(sort_by)

    # Pagination (10 per page)
    paginator = Paginator(expenses_qs, 10)
    expenses  = paginator.get_page(page)

    # Financial totals via ORM aggregation
    all_expenses_sum     = _agg(Expense.objects.filter(user=request.user), 'total')
    filtered_expenses_total = _agg(expenses_qs, 'total')
    total_income         = _agg(Income.objects.filter(user=request.user))
    savings_from_funds   = _agg(Saving.objects.filter(user=request.user, source='funds'))
    savings_from_balance = _agg(Saving.objects.filter(user=request.user, source='balance'))
    total_savings        = _agg(Saving.objects.filter(user=request.user))
    total_transfers      = _agg(BalanceTransfer.objects.filter(user=request.user))

    total_funds       = max(float(total_income) - float(total_transfers) - float(savings_from_funds), 0)
    remaining_balance = max(float(total_transfers) - float(all_expenses_sum) - float(savings_from_balance), 0)

    # Insights
    insights = []
    if period == 'monthly':
        month_savings = _agg(Saving.objects.filter(user=request.user, date__gte=today.replace(day=1)))
        if month_savings > 0:
            insights.append(f"You saved ₱{month_savings:,.2f} this month.")

    # Goals progress
    goals         = SavingsGoal.objects.filter(user=request.user)
    goal_progress = []
    for g in goals:
        saved  = _agg(Saving.objects.filter(user=request.user, goal=g))
        target = g.target_amount
        if target > 0:
            pct    = min((float(saved) / float(target)) * 100, 100)
            status = 'completed' if pct >= 100 else 'in_progress'
            goal_progress.append({
                'name':      g.name,
                'saved':     float(saved),
                'target':    float(target),
                'percent':   pct,
                'status':    status,
                'remaining': max(float(target) - float(saved), 0),
            })

    context = {
        'expenses':              expenses,
        'sort_by':               sort_by,
        'period':                period,
        'total_expenses':        filtered_expenses_total,
        'all_time_expenses':     all_expenses_sum,
        'monthly_budget':        total_funds,
        'total_savings':         total_savings,
        'remaining_balance':     remaining_balance,
        'insights':              insights,
        'goal_progress':         goal_progress,
        'expense_form':          ExpenseForm(user=request.user),
        'income_form':           IncomeForm(),
        'saving_form':           SavingForm(user=request.user),
        'paginator':             paginator,
        'is_paginated':          paginator.num_pages > 1,
    }
    return render(request, 'budgetapp/dashboard.html', context)


# ---------------------------------------------------------------------------
# Expense CRUD
# ---------------------------------------------------------------------------
def _get_current_balance(user):
    transfers    = _agg(BalanceTransfer.objects.filter(user=user))
    expenses_sum = _agg(Expense.objects.filter(user=user), 'total')
    savings_bal  = _agg(Saving.objects.filter(user=user, source='balance'))
    return max(float(transfers) - float(expenses_sum) - float(savings_bal), 0)


def _get_current_funds(user):
    incomes       = _agg(Income.objects.filter(user=user))
    transfers     = _agg(BalanceTransfer.objects.filter(user=user))
    savings_funds = _agg(Saving.objects.filter(user=user, source='funds'))
    return float(incomes) - float(transfers) - float(savings_funds)


@login_required
def expense_create(request):
    if request.method == 'POST':
        form = ExpenseForm(request.POST, user=request.user)
        if form.is_valid():
            expense = form.save(commit=False)
            current_balance = _get_current_balance(request.user)
            expense_total   = float(expense.quantity * expense.amount)

            if current_balance < expense_total:
                msg = 'Insufficient Remaining Balance!'
                if request.headers.get('Accept') == 'application/json':
                    return JsonResponse({'success': False, 'message': msg})
                messages.error(request, f'Error: {msg}')
                return render(request, 'budgetapp/expense_form.html',
                              {'form': form, 'action': 'Add', 'remaining_balance': current_balance})

            expense.user = request.user
            expense.save()
            if request.headers.get('Accept') == 'application/json':
                return JsonResponse({'success': True, 'message': 'Expense logged!',
                                     'updated_data': get_dashboard_totals(request.user)})
            messages.success(request, 'Expense added successfully!')
            return redirect('dashboard')
        else:
            if request.headers.get('Accept') == 'application/json':
                return JsonResponse({'success': False, 'message': 'Invalid expense data provided.'})
            messages.error(request, 'Please correct the errors below.')
    else:
        form            = ExpenseForm(user=request.user)
        current_balance = _get_current_balance(request.user)

    return render(request, 'budgetapp/expense_form.html',
                  {'form': form, 'action': 'Add', 'remaining_balance': current_balance})


@login_required
def income_create(request):
    if request.method == 'POST':
        form = IncomeForm(request.POST)
        if form.is_valid():
            income = form.save(commit=False)
            income.user = request.user
            income.save()
            if request.headers.get('Accept') == 'application/json':
                return JsonResponse({'success': True, 'message': 'Funds added!',
                                     'updated_data': get_dashboard_totals(request.user)})
            messages.success(request, 'Funds added successfully!')
            return redirect('dashboard')
        else:
            if request.headers.get('Accept') == 'application/json':
                return JsonResponse({'success': False, 'message': 'Invalid income data provided.'})
            messages.error(request, 'Please correct the errors below.')
    else:
        form = IncomeForm()

    return render(request, 'budgetapp/income_form.html', {'form': form})


@login_required
def income_reset(request):
    if request.method == 'POST':
        Income.objects.filter(user=request.user).delete()
        messages.success(request, 'Your funds have been successfully reset.')
        return redirect('dashboard')
    return render(request, 'budgetapp/income_reset_confirm.html')


# ---------------------------------------------------------------------------
# Savings
# ---------------------------------------------------------------------------
@login_required
def savings_list(request):
    savings       = Saving.objects.filter(user=request.user).select_related('goal').order_by('-date')
    total_savings = _agg(savings)

    goals         = SavingsGoal.objects.filter(user=request.user)
    goal_progress = []
    for g in goals:
        saved  = _agg(Saving.objects.filter(user=request.user, goal=g))
        target = g.target_amount
        if target > 0:
            pct    = min((float(saved) / float(target)) * 100, 100)
            status = 'completed' if pct >= 100 else 'in_progress'
            goal_progress.append({
                'pk':       g.pk,
                'name':     g.name,
                'saved':    float(saved),
                'target':   float(target),
                'percent':  pct,
                'status':   status,
                'deadline': g.deadline,
            })

    return render(request, 'budgetapp/savings_list.html',
                  {'savings': savings, 'total_savings': total_savings,
                   'goal_progress': goal_progress})


@login_required
def saving_create(request):
    if request.method == 'POST':
        form = SavingForm(request.POST, user=request.user)
        if form.is_valid():
            saving = form.save(commit=False)

            if saving.source == 'balance':
                current_balance = _get_current_balance(request.user)
                if current_balance < float(saving.amount):
                    msg = 'Insufficient Remaining Balance!'
                    if request.headers.get('Accept') == 'application/json':
                        return JsonResponse({'success': False, 'message': msg})
                    messages.error(request, f'Error: {msg}')
                    return render(request, 'budgetapp/saving_form.html', {'form': form})
            else:
                current_funds = _get_current_funds(request.user)
                if current_funds < float(saving.amount):
                    msg = 'Insufficient Total Funds!'
                    if request.headers.get('Accept') == 'application/json':
                        return JsonResponse({'success': False, 'message': msg})
                    messages.error(request, f'Error: {msg}')
                    return render(request, 'budgetapp/saving_form.html', {'form': form})

            saving.user = request.user
            saving.save()

            if saving.goal:
                goal_savings = _agg(Saving.objects.filter(user=request.user, goal=saving.goal))
                msg = (f'Congratulations! You reached your savings goal: {saving.goal.name}!'
                       if float(goal_savings) >= float(saving.goal.target_amount)
                       else 'Savings added!')
            else:
                msg = 'Savings added!'

            if request.headers.get('Accept') == 'application/json':
                return JsonResponse({'success': True, 'message': msg,
                                     'updated_data': get_dashboard_totals(request.user)})
            messages.success(request, msg)
            return redirect('savings_list')
        else:
            if request.headers.get('Accept') == 'application/json':
                return JsonResponse({'success': False, 'message': 'Invalid saving data provided.'})
            messages.error(request, 'Please correct the errors below.')
    else:
        form = SavingForm(user=request.user)

    return render(request, 'budgetapp/saving_form.html', {'form': form})


@login_required
def expense_update(request, pk):
    expense = get_object_or_404(Expense, pk=pk, user=request.user)
    if request.method == 'POST':
        form = ExpenseForm(request.POST, instance=expense, user=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, 'Expense updated successfully!')
            return redirect('dashboard')
    else:
        form = ExpenseForm(instance=expense, user=request.user)

    return render(request, 'budgetapp/expense_form.html', {'form': form, 'action': 'Edit'})


@login_required
def expense_delete(request, pk):
    expense = get_object_or_404(Expense, pk=pk, user=request.user)
    if request.method == 'POST':
        expense.delete()
        messages.success(request, 'Expense deleted successfully!')
        return redirect('dashboard')
    return render(request, 'budgetapp/expense_confirm_delete.html', {'expense': expense})


@login_required
def expense_delete_all(request):
    if request.method == 'POST':
        Expense.objects.filter(user=request.user).delete()
        messages.success(request, 'All expenses deleted successfully!')
        return redirect('dashboard')
    return render(request, 'budgetapp/expense_delete_all_confirm.html')


# ---------------------------------------------------------------------------
# Monitoring
# ---------------------------------------------------------------------------
def _build_chart_data(daily_qs):
    dates, totals = [], []
    for item in daily_qs:
        day = item['date']
        if hasattr(day, 'strftime'):
            dates.append([day.strftime('%a'), day.strftime('%Y-%m-%d')])
        else:
            import datetime as dt
            try:
                parsed = dt.datetime.strptime(str(day).split(' ')[0], '%Y-%m-%d')
                dates.append([parsed.strftime('%a'), parsed.strftime('%Y-%m-%d')])
            except Exception:
                dates.append([str(day).split(' ')[0]])
        totals.append(float(item['daily_total'] or 0))
    return dates, totals


@login_required
def monitoring(request):
    daily_expenses = (Expense.objects
                      .filter(user=request.user)
                      .values('date')
                      .annotate(daily_total=Sum('total'))
                      .order_by('date'))
    dates, totals = _build_chart_data(daily_expenses)
    return render(request, 'budgetapp/monitoring.html', {'dates': dates, 'totals': totals})


@login_required
def savings_monitoring(request):
    daily_savings = (Saving.objects
                     .filter(user=request.user)
                     .values('date')
                     .annotate(daily_total=Sum('amount'))
                     .order_by('date'))
    dates, totals = _build_chart_data(daily_savings)
    return render(request, 'budgetapp/savings_monitoring.html', {'dates': dates, 'totals': totals})


@login_required
def funds_history(request):
    incomes     = Income.objects.filter(user=request.user).order_by('-date')
    total_funds = _agg(incomes)

    daily_funds = (Income.objects
                   .filter(user=request.user)
                   .values('date')
                   .annotate(daily_total=Sum('amount'))
                   .order_by('date'))
    dates, totals = _build_chart_data(daily_funds)

    return render(request, 'budgetapp/funds_history.html',
                  {'incomes': incomes, 'total_funds': total_funds,
                   'dates': dates, 'totals': totals})


@login_required
def balance_history(request):
    transfers            = BalanceTransfer.objects.filter(user=request.user).order_by('-date')
    current_balance_total = _agg(transfers)

    daily_transfers = (BalanceTransfer.objects
                       .filter(user=request.user)
                       .values('date')
                       .annotate(daily_total=Sum('amount'))
                       .order_by('date'))
    dates, totals = _build_chart_data(daily_transfers)

    return render(request, 'budgetapp/balance_history.html',
                  {'transfers': transfers, 'current_balance_total': current_balance_total,
                   'dates': dates, 'totals': totals})


def about(request):
    return render(request, 'budgetapp/about.html')


def contact(request):
    return render(request, 'budgetapp/contact.html')


# ---------------------------------------------------------------------------
# Balance management
# ---------------------------------------------------------------------------
@login_required
def balance_reset(request):
    if request.method == 'POST':
        BalanceTransfer.objects.filter(user=request.user).delete()
        messages.success(request, 'Your balance has been successfully reset.')
        return redirect('dashboard')
    return render(request, 'budgetapp/balance_reset_confirm.html')


@login_required
def balance_to_funds(request):
    current_balance = _get_current_balance(request.user)

    if request.method == 'POST':
        try:
            amount = float(request.POST.get('amount', 0))
        except (ValueError, TypeError):
            amount = 0

        if amount <= 0:
            messages.error(request, 'Please enter a valid amount greater than zero.')
        elif amount > current_balance:
            messages.error(request,
                           f'Error: Insufficient Balance! You only have ₱{current_balance:.2f} available.')
        else:
            BalanceTransfer.objects.create(user=request.user, amount=-amount)
            messages.success(request, f'₱{amount:,.2f} transferred back to Funds successfully!')
            return redirect('dashboard')

    return render(request, 'budgetapp/balance_to_funds_form.html',
                  {'current_balance': current_balance})


@login_required
def balance_transfer_create(request):
    if request.method == 'POST':
        form = BalanceTransferForm(request.POST)
        if form.is_valid():
            transfer      = form.save(commit=False)
            current_funds = _get_current_funds(request.user)

            if current_funds < float(transfer.amount):
                msg = 'Insufficient Total Funds!'
                if request.headers.get('Accept') == 'application/json':
                    return JsonResponse({'success': False, 'message': msg})
                messages.error(request, f'Error: {msg}')
                return render(request, 'budgetapp/balance_transfer_form.html', {'form': form})

            transfer.user = request.user
            transfer.save()
            if request.headers.get('Accept') == 'application/json':
                return JsonResponse({'success': True, 'message': 'Added to Balance!',
                                     'updated_data': get_dashboard_totals(request.user)})
            messages.success(request, 'Transferred to Balance successfully!')
            return redirect('dashboard')
        else:
            if request.headers.get('Accept') == 'application/json':
                return JsonResponse({'success': False, 'message': 'Invalid transfer data provided.'})
            messages.error(request, 'Please correct the errors below.')
    else:
        form = BalanceTransferForm()

    return render(request, 'budgetapp/balance_transfer_form.html', {'form': form})


# ---------------------------------------------------------------------------
# Saving delete
# ---------------------------------------------------------------------------
@login_required
def saving_delete(request, pk):
    saving = get_object_or_404(Saving, pk=pk, user=request.user)
    if request.method == 'POST':
        saving.delete()
        messages.success(request, 'Savings entry deleted successfully!')
        return redirect('savings_list')
    return render(request, 'budgetapp/saving_confirm_delete.html', {'saving': saving})


@login_required
def saving_delete_all(request):
    if request.method == 'POST':
        Saving.objects.filter(user=request.user).delete()
        messages.success(request, 'All savings deleted successfully!')
        return redirect('savings_list')
    return render(request, 'budgetapp/saving_delete_all_confirm.html')


# ---------------------------------------------------------------------------
# Savings Goals CRUD
# ---------------------------------------------------------------------------
@login_required
def savings_goal_create(request):
    if request.method == 'POST':
        form = SavingsGoalForm(request.POST)
        if form.is_valid():
            sg      = form.save(commit=False)
            sg.user = request.user
            sg.save()
            messages.success(request, 'Savings Goal created successfully!')
            return redirect('savings_list')
    else:
        form = SavingsGoalForm()
    return render(request, 'budgetapp/savings_goal_form.html', {'form': form, 'action': 'Create'})


@login_required
def savings_goal_update(request, pk):
    sg = get_object_or_404(SavingsGoal, pk=pk, user=request.user)
    if request.method == 'POST':
        form = SavingsGoalForm(request.POST, instance=sg)
        if form.is_valid():
            form.save()
            messages.success(request, 'Savings Goal updated successfully!')
            return redirect('savings_list')
    else:
        form = SavingsGoalForm(instance=sg)
    return render(request, 'budgetapp/savings_goal_form.html', {'form': form, 'action': 'Edit'})


@login_required
def savings_goal_delete(request, pk):
    sg = get_object_or_404(SavingsGoal, pk=pk, user=request.user)
    if request.method == 'POST':
        sg.delete()
        messages.success(request, 'Savings Goal deleted successfully!')
        return redirect('savings_list')
    return render(request, 'budgetapp/savings_goal_confirm_delete.html', {'goal': sg})


# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------
@login_required
def export_report(request):
    format_type = request.GET.get('format', 'csv')
    
    # Collect all data
    data = []
    
    for e in Expense.objects.filter(user=request.user).order_by('-date'):
        data.append(['Expense', e.date.strftime('%m/%d/%Y') if e.date else '', e.item, '', float(e.total)])

    for i in Income.objects.filter(user=request.user).order_by('-date'):
        data.append(['Income', i.date.strftime('%m/%d/%Y') if i.date else '', i.source, '', float(i.amount)])

    for s in Saving.objects.filter(user=request.user).select_related('goal').order_by('-date'):
        goal_name = s.goal.name if s.goal else 'General Savings'
        data.append(['Saving', s.date.strftime('%m/%d/%Y') if s.date else '', s.purpose, goal_name, float(s.amount)])

    if format_type == 'pdf':
        response = HttpResponse(content_type='application/pdf')
        response['Content-Disposition'] = 'attachment; filename="TipidTracker_Report.pdf"'
        
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=letter)
        elements = []
        styles = getSampleStyleSheet()
        
        # Title
        title_style = styles['Heading1']
        title_style.alignment = 1 # Center
        elements.append(Paragraph("TipidTracker Financial Report", title_style))
        elements.append(Spacer(1, 20))
        
        # Table Data
        table_data = [['Type', 'Date', 'Description', 'Category', 'Amount (₱)']]
        for row in data:
            formatted_amount = f"₱{row[4]:,.2f}"
            table_data.append([row[0], row[1], row[2], row[3], formatted_amount])
            
        if len(table_data) > 1:
            t = Table(table_data, colWidths=[80, 80, 160, 120, 80])
            t.setStyle(TableStyle([
                ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#4f46e5')),
                ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
                ('ALIGN', (0,0), (-1,-1), 'LEFT'),
                ('ALIGN', (-1,0), (-1,-1), 'RIGHT'),
                ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
                ('FONTSIZE', (0,0), (-1,0), 12),
                ('BOTTOMPADDING', (0,0), (-1,0), 12),
                ('BACKGROUND', (0,1), (-1,-1), colors.HexColor('#f8fafc')),
                ('GRID', (0,0), (-1,-1), 1, colors.HexColor('#e2e8f0')),
            ]))
            elements.append(t)
        else:
            elements.append(Paragraph("No financial records found.", styles['Normal']))
            
        doc.build(elements)
        pdf = buffer.getvalue()
        buffer.close()
        response.write(pdf)
        return response

    else:
        # Default CSV export
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="TipidTracker_Report.csv"'

        writer = csv.writer(response)
        writer.writerow(['Type', 'Date', 'Description/Item', 'Category/Goal', 'Amount'])
        for row in data:
            writer.writerow(row)

        return response


# ---------------------------------------------------------------------------
# OTP-Based Password Reset (3-step flow)
# ---------------------------------------------------------------------------

def password_reset_request(request):
    """Step 1: User enters their email. OTP is generated and sent."""
    if request.method == 'POST':
        email = request.POST.get('email', '').strip()
        try:
            user = User.objects.get(email__iexact=email)
        except User.DoesNotExist:
            # Don't leak whether the email exists. Show fake success.
            request.session['otp_email'] = email
            return redirect('password_reset_verify')

        # Invalidate any old OTPs for this user
        PasswordResetOTP.objects.filter(user=user, is_used=False).update(is_used=True)

        # Generate a fresh 6-digit OTP
        otp_code = f"{random.randint(100000, 999999)}"
        PasswordResetOTP.objects.create(user=user, otp=otp_code)

        # Send the OTP email
        send_mail(
            subject='Your TipidTracker Password Reset Code',
            message=(
                f"Hello {user.username},\n\n"
                f"Your password reset code is:\n\n"
                f"  {otp_code}\n\n"
                f"This code is valid for 10 minutes. Do not share it with anyone.\n\n"
                f"If you did not request this, you can safely ignore this email.\n\n"
                f"— TipidTracker Team"
            ),
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[email],
            fail_silently=False,
        )

        request.session['otp_email'] = email
        return redirect('password_reset_verify')

    return render(request, 'budgetapp/password_reset_request.html')


def password_reset_verify(request):
    """Step 2: User enters the 6-digit OTP they received."""
    email = request.session.get('otp_email')
    if not email:
        return redirect('password_reset_request')

    if request.method == 'POST':
        entered_otp = request.POST.get('otp', '').strip()
        try:
            user = User.objects.get(email__iexact=email)
            otp_obj = PasswordResetOTP.objects.filter(
                user=user, otp=entered_otp, is_used=False
            ).latest('created_at')

            if otp_obj.is_valid():
                # Mark OTP as used and store user ID for Step 3
                otp_obj.is_used = True
                otp_obj.save()
                request.session['reset_user_id'] = user.pk
                # Clean up to prevent re-use
                del request.session['otp_email']
                return redirect('password_reset_confirm')
            else:
                messages.error(request, 'This OTP has expired. Please request a new one.')
        except (User.DoesNotExist, PasswordResetOTP.DoesNotExist):
            messages.error(request, 'Invalid OTP. Please check and try again.')

    return render(request, 'budgetapp/password_reset_verify.html', {'email': email})


def password_reset_confirm(request):
    """Step 3: User sets a new password after OTP verification."""
    user_id = request.session.get('reset_user_id')
    if not user_id:
        return redirect('password_reset_request')

    user = get_object_or_404(User, pk=user_id)

    if request.method == 'POST':
        password1 = request.POST.get('password1', '')
        password2 = request.POST.get('password2', '')

        if password1 != password2:
            messages.error(request, 'Passwords do not match.')
        elif len(password1) < 8:
            messages.error(request, 'Password must be at least 8 characters long.')
        else:
            user.set_password(password1)
            user.save()
            # Clear session
            del request.session['reset_user_id']
            messages.success(request, 'Your password has been updated! Please sign in.')
            return redirect('account_login')

    return render(request, 'budgetapp/password_reset_confirm.html')
