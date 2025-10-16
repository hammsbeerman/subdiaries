from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponse, HttpResponseBadRequest, HttpResponseForbidden
from django.template.loader import render_to_string
from django.views.decorators.http import require_GET
from django.contrib import messages
from .models import UserProfile, SocialLink, ProfileImage, CustomField
from .forms import (
    UserProfileForm,
    SocialFormSet,
    ImageFormSet,
    CustomFieldItemForm as CustomFieldForm,  # alias so existing code still works
)
from .permissions import get_target_user_or_404
from django.utils.html import format_html

# ...existing imports and views...

def _next_form_index(prefix, request):
    total_key = f"{prefix}-TOTAL_FORMS"
    try:
        return int(request.GET.get("index", request.POST.get(total_key, "0")))
    except ValueError:
        return 0

def _get_profile_for(request, user_id=None):
    if user_id and int(user_id) != request.user.id:
        # add authorization checks as needed
        return get_object_or_404(UserProfile, user__id=user_id)
    return get_object_or_404(UserProfile, user=request.user)

@login_required
@require_GET
def social_form_row(request):
    profile = request.user.profile  # editing own; for manager view, accept ?user_id
    prefix = "soc"
    index = _next_form_index(prefix, request)
    fs = SocialFormSet(instance=profile, prefix=prefix)
    form = fs.empty_form
    form.prefix = f"{prefix}-{index}"
    html = render_to_string("journal/partials/profile_social_row.html", {"form": form}, request)
    # tiny snippet that bumps TOTAL_FORMS on the page
    bump = format_html(
        "<script>const tf=document.querySelector('[name=\"{}-TOTAL_FORMS\"]'); if(tf) tf.value=parseInt(tf.value||'0')+1;</script>",
        prefix
    )
    return HttpResponse(html + bump)

@login_required
@require_GET
def image_form_row(request):
    profile = request.user.profile
    prefix = "img"
    index = _next_form_index(prefix, request)
    fs = ImageFormSet(instance=profile, prefix=prefix)
    form = fs.empty_form
    form.prefix = f"{prefix}-{index}"
    html = render_to_string("journal/partials/profile_image_row.html", {"form": form}, request)
    bump = format_html(
        "<script>const tf=document.querySelector('[name=\"{}-TOTAL_FORMS\"]'); if(tf) tf.value=parseInt(tf.value||'0')+1;</script>",
        prefix
    )
    return HttpResponse(html + bump)

@login_required
def profile_edit(request, user_id=None):
    profile = _get_profile_for(request, user_id)

    if request.method == "POST":
        form = UserProfileForm(request.POST, request.FILES, instance=profile)
        social_fs = SocialFormSet(request.POST, instance=profile, prefix="social")
        image_fs = ImageFormSet(request.POST, request.FILES, instance=profile, prefix="image")
        custom_form = CustomFieldForm(request.POST, prefix="custom")
        if form.is_valid() and social_fs.is_valid() and image_fs.is_valid():
            form.save()
            social_fs.save()
            image_fs.save()
            # optional: handle a single “add custom field” form
            if custom_form.is_valid() and custom_form.cleaned_data:
                cf = custom_form.save(commit=False)
                cf.profile = profile
                cf.save()
            messages.success(request, "Profile updated.")
            return redirect("journal:profile_detail")
    else:
        form = UserProfileForm(instance=profile)
        social_fs = SocialFormSet(instance=profile, prefix="social")
        image_fs = ImageFormSet(instance=profile, prefix="image")
        custom_form = CustomFieldForm(prefix="custom")

    return render(
        request,
        "journal/profile_edit.html",
        {
            "profile": profile,
            "form": form,
            "social_fs": social_fs,
            "image_fs": image_fs,
            "custom_form": custom_form,
            "target_user": profile.user,
        },
    )

# ---- HTMX row adders (now with user_id) ----

def _next_form_index(prefix, request):
    try:
        return int(request.GET.get("index", request.POST.get(f"{prefix}-TOTAL_FORMS", "0")))
    except ValueError:
        return 0

@login_required
@require_GET
def social_form_row(request, user_id: int | None = None):
    target_user = get_target_user_or_404(request.user, user_id)
    profile, _ = UserProfile.objects.get_or_create(user=target_user)
    prefix = "soc"
    idx = _next_form_index(prefix, request)
    fs = SocialFormSet(instance=profile, prefix=prefix)
    form = fs.empty_form
    form.prefix = f"{prefix}-{idx}"
    html = render_to_string("journal/partials/profile_social_row.html", {"form": form}, request)
    bump = f"<script>const tf=document.querySelector('[name=\"{prefix}-TOTAL_FORMS\"]');if(tf)tf.value=parseInt(tf.value||'0')+1;</script>"
    return HttpResponse(html + bump)

@login_required
@require_GET
def image_form_row(request, user_id: int | None = None):
    target_user = get_target_user_or_404(request.user, user_id)
    profile, _ = UserProfile.objects.get_or_create(user=target_user)
    prefix = "img"
    idx = _next_form_index(prefix, request)
    fs = ImageFormSet(instance=profile, prefix=prefix)
    form = fs.empty_form
    form.prefix = f"{prefix}-{idx}"
    html = render_to_string("journal/partials/profile_image_row.html", {"form": form}, request)
    bump = f"<script>const tf=document.querySelector('[name=\"{prefix}-TOTAL_FORMS\"]');if(tf)tf.value=parseInt(tf.value||'0')+1;</script>"
    return HttpResponse(html + bump)

def profile_detail(request, user_id=None):
    """
    Back-compat alias: old routes pointed at profile_detail.
    We now redirect to the edit page (self or specific user).
    """
    if user_id:
        return redirect("journal:profile_edit_user", user_id=user_id)
    return redirect("journal:profile_edit")