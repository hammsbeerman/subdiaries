
# journal/views.py
from django.contrib.auth.decorators import login_required
from django.contrib.auth import get_user_model, login, logout
from django.core.mail import send_mail
from django.conf import settings
from django.utils.crypto import get_random_string
from django.http import HttpResponse, HttpResponseForbidden, JsonResponse
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.cache import never_cache
from django.template.loader import render_to_string
from django.urls import reverse
from django.views.decorators.http import require_POST, require_http_methods
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.utils import timezone
from django.db import transaction
from .models import Entry, EntryImage, Tab, Membership, Organization, Invite, UserProfile, SocialLink, ProfileImage, CustomField
from .forms import EntryForm, MemberAddForm, InviteForm, AcceptInviteForm, TabForm, TabRenameForm, ProfileMiniForm, SubuserCreateForm, SocialLinkForm, UserProfileForm, SocialFormSet, ImageFormSet, CustomFieldItemForm as CustomFieldForm
from django import forms
from django.template.loader import render_to_string
from .utils import send_invite_email, send_invite_sms, get_user_org, is_htmx, user_is_moderator, can_manage_member
from journal.constants import ROLE_CHOICES
from journal.models import UserProfile
from journal.permissions import can_view_profile, can_edit_profile

U = get_user_model()

@login_required
@ensure_csrf_cookie
@never_cache
def ok(request):
    return HttpResponse("OK", content_type="text/plain")



def _get_profile(user):
    profile, _ = UserProfile.objects.get_or_create(user=user)
    return profile

def site_base_url(request):
    # naive base URL for dev; adjust if behind proxy
    scheme = "https" if request.is_secure() else "http"
    return f"{scheme}://{request.get_host()}"

# def get_user_org(user):
#     m = Membership.objects.select_related("org").filter(user=request.user).first()
#     org = m.org if m else None

@login_required
def index(request):
    org = get_user_org(request.user)   # <-- pass user
    if not org:
        return redirect("journal:profile_detail")

    tabs = Tab.objects.filter(org=org, enabled=True)
    entries = (Entry.objects
               .filter(org=org, status=Entry.Status.APPROVED)
               .prefetch_related("tabs", "images")
               .select_related("author")
               .order_by("-created_at"))
    return render(request, "journal/index.html", {"org": org, "tabs": tabs, "entries": entries})

@login_required
@transaction.atomic
def entry_create(request):
    org = get_user_org(request.user)

    if request.method == "POST":
        form = EntryForm(request.POST, request.FILES)
        form.fields["tabs"].queryset = Tab.objects.filter(org=org, enabled=True)

        if form.is_valid():
            entry = form.save(commit=False)
            entry.author = request.user
            entry.org = org

            if "submit" in request.POST:
                entry.status = Entry.Status.PENDING
                entry.submitted_at = timezone.now()
            else:
                entry.status = Entry.Status.DRAFT

            entry.save()

            # Tabs (prefer form; fall back to a default in this org)
            tabs = list(form.cleaned_data.get("tabs") or [])
            if not tabs:
                default_tab, _ = Tab.objects.get_or_create(
                    org=org, name="General",
                    defaults={"owner": request.user, "enabled": True},
                )
                tabs = [default_tab]
            entry.tabs.set(tabs)  # we manage M2M ourselves; no form.save_m2m()

            # Images
            for f in request.FILES.getlist("images"):
                EntryImage.objects.create(entry=entry, image=f)

            messages.success(request, "Submitted for review." if "submit" in request.POST else "Draft saved.")
            return redirect("journal:index")

    else:
        form = EntryForm()
        form.fields["tabs"].queryset = Tab.objects.filter(org=org, enabled=True)

    return render(request, "journal/entry_form.html", {"form": form})



# ---------- Drafts (HTMX) ----------
@login_required
def drafts(request):
    rows = (Entry.objects
            .filter(author=request.user, status=Entry.Status.DRAFT)
            .prefetch_related("tabs"))
    if is_htmx(request):
        html = render_to_string("journal/partials/drafts_table.html", {"entries": rows}, request)
        return HttpResponse(html)
    return render(request, "journal/drafts.html", {"entries": rows})

@login_required
def entry_detail(request, pk):
    entry = get_object_or_404(Entry.objects.select_related("author").prefetch_related("tabs","images"), pk=pk)
    return render(request, "journal/entry_detail.html", {"entry": entry})

@login_required
@transaction.atomic
def entry_edit(request, pk):
    entry = get_object_or_404(Entry, pk=pk, author=request.user)
    if request.method == "POST":
        form = EntryForm(request.POST, request.FILES, instance=entry)
        form.fields["tabs"].queryset = Tab.objects.filter(org=entry.org, enabled=True)
        if form.is_valid():
            entry = form.save()
            for f in request.FILES.getlist("images"):
                EntryImage.objects.create(entry=entry, image=f)
            messages.success(request, "Entry updated.")
            return redirect("journal:entry_detail", pk=entry.pk)
    else:
        form = EntryForm(instance=entry)
        form.fields["tabs"].queryset = Tab.objects.filter(org=entry.org, enabled=True)
    return render(request, "journal/entry_form.html", {"form": form})

# --- Moderator / management ---

# ---------- Review queue (HTMX, partial path updated) ----------
@login_required
def review_queue(request):
    if not user_is_moderator(request.user):
        return HttpResponseForbidden()
    org = get_user_org(request.user)
    rows = Entry.objects.filter(org=org, status=Entry.Status.PENDING).select_related("author")
    if is_htmx(request):
        html = render_to_string("journal/partials/review_table.html", {"entries": rows}, request)
        return HttpResponse(html)
    return render(request, "journal/review_queue.html", {"entries": rows})




@login_required
def tabs(request):
    if not user_is_moderator(request.user):
        return HttpResponseForbidden()
    org = get_user_org(request.user)
    rows = Tab.objects.filter(org=org).order_by("-enabled", "name")
    form = TabForm()
    return render(request, "journal/tabs.html", {"tabs": rows, "form": form})

def tabs_table(request):
    """Return just the table (HTMX refresh target)."""
    if not user_is_moderator(request.user):
        return HttpResponseForbidden()
    org = get_user_org(request.user)
    rows = Tab.objects.filter(org=org).order_by("-enabled", "name")
    html = render_to_string("journal/partials/tabs_table.html", {"tabs": rows}, request=request)
    return HttpResponse(html)


@login_required
@require_POST
def tab_create(request):
    if not user_is_moderator(request.user):
        return HttpResponseForbidden()
    org = get_user_org(request.user)

    name = " ".join((request.POST.get("name") or "").split()).strip()
    enabled = bool(request.POST.get("enabled"))

    if name:
        Tab.objects.create(org=org, name=name, enabled=enabled, created_by=request.user)

    # Always re-render table (and optionally clear any error banner OOB)
    rows = Tab.objects.filter(org=org).order_by("-enabled", "name")
    html = render_to_string("journal/partials/tabs_table.html", {"tabs": rows}, request=request)
    return HttpResponse(html)

@login_required
@require_POST
def tab_toggle(request, pk):
    if not user_is_moderator(request.user):
        return HttpResponseForbidden()
    org = get_user_org(request.user)
    t = get_object_or_404(Tab, pk=pk, org=org)
    t.enabled = not t.enabled
    t.save(update_fields=["enabled"])

    rows = Tab.objects.filter(org=org).order_by("-enabled", "name")
    html = render_to_string("journal/partials/tabs_table.html", {"tabs": rows}, request=request)
    return HttpResponse(html)

# --- Members admin ---
ROLE_CHOICES = [("moderator","moderator"), ("author","author"), ("subauthor","subauthor")]

@login_required
def members(request):
    if not user_is_moderator(request.user):
        return HttpResponse(status=403)

    org = get_user_org(request.user)

    # Single source of truth: `members` (not rows/memberships)
    members = (
        Membership.objects
        .filter(org=org)                      # <-- filter by org
        .select_related("user", "org")
        .order_by("user__first_name", "user__last_name", "user__username")
    )

    form = MemberAddForm()

    ctx = {
        "org": org,
        "members": members,                   # <-- consistent key
        "role_choices": getattr(Membership, "Role", None).choices if hasattr(Membership, "Role") else ROLE_CHOICES,
        "form": form,
    }

    if is_htmx(request):
        html = render_to_string("journal/partials/members_table.html", ctx, request=request)
        return HttpResponse(html)

    return render(request, "journal/members.html", ctx)

@login_required
@require_POST
def member_set_role(request, pk):
    if not user_is_moderator(request.user):
        return HttpResponseForbidden()
    org = get_user_org(request.user)
    m = get_object_or_404(Membership, pk=pk, org=org)
    role = request.POST.get("role")
    if role in {r for r,_ in ROLE_CHOICES}:
        m.role = role; m.save(update_fields=["role"])
    rows = Membership.objects.filter(org=org).select_related("user")
    html = render_to_string("journal/partials/members_table.html", {"memberships": rows, "ROLE_CHOICES": ROLE_CHOICES}, request)
    return HttpResponse(html)

@login_required
def plans(request):
    if not user_is_moderator(request.user):
        messages.error(request, "Not authorized.")
        return redirect("journal:index")
    # Billing toggles off; show read-only placeholder
    return render(request, "journal/plans.html", {"enabled": False})

@login_required
def profile(request):
    return render(request, "journal/profile.html", {"user": request.user})

@login_required
@require_POST
def entry_approve(request, pk):
    if not user_is_moderator(request.user):
        return HttpResponseForbidden()
    org = get_user_org(request.user)
    e = get_object_or_404(Entry, pk=pk, org=org)
    e.status = Entry.Status.APPROVED
    e.approved_at = timezone.now()
    e.save(update_fields=["status","approved_at"])
    rows = Entry.objects.filter(org=org, status=Entry.Status.PENDING).select_related("author")
    html = render_to_string("journal/partials/review_table.html", {"entries": rows}, request)
    return HttpResponse(html)

@login_required
@require_POST
def entry_reject(request, pk):
    if not user_is_moderator(request.user):
        return HttpResponseForbidden()
    org = get_user_org(request.user)
    e = get_object_or_404(Entry, pk=pk, org=org)
    e.status = Entry.Status.DRAFT
    e.save(update_fields=["status"])
    rows = Entry.objects.filter(org=org, status=Entry.Status.PENDING).select_related("author")
    html = render_to_string("journal/partials/review_table.html", {"entries": rows}, request)
    return HttpResponse(html)

@login_required
@require_POST
def entry_publish(request, pk):
    e = get_object_or_404(Entry, pk=pk, author=request.user, status=Entry.Status.DRAFT)
    e.status = Entry.Status.PENDING
    e.submitted_at = timezone.now()
    e.save(update_fields=["status","submitted_at"])
    rows = Entry.objects.filter(author=request.user, status=Entry.Status.DRAFT).prefetch_related("tabs")
    html = render_to_string("journal/partials/drafts_table.html", {"entries": rows}, request)
    return HttpResponse(html)

@login_required
@require_POST
def entry_delete(request, pk):
    e = get_object_or_404(Entry, pk=pk, author=request.user, status=Entry.Status.DRAFT)
    e.delete()
    rows = Entry.objects.filter(author=request.user, status=Entry.Status.DRAFT).prefetch_related("tabs")
    html = render_to_string("journal/partials/drafts_table.html", {"entries": rows}, request)
    return HttpResponse(html)

@login_required
@require_POST
def member_add(request):
    if not user_is_moderator(request.user):
        return HttpResponse(status=403)
    org = get_user_org(request.user)
    form = MemberAddForm(request.POST)
    if form.is_valid():
        U = get_user_model()
        username = form.cleaned_data["username"]
        email = form.cleaned_data.get("email", "")
        password = form.cleaned_data.get("password") or get_random_string(12)
        user = U.objects.create_user(username=username, email=email, password=password)
        Membership.objects.get_or_create(user=user, org=org,
                                         defaults={"role": form.cleaned_data["role"]})
        # Re-render members table and blank form using HTMX OOB swaps
        rows = Membership.objects.filter(org=org).select_related("user")
        table_html = render_to_string("journal/partials/members_table.html",
                                      {"memberships": rows, "ROLE_CHOICES": ROLE_CHOICES}, request)
        form_html  = render_to_string("journal/partials/member_add_form.html",
                                      {"form": MemberAddForm()}, request)
        return HttpResponse(table_html + form_html)  # form has hx-swap-oob
    else:
        # Return only the form (with errors) via OOB, leave table as-is
        form_html = render_to_string("journal/partials/member_add_form.html",
                                     {"form": form}, request)
        return HttpResponse(form_html)

@login_required
def member_invite(request):
    if not user_is_moderator(request.user):
        return HttpResponseForbidden()
    org = get_user_org(request.user)

    if request.method == "POST":
        form = InviteForm(request.POST)
        if form.is_valid():
            inv = Invite.create(
                org=org,
                role=form.cleaned_data["role"],
                created_by=request.user,
                email=form.cleaned_data.get("email","") if form.cleaned_data["delivery"]=="email" else "",
                phone=form.cleaned_data.get("phone","") if form.cleaned_data["delivery"]=="sms" else "",
                delivery=form.cleaned_data["delivery"],
            )
            accept_url = site_base_url(request) + reverse("journal:invite_accept", args=[inv.token])

            if inv.delivery == "email":
                subject = f"You're invited to {org.name}"
                body = render_to_string("journal/partials/invite_email.txt", {"org": org, "accept_url": accept_url})
                send_invite_email(inv.email, subject, body)
                dev_link = accept_url
            else:
                body = f"Join {org.name}: {accept_url}"
                send_invite_sms(inv.phone, body)
                dev_link = accept_url

            # Refresh members table + show link (dev helper)
            rows = Membership.objects.filter(org=org).select_related("user")
            table_html = render_to_string("journal/partials/members_table.html",
                                          {"memberships": rows, "ROLE_CHOICES": ROLE_CHOICES}, request)
            notice_html = f'<div class="alert alert-info" id="invite-link" hx-swap-oob="true">Invite sent. Dev link: <a href="{dev_link}">{dev_link}</a></div>'
            # Reset the form via OOB
            form_html = render_to_string("journal/partials/member_invite_form.html",
                                         {"invite_form": InviteForm()}, request)
            return HttpResponse(table_html + notice_html + form_html)

        # invalid -> return form only via OOB
        form_html = render_to_string("journal/partials/member_invite_form.html", {"invite_form": form}, request)
        return HttpResponse(form_html)

    # GET
    form = InviteForm()
    html = render_to_string("journal/partials/member_invite_form.html", {"invite_form": form}, request)
    return HttpResponse(html)

def invite_accept(request, token):
    inv = Invite.objects.filter(token=token).select_related("org").first()
    if not inv or not inv.is_valid():
        return render(request, "journal/invite_invalid.html", {"reason": "Invalid or expired invite."})

    U = get_user_model()
    # If user is already logged in, attach and finish
    if request.user.is_authenticated:
        Membership.objects.get_or_create(user=request.user, org=inv.org, defaults={"role": inv.role})
        inv.mark_used(request.user)
        messages.success(request, f"Added to {inv.org.name}.")
        return redirect("journal:index")

    # Existing account? (email path preferred)
    existing = None
    if inv.email:
        existing = U.objects.filter(email__iexact=inv.email).first()
    elif inv.phone:
        # If you store phone on user profiles, look it up here; else skip.
        existing = None

    if existing:
        # Ask them to login, then come back here (Django auth will redirect back)
        login_url = reverse("login") + f"?next={reverse('journal:invite_accept', args=[inv.token])}"
        messages.info(request, "Please log in to accept this invite.")
        return redirect(login_url)

    # No existing account -> let them set username/password and create
    if request.method == "POST":
        form = AcceptInviteForm(request.POST)
        if form.is_valid():
            user = U.objects.create_user(
                username=form.cleaned_data["username"],
                email=inv.email or "",
                password=form.cleaned_data["password"],
            )
            Membership.objects.get_or_create(user=user, org=inv.org, defaults={"role": inv.role})
            inv.mark_used(user)
            login(request, user)
            return redirect("journal:index")
    else:
        suggested = (inv.email or "user").split("@")[0]
        form = AcceptInviteForm(initial={"username": suggested})

    return render(request, "journal/invite_accept.html", {"form": form, "org": inv.org})

@login_required
def tab_edit_form(request, pk):
    if not user_is_moderator(request.user):
        return HttpResponse(status=403)
    org = get_user_org(request.user)
    t = get_object_or_404(Tab, pk=pk, org=org)
    form = TabRenameForm(instance=t)
    html = render_to_string("journal/partials/tab_edit_row.html", {"t": t, "form": form}, request)
    return HttpResponse(html)

@login_required
@require_POST
def tab_save_row(request, pk: int):
    """Persist edits for one row, then return the refreshed table."""
    if not user_is_moderator(request.user):
        return HttpResponseForbidden()
    org = get_user_org(request.user)
    tab = get_object_or_404(Tab, pk=pk, org=org)

    name = " ".join((request.POST.get("name") or "").split()).strip()
    enabled = bool(request.POST.get("enabled"))

    if not name:
        rows = Tab.objects.filter(org=org).order_by("-enabled","name")
        html = render_to_string("journal/partials/tabs_table.html", {"tabs": rows}, request)
        html += '<div class="alert alert-danger mt-2" hx-swap-oob="true" id="tabs-error">Name is required.</div>'
        return HttpResponse(html)

    if tab.name != name or tab.enabled != enabled:
        tab.name = name
        tab.enabled = enabled
        tab.save(update_fields=["name", "enabled"])

    rows = Tab.objects.filter(org=org).order_by("-enabled","name")
    html = render_to_string("journal/partials/tabs_table.html", {"tabs": rows}, request)
    html += '<div id="tabs-error" hx-swap-oob="true"></div>'
    return HttpResponse(html)

@login_required
def tab_edit_row(request, pk: int):
    """Swap a single row into edit mode."""
    if not user_is_moderator(request.user):
        return HttpResponseForbidden()
    org = get_user_org(request.user)
    tab = get_object_or_404(Tab, pk=pk, org=org)
    html = render_to_string("journal/partials/tab_edit_row.html", {"tab": tab}, request)
    return HttpResponse(html)

@login_required
def tab_edit(request, pk):
    """Classic edit page (no inline row edit)."""
    if not user_is_moderator(request.user):
        return HttpResponseForbidden()
    org = get_user_org(request.user)
    tab = get_object_or_404(Tab, pk=pk, org=org)

    if request.method == "POST":
        form = TabRenameForm(request.POST, instance=tab)
        if form.is_valid():
            form.save()
            return redirect("journal:tabs")
    else:
        form = TabRenameForm(instance=tab)

    return render(request, "journal/tab_edit.html", {"form": form, "tab": tab})

@login_required
@require_POST
def tab_update(request, pk):
    if not user_is_moderator(request.user):
        return HttpResponse(status=403)
    org = get_user_org(request.user)
    t = get_object_or_404(Tab, pk=pk, org=org)
    form = TabRenameForm(request.POST, instance=t)
    if form.is_valid():
        obj = form.save(commit=False)
        # regenerate slug from new name (keeps unique per org)
        obj.slug = ""  # trigger auto-slug in Tab.save()
        obj.save()
        # return refreshed table
        rows = Tab.objects.filter(org=org).order_by("-enabled","name")
        html = render_to_string("journal/partials/tabs_table.html", {"tabs": rows}, request)
        return HttpResponse(html)
    # invalid -> return edit row with errors
    html = render_to_string("journal/partials/tab_edit_row.html", {"t": t, "form": form}, request)
    return HttpResponse(html)

@login_required
def tutorial(request):
    profile = _get_profile(request.user)
    if not profile.onboarding_enabled:
        messages.info(request, "Tutorial is disabled. Enable it from Profile to run again.")
        return redirect("journal:index")

    step = max(1, min(5, profile.onboarding_step or 1))
    # initial page loads the step container and lazy-loads the partial
    return render(request, "journal/tutorial.html", {"step": step})

@login_required
def tutorial_step(request, step: int):
    profile = _get_profile(request.user)
    if not profile.onboarding_enabled:
        return HttpResponse(status=403)

    # Clamp step
    step = max(1, min(5, step))
    org = None
    m = request.user.memberships.select_related("org").first()
    if m: org = m.org

    # Handle POST actions per step
    if request.method == "POST":
        action = request.POST.get("action")

        # STEP 1: set profile full name
        if step == 1:
            if action == "skip":
                profile.onboarding_step = 2; profile.save(update_fields=["onboarding_step"])
            else:
                form = ProfileMiniForm(request.POST, instance=profile)
                if form.is_valid():
                    form.save()
                    profile.onboarding_step = 2; profile.save(update_fields=["onboarding_step"])
                else:
                    html = render_to_string("journal/partials/tutorial/_step_1_profile.html", {"form": form}, request)
                    return HttpResponse(html)

        # STEP 2: create tab
        elif step == 2:
            if action == "skip":
                profile.onboarding_step = 3; profile.save(update_fields=["onboarding_step"])
            else:
                if not org:
                    messages.error(request, "No organization found. Ask a moderator to add you.")
                    profile.onboarding_step = 3; profile.save(update_fields=["onboarding_step"])
                else:
                    form = TabForm(request.POST)
                    if form.is_valid():
                        t = form.save(commit=False)
                        t.org = org
                        t.save()
                        profile.onboarding_step = 3; profile.save(update_fields=["onboarding_step"])
                    else:
                        html = render_to_string("journal/partials/tutorial/_step_2_tab.html", {"form": form}, request)
                        return HttpResponse(html)

        # STEP 3: first entry
        elif step == 3:
            if action == "skip":
                profile.onboarding_step = 4; profile.save(update_fields=["onboarding_step"])
            else:
                form = EntryForm(request.POST, request.FILES)
                if form.is_valid():
                    entry = form.save(commit=False)
                    entry.author = request.user
                    if org: entry.org = org
                    entry.status = Entry.Status.DRAFT
                    entry.save()
                    form.save_m2m()
                    for f in request.FILES.getlist("images"):
                        EntryImage.objects.create(entry=entry, image=f)
                    profile.onboarding_step = 4; profile.save(update_fields=["onboarding_step"])
                else:
                    html = render_to_string("journal/partials/tutorial/_step_3_entry.html", {"form": form, "org": org}, request)
                    return HttpResponse(html)

        # STEP 4: invite (optional)
        elif step == 4:
            if action == "skip":
                profile.onboarding_step = 5; profile.save(update_fields=["onboarding_step"])
            else:
                form = InviteForm(request.POST)
                if form.is_valid() and org:
                    inv = Invite.create(
                        org=org,
                        role=form.cleaned_data["role"],
                        created_by=request.user,
                        email=form.cleaned_data.get("email","") if form.cleaned_data["delivery"]=="email" else "",
                        phone=form.cleaned_data.get("phone","") if form.cleaned_data["delivery"]=="sms" else "",
                        delivery=form.cleaned_data["delivery"],
                    )
                    from django.urls import reverse
                    accept_url = f"{'https' if request.is_secure() else 'http'}://{request.get_host()}" + reverse("journal:invite_accept", args=[inv.token])
                    # Show link inline for dev
                    messages.info(request, f"Invite link (dev): {accept_url}")
                    profile.onboarding_step = 5; profile.save(update_fields=["onboarding_step"])
                else:
                    html = render_to_string("journal/partials/tutorial/_step_4_invite.html", {"form": form}, request)
                    return HttpResponse(html)

        # STEP 5: finish
        elif step == 5:
            if action == "skip":
                profile.onboarding_enabled = False
                profile.onboarding_step = 5
                profile.save(update_fields=["onboarding_enabled","onboarding_step"])
            else:
                profile.onboarding_enabled = False
                profile.save(update_fields=["onboarding_enabled"])

        # After any POST: load next/current step partial
        next_step = max(1, min(5, profile.onboarding_step))
        html = render_to_string(f"journal/partials/tutorial/_step_{next_step}.html", _step_ctx(request.user, next_step, org), request)
        return HttpResponse(html)

    # GET: return current step partial
    html = render_to_string(f"journal/partials/tutorial/_step_{step}.html", _step_ctx(request.user, step, org), request)
    return HttpResponse(html)

def _step_ctx(user, step, org):
    ctx = {"step": step}
    if step == 1:
        ctx["form"] = ProfileMiniForm(instance=_get_profile(user))
    elif step == 2:
        ctx["form"] = TabForm()
    elif step == 3:
        ctx["form"] = EntryForm()
        ctx["org"] = org
    elif step == 4:
        ctx["form"] = InviteForm()
    return ctx

@login_required
def tutorial_enable(request):
    p = _get_profile(request.user)
    p.onboarding_enabled = True
    p.onboarding_step = 1
    p.save(update_fields=["onboarding_enabled","onboarding_step"])
    messages.success(request, "Tutorial enabled.")
    return redirect("journal:tutorial")

@login_required
def tutorial_disable(request):
    p = _get_profile(request.user)
    p.onboarding_enabled = False
    p.save(update_fields=["onboarding_enabled"])
    messages.info(request, "Tutorial disabled.")
    return redirect("journal:index")

@require_http_methods(["GET", "POST"])
def logout_then_login(request):
    logout(request)
    # respect ?next=... if present, else go to login
    next_url = request.GET.get("next") or request.POST.get("next") or "/accounts/login/"
    return redirect(next_url)

@login_required
def subusers_list(request):
    org = get_user_org(request.user)
    # Org managers see all subauthors; otherwise show only the ones you manage
    qs = (Membership.objects
          .filter(org=org, role=Membership.Role.SUBAUTHOR)
          .select_related("user", "org"))
    if not user_is_moderator(request.user):
        qs = qs.filter(managed_by=request.user)

    ctx = {"org": org, "members": qs, "role_choices": Membership.Role.choices}
    if is_htmx(request):
        html = render_to_string("journal/partials/members_table.html", ctx, request=request)
        return HttpResponse(html)
    return render(request, "journal/members.html", ctx)  # reuse the table template section

@login_required
@transaction.atomic
def subuser_create(request):
    if request.method != "POST":
        return HttpResponse(status=405)
    org = get_user_org(request.user)
    form = SubuserCreateForm(request.POST)
    if not (user_is_moderator(request.user) or True):  # allow any user to create their own subusers
        return HttpResponseForbidden()
    if not form.is_valid():
        html = render_to_string("journal/partials/form_errors.html", {"form": form}, request=request)
        return HttpResponse(html, status=400)

    full_name = form.cleaned_data.get("full_name") or ""
    email = form.cleaned_data.get("email") or ""
    role = Membership.Role.SUBAUTHOR

    # Create (or reuse) a user record
    user, created = U.objects.get_or_create(email=email or None, defaults={
        "username": (email or f"sub_{request.user.id}_{U.objects.count()+1}")[:150],
        "is_active": True,
    })
    # optional: split full_name into first/last
    if full_name and created:
        parts = full_name.split()
        user.first_name = parts[0]
        user.last_name = " ".join(parts[1:]) if len(parts) > 1 else ""
        user.save()

    mem, _ = Membership.objects.get_or_create(
        org=org, user=user,
        defaults={"role": role, "managed_by": request.user}
    )
    if mem.managed_by_id is None:
        mem.managed_by = request.user
        mem.save(update_fields=["managed_by"])

    # return refreshed table for HTMX
    return subusers_list(request)

@login_required
def profile_detail(request, user_id=None):
    subject = request.user if not user_id else get_object_or_404(UserProfile, user__id=user_id).user
    profile = getattr(subject, "profile", None) or UserProfile.objects.get_or_create(user=subject)[0]
    if not can_view_profile(request.user, subject):
        return HttpResponseForbidden()
    return render(request, "journal/profile_detail.html", {"subject": subject, "profile": profile})

@login_required
def profile_edit(request, user_id=None):
    """
    Edit your own profile, or (if you have permission) a subuser's profile.
    - Uses fixed prefixes: social / image / custom
    - Reuses the same template for both cases
    """
    User = get_user_model()
    target_user = request.user if user_id is None else get_object_or_404(User, pk=user_id)

    if user_id is not None and not user_can_manage_user(request.user, target_user):
        return HttpResponseForbidden("You can't edit this user's profile.")

    profile, _ = UserProfile.objects.get_or_create(user=target_user)

    if request.method == "POST":
        form = ProfileForm(request.POST, request.FILES, instance=profile)

        # IMPORTANT: keep these prefixes in sync with the template & HTMX row endpoints
        social_fs = SocialFormSet(request.POST, prefix="social", instance=profile)
        image_fs  = ImageFormSet(request.POST, request.FILES, prefix="image", instance=profile)
        custom_fs = CustomFieldFormSet(request.POST, prefix="custom", instance=profile)

        if form.is_valid() and social_fs.is_valid() and image_fs.is_valid() and custom_fs.is_valid():
            form.save()
            social_fs.save()
            image_fs.save()
            custom_fs.save()
            # where to go after save
            if user_id:
                return redirect("journal:profile_detail_user", user_id=target_user.id)
            return redirect("journal:profile_detail")
    else:
        form = ProfileForm(instance=profile)
        social_fs = SocialFormSet(prefix="social", instance=profile)
        image_fs  = ImageFormSet(prefix="image", instance=profile)
        custom_fs = CustomFieldFormSet(prefix="custom", instance=profile)

    ctx = {
        "form": form,
        "profile": profile,
        "social_fs": social_fs,
        "image_fs": image_fs,
        "custom_fs": custom_fs,
        "target_user": target_user if user_id else None,
    }
    return render(request, "journal/profile_edit.html", ctx)

@login_required
def profile_social_row(request, user_id=None):
    target = request.user
    if user_id is not None:
        U = get_user_model()
        target = get_object_or_404(U, pk=user_id)
        if not user_can_manage_user(request.user, target):
            return HttpResponseForbidden()

    index = request.GET.get("index", "__prefix__")
    form = SocialFormSet.form(prefix=f"social-{index}")  # keep in sync with formset prefix
    return render(request, "journal/partials/profile_social_row.html", {"form": form})

@login_required
def profile_image_row(request, user_id=None):
    target = request.user
    if user_id is not None:
        U = get_user_model()
        target = get_object_or_404(U, pk=user_id)
        if not user_can_manage_user(request.user, target):
            return HttpResponseForbidden()

    index = request.GET.get("index", "__prefix__")
    form = ImageFormSet.form(prefix=f"image-{index}")
    return render(request, "journal/partials/profile_image_row.html", {"form": form})

@login_required
def profile_custom_row(request, user_id=None):
    target = request.user
    if user_id is not None:
        U = get_user_model()
        target = get_object_or_404(U, pk=user_id)
        if not user_can_manage_user(request.user, target):
            return HttpResponseForbidden()

    index = request.GET.get("index", "__prefix__")
    form = CustomFieldFormSet.form(prefix=f"custom-{index}")
    return render(request, "journal/partials/profile_custom_row.html", {"form": form})