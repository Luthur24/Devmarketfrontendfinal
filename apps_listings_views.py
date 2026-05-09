"""
Developer Marketplace - Listings Views Module

This module contains all CRUD views for developer services/products in the marketplace.
It handles:
- Service creation/editing/deletion
- Service listing with search/filter capabilities
- Category-based filtering
- Pagination for large result sets

All views enforce proper authentication and authorization.
"""

from django.shortcuts import render, get_object_or_404, redirect
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.urls import reverse_lazy
from django.db.models import Q
from django.core.paginator import Paginator
from django.contrib import messages
from django.http import HttpResponseForbidden
from django.conf import settings
import logging

from .models import Service, Category
from .forms import ServiceForm

# Configure logging
logger = logging.getLogger(__name__)

class ServiceListView(ListView):
    """
    View for listing all services with search and filter capabilities.

    Attributes:
        model (Model): The Service model
        template_name (str): Template to render
        context_object_name (str): Name for services in template context
        paginate_by (int): Number of services per page
    """
    model = Service
    template_name = 'listings/service_list.html'
    context_object_name = 'services'
    paginate_by = 10

    def get_queryset(self):
        """
        Get the queryset of services with optional search and filter.

        Returns:
            QuerySet: Filtered queryset of services
        """
        queryset = super().get_queryset().filter(is_active=True)

        # Search functionality
        search_query = self.request.GET.get('search')
        if search_query:
            queryset = queryset.filter(
                Q(title__icontains=search_query) |
                Q(description__icontains=search_query) |
                Q(tags__name__icontains=search_query)
            ).distinct()

        # Category filter
        category_id = self.request.GET.get('category')
        if category_id:
            queryset = queryset.filter(category_id=category_id)

        return queryset.order_by('-created_at')

    def get_context_data(self, **kwargs):
        """
        Add additional context data to the template.

        Args:
            **kwargs: Additional keyword arguments

        Returns:
            dict: Context data for the template
        """
        context = super().get_context_data(**kwargs)
        context['categories'] = Category.objects.all()
        context['search_query'] = self.request.GET.get('search', '')
        context['selected_category'] = self.request.GET.get('category', '')
        return context

class ServiceDetailView(DetailView):
    """
    View for displaying a single service.

    Attributes:
        model (Model): The Service model
        template_name (str): Template to render
        context_object_name (str): Name for service in template context
    """
    model = Service
    template_name = 'listings/service_detail.html'
    context_object_name = 'service'

    def get_object(self, queryset=None):
        """
        Get the service object, ensuring it's active.

        Args:
            queryset (QuerySet, optional): Custom queryset

        Returns:
            Service: The service object

        Raises:
            Http404: If service is not found or not active
        """
        obj = super().get_object(queryset)
        if not obj.is_active:
            raise Http404("Service not found")
        return obj

class ServiceCreateView(LoginRequiredMixin, CreateView):
    """
    View for creating a new service.

    Attributes:
        model (Model): The Service model
        form_class (Form): The ServiceForm
        template_name (str): Template to render
        success_url (str): URL to redirect after successful creation
    """
    model = Service
    form_class = ServiceForm
    template_name = 'listings/service_form.html'
    success_url = reverse_lazy('listings:service-list')

    def form_valid(self, form):
        """
        Save the form with the current user as the owner.

        Args:
            form (Form): The validated form

        Returns:
            HttpResponse: Redirect to success URL
        """
        form.instance.owner = self.request.user
        messages.success(self.request, 'Service created successfully!')
        return super().form_valid(form)

    def form_invalid(self, form):
        """
        Handle invalid form submission.

        Args:
            form (Form): The invalid form

        Returns:
            HttpResponse: Rendered form with errors
        """
        messages.error(self.request, 'Please correct the errors below.')
        return super().form_invalid(form)

class ServiceUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    """
    View for updating an existing service.

    Attributes:
        model (Model): The Service model
        form_class (Form): The ServiceForm
        template_name (str): Template to render
        success_url (str): URL to redirect after successful update
    """
    model = Service
    form_class = ServiceForm
    template_name = 'listings/service_form.html'
    success_url = reverse_lazy('listings:service-list')

    def test_func(self):
        """
        Check if the current user is the owner of the service.

        Returns:
            bool: True if user is owner, False otherwise
        """
        service = self.get_object()
        return self.request.user == service.owner

    def form_valid(self, form):
        """
        Save the form and show success message.

        Args:
            form (Form): The validated form

        Returns:
            HttpResponse: Redirect to success URL
        """
        messages.success(self.request, 'Service updated successfully!')
        return super().form_valid(form)

    def form_invalid(self, form):
        """
        Handle invalid form submission.

        Args:
            form (Form): The invalid form

        Returns:
            HttpResponse: Rendered form with errors
        """
        messages.error(self.request, 'Please correct the errors below.')
        return super().form_invalid(form)

class ServiceDeleteView(LoginRequiredMixin, UserPassesTestMixin, DeleteView):
    """
    View for deleting a service.

    Attributes:
        model (Model): The Service model
        template_name (str): Template to render
        success_url (str): URL to redirect after successful deletion
    """
    model = Service
    template_name = 'listings/service_confirm_delete.html'
    success_url = reverse_lazy('listings:service-list')

    def test_func(self):
        """
        Check if the current user is the owner of the service.

        Returns:
            bool: True if user is owner, False otherwise
        """
        service = self.get_object()
        return self.request.user == service.owner

    def delete(self, request, *args, **kwargs):
        """
        Handle the deletion of the service.

        Args:
            request (HttpRequest): The request object
            *args: Additional positional arguments
            **kwargs: Additional keyword arguments

        Returns:
            HttpResponse: Redirect to success URL
        """
        messages.success(self.request, 'Service deleted successfully!')
        return super().delete(request, *args, **kwargs)

def toggle_service_status(request, pk):
    """
    Toggle the active status of a service.

    Args:
        request (HttpRequest): The request object
        pk (int): Primary key of the service

    Returns:
        HttpResponse: Redirect to service list
    """
    if not request.user.is_authenticated:
        return HttpResponseForbidden()

    service = get_object_or_404(Service, pk=pk)

    if request.user != service.owner:
        return HttpResponseForbidden()

    try:
        service.is_active = not service.is_active
        service.save()
        status = "activated" if service.is_active else "deactivated"
        messages.success(request, f'Service {status} successfully!')
    except Exception as e:
        logger.error(f"Error toggling service status: {str(e)}")
        messages.error(request, 'An error occurred while updating the service status.')

    return redirect('listings:service-list')

def service_search(request):
    """
    Handle service search requests.

    Args:
        request (HttpRequest): The request object

    Returns:
        HttpResponse: Rendered search results
    """
    search_query = request.GET.get('search', '')
    category_id = request.GET.get('category', '')

    services = Service.objects.filter(is_active=True)

    if search_query:
        services = services.filter(
            Q(title__icontains=search_query) |
            Q(description__icontains=search_query) |
            Q(tags__name__icontains=search_query)
        ).distinct()

    if category_id:
        services = services.filter(category_id=category_id)

    paginator = Paginator(services.order_by('-created_at'), 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'services': page_obj,
        'categories': Category.objects.all(),
        'search_query': search_query,
        'selected_category': category_id,
    }

    return render(request, 'listings/service_list.html', context)