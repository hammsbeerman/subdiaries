
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
from .models import Entry, EntryImage, Tab, Membership, Organization, Invite, UserProfile
from .forms import EntryForm, MemberAddForm, InviteForm, AcceptInviteForm, TabForm, TabRenameForm, ProfileMiniForm
from django import forms
from django.template.loader import render_to_string
from .utils import send_invite_email, send_invite_sms, get_user_org

@login_required
@ensure_csrf_cookie
@never_cache
def ok(request):
    return HttpResponse("OK", content_type="text/plain")

def is_htmx(request):
    return request.headers.get("HX-Request") == "true"

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
        return redirect("journal:tutorial")

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

def user_is_moderator(user):
    m = Membership.objects.filter(user=user).first()
    return bool(m and str(m.role).lower() in {"moderator","admin","owner"})

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
    org = get_user_org(request.user)
    rows = Tab.objects.filter(org=org).order_by("-enabled","name")
    form = TabForm()
    if is_htmx(request):
        html = render_to_string("journal/partials/tabs_table.html", {"tabs": rows}, request)
        return HttpResponse(html)
    return render(request, "journal/tabs.html", {"tabs": rows, "form": form})


@login_required
@require_POST
def tab_create(request):
    if not user_is_moderator(request.user):
        return HttpResponse(status=403)
    org = get_user_org(request.user)

    name = " ".join((request.POST.get("name") or "").split()).strip()
    enabled = bool(request.POST.get("enabled"))

    if not name:
        rows = Tab.objects.filter(org=org).order_by("-enabled","name")
        html = render_to_string("journal/partials/tabs_table.html", {"tabs": rows}, request)
        # quick inline error banner (htmx will still replace the table)
        html += '<div class="alert alert-danger mt-2" hx-swap-oob="true" id="tabs-error">Name is required.</div>'
        return HttpResponse(html)

    # Create the tab; model auto-generates slug
    Tab.objects.create(org=org, name=name, enabled=enabled, created_by=request.user)

    rows = Tab.objects.filter(org=org).order_by("-enabled","name")
    html = render_to_string("journal/partials/tabs_table.html", {"tabs": rows}, request)
    # also clear any prior error + optionally clear the form via OOB
    html += '<div id="tabs-error" hx-swap-oob="true"></div>'
    return HttpResponse(html)

@login_required
@require_POST
def tab_toggle(request, pk):
    if not user_is_moderator(request.user):
        return HttpResponseForbidden()
    org = get_user_org(request.user)
    t = get_object_or_404(Tab, pk=pk, org=org)
    t.enabled = not t.enabled; t.save(update_fields=["enabled"])
    rows = Tab.objects.filter(org=org).order_by("-enabled","name")
    html = render_to_string("journal/partials/tabs_table.html", {"tabs": rows}, request)
    return HttpResponse(html)

# --- Members admin ---
ROLE_CHOICES = [("moderator","moderator"), ("author","author"), ("subauthor","subauthor")]

@login_required
def members(request):
    if not user_is_moderator(request.user):
        return HttpResponse(status=403)
    org = get_user_org(request.user)
    rows = Membership.objects.filter(org=org).select_related("user")
    form = MemberAddForm()
    if is_htmx(request):
        # return only the table for HTMX refresh
        html = render_to_string("journal/partials/members_table.html",
                                {"memberships": rows, "ROLE_CHOICES": ROLE_CHOICES}, request)
        return HttpResponse(html)
    return render(request, "journal/members.html",
                  {"memberships": rows, "ROLE_CHOICES": ROLE_CHOICES, "form": form})

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