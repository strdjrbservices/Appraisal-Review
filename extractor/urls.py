from django.urls import path
from . import views
from django.views.generic.base import RedirectView
from django.contrib.staticfiles.storage import staticfiles_storage

urlpatterns = [
    path('', views.upload_pdf, name='upload_pdf'),
    path('register/', views.register_view, name='register'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('extract/<str:filename>/<str:section_name>/', views.extract_section, name='extract_section'),
    path('compare/', views.compare_pdfs_upload_view, name='compare_pdfs_upload'),
    path('compare/process/', views.compare_pdfs_process_view, name='compare_pdfs_process'),
    path('compare-html-pdf/', views.compare_html_pdf_upload_view, name='compare_html_pdf_upload'),
    path('compare-html-pdf/process/', views.compare_html_pdf_process_view, name='compare_html_pdf_process'),
    path('generate-report/', views.generate_report, name='generate_report'),
    path('escalation-check/', views.escalation_check_upload_view, name='escalation_check_upload'),
    path('escalation-check/process/', views.escalation_check_process_view, name='escalation_check_process'),
    
    # API endpoint for fetching section data
    path('api/data/<str:filename>/<str:section_name>/', views.get_section_data_api, name='get_section_data_api'),

    # Add this line to serve the favicon
    path('favicon.ico', RedirectView.as_view(url=staticfiles_storage.url('extractor/img/favicon.ico'))),
]