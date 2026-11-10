from django.urls import path
from . import views
from . import gathering_views

# Các đường dẫn bên dưới được gắn sau tiền tố /api/order/ của dự án.
urlpatterns = [
    path('gatherings/', gathering_views.gatherings),
    path('gatherings/<int:pk>/', gathering_views.gathering_detail),
    path('gatherings/<int:pk>/orders/', gathering_views.gathering_orders),
    path('gathering-orders/<int:pk>/', gathering_views.gathering_order_detail),
    path('session/', views.session_view),
    path('login/', views.login_view),
    path('logout/', views.logout_view),
    path('pricing/', views.pricing_view),
    path('contact/', views.contact_view),
    path('lookup/', views.lookup_view),
    path('shipments/', views.shipments_view),
    path('shipments/export/', views.shipment_export),
    path('shipments/<int:pk>/', views.shipment_detail),
    path('shipments/<int:pk>/history/', views.shipment_history),
    path('shipments/<int:pk>/payments/', views.shipment_payments),
    path('employees/', views.employees_view),
    path('employees/<int:pk>/', views.employee_detail),
]
