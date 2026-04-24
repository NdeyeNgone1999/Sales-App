from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.models import User
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q
from .forms import (
    CustomUserCreationForm,
    CustomAuthenticationForm,
    UserProfileForm,
    RoleForm,
    AdminPasswordChangeForm,
)
from .models import UserProfile, Role


@login_required
@user_passes_test(lambda u: u.is_staff, login_url="/accounts/login/")
def register_view(request):
    """Admin-only user creation view"""
    if request.method == "POST":
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            username = form.cleaned_data.get("username")
            messages.success(
                request,
                f"Account created for {username}! The user registration is pending approval. "
                f"An email notification will be sent once the account is approved.",
            )
            return redirect("accounts:user_list")
        else:
            messages.error(request, "Please correct the errors below.")
    else:
        form = CustomUserCreationForm()

    context = {
        "form": form,
        "page_title": "Create New User Account",
        "is_admin_creation": True,
    }
    return render(request, "accounts/register.html", context)


def login_view(request):
    """User login view"""
    if request.method == "POST":
        form = CustomAuthenticationForm(request, data=request.POST)
        if form.is_valid():
            username = form.cleaned_data.get("username")
            password = form.cleaned_data.get("password")
            user = authenticate(username=username, password=password)
            if user is not None:
                # Check if user account is approved
                if (
                    hasattr(user, "profile")
                    and user.profile.approval_status != "approved"
                ):
                    if user.profile.approval_status == "pending":
                        messages.warning(
                            request,
                            "Your account is pending approval. Please wait for an administrator to review your registration.",
                        )
                    elif user.profile.approval_status == "rejected":
                        messages.error(
                            request,
                            "Your account registration was not approved. Please contact an administrator for more information.",
                        )
                    return render(request, "accounts/login.html", {"form": form})

                login(request, user)
                messages.success(
                    request, f"Welcome back, {user.first_name or user.username}!"
                )
                next_url = request.GET.get("next", "pages:home")
                return redirect(next_url)
            else:
                messages.error(request, "Invalid username or password.")
        else:
            messages.error(request, "Please correct the errors below.")
    else:
        form = CustomAuthenticationForm()

    return render(request, "accounts/login.html", {"form": form})


@login_required
def logout_view(request):
    """User logout view"""
    logout(request)
    messages.success(request, "You have been logged out successfully.")
    return redirect("accounts:login")


@login_required
def profile_view(request):
    """User profile view"""
    profile = request.user.profile
    return render(request, "accounts/profile.html", {"profile": profile})


@login_required
def edit_profile_view(request):
    """Edit user profile view"""
    profile = request.user.profile

    if request.method == "POST":
        form = UserProfileForm(request.POST, instance=profile)
        if form.is_valid():
            form.save()
            messages.success(request, "Your profile has been updated successfully!")
            return redirect("accounts:profile")
        else:
            messages.error(request, "Please correct the errors below.")
    else:
        form = UserProfileForm(instance=profile)

    return render(request, "accounts/edit_profile.html", {"form": form})


def is_admin(user):
    """Check if user is admin"""
    return user.is_authenticated and (
        user.is_superuser
        or (
            hasattr(user, "profile")
            and user.profile.role
            and user.profile.role.name == "admin"
        )
    )


@user_passes_test(is_admin)
def user_list_view(request):
    """List all users (admin only)"""
    search_query = request.GET.get("search", "")
    users = User.objects.all()

    if search_query:
        users = users.filter(
            Q(username__icontains=search_query)
            | Q(first_name__icontains=search_query)
            | Q(last_name__icontains=search_query)
            | Q(email__icontains=search_query)
        )

    users = users.order_by("username")

    # Pagination
    paginator = Paginator(users, 20)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    return render(
        request,
        "accounts/user_list.html",
        {"page_obj": page_obj, "search_query": search_query},
    )


@user_passes_test(is_admin)
def user_detail_view(request, user_id):
    """View user details (admin only)"""
    user = get_object_or_404(User, id=user_id)
    return render(request, "accounts/user_detail.html", {"user_obj": user})


@user_passes_test(is_admin)
def edit_user_view(request, user_id):
    """Edit user (admin only)"""
    user = get_object_or_404(User, id=user_id)
    profile = user.profile

    if request.method == "POST":
        form = UserProfileForm(request.POST, instance=profile)
        if form.is_valid():
            form.save()
            messages.success(
                request, f"User {user.username} has been updated successfully!"
            )
            return redirect("accounts:user_detail", user_id=user.id)
        else:
            messages.error(request, "Please correct the errors below.")
    else:
        form = UserProfileForm(instance=profile)

    return render(request, "accounts/edit_user.html", {"form": form, "user_obj": user})


@user_passes_test(is_admin)
def toggle_user_status_view(request, user_id):
    """Toggle user active status (admin only)"""
    user = get_object_or_404(User, id=user_id)

    if request.method == "POST":
        user.is_active = not user.is_active
        user.save()

        status = "activated" if user.is_active else "deactivated"
        messages.success(request, f"User {user.username} has been {status}!")

    return redirect("accounts:user_detail", user_id=user.id)


@user_passes_test(is_admin)
def delete_user_view(request, user_id):
    """Delete user (admin only)"""
    user = get_object_or_404(User, id=user_id)

    # Prevent admin from deleting themselves
    if user == request.user:
        messages.error(request, "You cannot delete your own account!")
        return redirect("accounts:user_detail", user_id=user.id)

    # Prevent deletion of superusers by non-superusers
    if user.is_superuser and not request.user.is_superuser:
        messages.error(request, "You cannot delete a superuser account!")
        return redirect("accounts:user_detail", user_id=user.id)

    if request.method == "POST":
        username = user.username
        user_email = user.email

        # Create notification about user deletion
        from .models import AdminNotification

        AdminNotification.objects.create(
            title=f"User Deleted: {username}",
            message=f"User {username} ({user_email}) has been deleted by {request.user.username}",
            notification_type="user_deleted",
            related_user=request.user,  # The admin who deleted the user
        )

        # Delete the user (this will cascade to UserProfile)
        user.delete()

        messages.success(request, f'User "{username}" has been deleted successfully!')
        return redirect("accounts:user_list")

    return render(request, "accounts/delete_user.html", {"user_obj": user})


@user_passes_test(is_admin)
def change_password_view(request, user_id):
    """Change user password (admin only)"""
    user = get_object_or_404(User, id=user_id)

    # Prevent changing password of superusers by non-superusers
    if user.is_superuser and not request.user.is_superuser:
        messages.error(
            request,
            "Vous ne pouvez pas modifier le mot de passe d'un superutilisateur!",
        )
        return redirect("accounts:user_detail", user_id=user.id)

    if request.method == "POST":
        form = AdminPasswordChangeForm(request.POST)
        if form.is_valid():
            new_password = form.cleaned_data["new_password1"]
            user.set_password(new_password)
            user.save()

            # Create notification about password change
            from .models import AdminNotification

            AdminNotification.objects.create(
                title=f"Mot de passe modifié: {user.username}",
                message=f"Le mot de passe de {user.username} a été changé par {request.user.username}",
                notification_type="user_updated",
                related_user=user,
            )

            messages.success(
                request,
                f"Le mot de passe de {user.username} a été modifié avec succès!",
            )
            return redirect("accounts:user_detail", user_id=user.id)
    else:
        form = AdminPasswordChangeForm()

    return render(
        request,
        "accounts/change_password.html",
        {"form": form, "user_obj": user},
    )


@user_passes_test(is_admin)
def role_list_view(request):
    """List all roles (admin only)"""
    roles = Role.objects.all()
    return render(request, "accounts/role_list.html", {"roles": roles})


@user_passes_test(is_admin)
def create_role_view(request):
    """Create new role (admin only)"""
    if request.method == "POST":
        form = RoleForm(request.POST)
        if form.is_valid():
            role = form.save()
            messages.success(
                request, f'Role "{role.name}" has been created successfully!'
            )
            return redirect("accounts:role_list")
        else:
            messages.error(request, "Please correct the errors below.")
    else:
        form = RoleForm()

    return render(request, "accounts/create_role.html", {"form": form})


@user_passes_test(is_admin)
def edit_role_view(request, role_id):
    """Edit role (admin only)"""
    role = get_object_or_404(Role, id=role_id)

    if request.method == "POST":
        form = RoleForm(request.POST, instance=role)
        if form.is_valid():
            form.save()
            messages.success(
                request, f'Role "{role.name}" has been updated successfully!'
            )
            return redirect("accounts:role_list")
        else:
            messages.error(request, "Please correct the errors below.")
    else:
        form = RoleForm(instance=role)

    return render(request, "accounts/edit_role.html", {"form": form, "role": role})


@user_passes_test(is_admin)
def delete_role_view(request, role_id):
    """Delete role (admin only)"""
    role = get_object_or_404(Role, id=role_id)

    if request.method == "POST":
        role_name = role.name
        role.delete()
        messages.success(request, f'Role "{role_name}" has been deleted successfully!')
        return redirect("accounts:role_list")

    return render(request, "accounts/delete_role.html", {"role": role})


def user_guide_view(request):
    """User guide and documentation"""
    return render(request, "accounts/user_guide.html")


@login_required
@user_passes_test(lambda u: u.is_staff)
def notifications_view(request):
    """View for managing admin notifications"""
    from .models import AdminNotification, approve_user, reject_user

    # Handle POST requests for approval/rejection
    if request.method == "POST":
        action = request.POST.get("action")
        notification_id = request.POST.get("notification_id")

        if notification_id:
            notification = get_object_or_404(AdminNotification, id=notification_id)
            user = notification.related_user

            if action == "approve" and user.profile.approval_status == "pending":
                approve_user(user.profile, request.user)
                notification.read_by.add(request.user)
                messages.success(request, f"User {user.username} has been approved!")

            elif action == "reject" and user.profile.approval_status == "pending":
                admin_notes = request.POST.get(
                    "admin_notes", "Rejected via notifications"
                )
                reject_user(user.profile, admin_notes)
                notification.read_by.add(request.user)
                messages.success(request, f"User {user.username} has been rejected!")

            elif action == "mark_read":
                notification.read_by.add(request.user)
                if not notification.is_read:
                    notification.is_read = True
                    notification.save()
                messages.success(request, "Notification marked as read!")

    # Get notifications (only unread ones that user hasn't read)
    notifications = (
        AdminNotification.objects.exclude(read_by=request.user)
        .filter(is_read=False)
        .order_by("-created_at")
    )

    # Paginate
    paginator = Paginator(notifications, 10)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    # Get pending registrations
    pending_registrations = UserProfile.objects.filter(
        approval_status="pending"
    ).select_related("user")

    context = {
        "page_obj": page_obj,
        "pending_registrations": pending_registrations,
        "total_unread": notifications.count(),
    }

    return render(request, "accounts/notifications.html", context)
