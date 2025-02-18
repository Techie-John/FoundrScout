from .views import home, dashboard, analyze_api
from django.urls import path

urlpatterns = [
    path('', home, name='home'),
    path('dashboard/', dashboard, name='dashboard'),
    path('api/analyze', analyze_api, name='analyze-api'),
]
