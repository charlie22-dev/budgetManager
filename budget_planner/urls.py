"""
URL configuration for budget_planner project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from django.views.generic import TemplateView
from django.views.decorators.cache import cache_control
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    # path('admin/', admin.site.urls),  # Admin hidden
    path('accounts/', include('allauth.urls')),
    path('', include('budgetapp.urls')),
    
    # PWA Service Worker (Cache control prevents stale files)
    path('serviceworker.js', cache_control(max_age=0, no_cache=True, must_revalidate=True)(
        TemplateView.as_view(template_name="serviceworker.js", content_type='application/javascript')
    ), name='serviceworker'),
]

# Serve media files during local development
if settings.DEBUG:
    urlpatterns += static(getattr(settings, 'MEDIA_URL', '/media/'), document_root=getattr(settings, 'MEDIA_ROOT', settings.BASE_DIR / 'media'))
