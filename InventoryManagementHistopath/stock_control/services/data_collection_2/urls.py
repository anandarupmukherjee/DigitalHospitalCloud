from django.urls import path
from .create_withdrawal import create_withdrawal

app_name = 'data_collection_2'

urlpatterns = [
    path('create_withdrawal/', create_withdrawal, name='create_withdrawal'),
]
