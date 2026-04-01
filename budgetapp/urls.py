from django.urls import path
from . import views

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('income/create/', views.income_create, name='income_create'),
    path('income/reset/', views.income_reset, name='income_reset'),
    path('savings/', views.savings_list, name='savings_list'),
    path('savings/create/', views.saving_create, name='saving_create'),
    path('savings/delete/<int:pk>/', views.saving_delete, name='saving_delete'),
    path('savings/delete_all/', views.saving_delete_all, name='saving_delete_all'),
    path('balance/add/', views.balance_transfer_create, name='balance_transfer_create'),
    path('balance/reset/', views.balance_reset, name='balance_reset'),
    path('balance/to_funds/', views.balance_to_funds, name='balance_to_funds'),
    path('expense/create/', views.expense_create, name='expense_create'),
    path('expense/update/<int:pk>/', views.expense_update, name='expense_update'),
    path('expense/delete/<int:pk>/', views.expense_delete, name='expense_delete'),
    path('expense/delete_all/', views.expense_delete_all, name='expense_delete_all'),
    path('monitoring/', views.monitoring, name='monitoring'),
    path('savings/monitoring/', views.savings_monitoring, name='savings_monitoring'),
    path('funds/history/', views.funds_history, name='funds_history'),
    path('balance/history/', views.balance_history, name='balance_history'),
    path('about/', views.about, name='about'),
    path('contact/', views.contact, name='contact'),
    
    path('savings_goal/create/', views.savings_goal_create, name='savings_goal_create'),
    path('savings_goal/update/<int:pk>/', views.savings_goal_update, name='savings_goal_update'),
    path('savings_goal/delete/<int:pk>/', views.savings_goal_delete, name='savings_goal_delete'),

    path('export/report/', views.export_report, name='export_report'),

    # OTP-based password reset flow
    path('password-reset/', views.password_reset_request, name='password_reset_request'),
    path('password-reset/verify/', views.password_reset_verify, name='password_reset_verify'),
    path('password-reset/confirm/', views.password_reset_confirm, name='password_reset_confirm'),
]
