
from django.urls import path
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from . import views
from . import views_profile

def ok(_): return HttpResponse("OK", content_type="text/plain")

app_name = "journal"

urlpatterns = [
    path("", views.index, name="index"),
    path("entry/new/", views.entry_create, name="entry_create"),

    path("drafts/", views.drafts, name="drafts"),
    path("drafts/<int:pk>/publish/", views.entry_publish, name="entry_publish"),
    path("drafts/<int:pk>/delete/", views.entry_delete, name="entry_delete"),

    path("entry/<int:pk>/", views.entry_detail, name="entry_detail"),
    path("entry/<int:pk>/edit/", views.entry_edit, name="entry_edit"),

    # moderator / management
    path("review/", views.review_queue, name="review_queue"),
    path("review/<int:pk>/approve/", views.entry_approve, name="entry_approve"),
    path("review/<int:pk>/reject/", views.entry_reject, name="entry_reject"),
    
    path("tabs/", views.tabs, name="tabs"),
    path("tabs/create/", views.tab_create, name="tab_create"),
    path("tabs/<int:pk>/toggle/", views.tab_toggle, name="tab_toggle"),
    path("tabs/<int:pk>/edit/", views.tab_edit_form, name="tab_edit_form"),   # GET -> inline form row
    path("tabs/<int:pk>/update/", views.tab_update, name="tab_update"),       # POST -> save rename

    path("members/", views.members, name="members"),
    path("members/add/", views.member_add, name="member_add"),
    path("members/invite/", views.member_invite, name="member_invite"),
    path("invite/accept/<str:token>/", views.invite_accept, name="invite_accept"),
    path("members/<int:pk>/set-role/", views.member_set_role, name="member_set_role"),

    path("tutorial/", views.tutorial, name="tutorial"),
    path("tutorial/step/<int:step>/", views.tutorial_step, name="tutorial_step"),
    path("tutorial/enable/", views.tutorial_enable, name="tutorial_enable"),
    path("tutorial/disable/", views.tutorial_disable, name="tutorial_disable"),

    path("plans/", views.plans, name="plans"),

    # profile
    path("profile/", views_profile.profile_detail, name="profile"), 
    path("profile/", views_profile.profile_detail, name="profile_detail"),
    path("profile/edit/", views_profile.profile_edit, name="profile_edit"),
    path("u/<int:user_id>/profile/edit/", views.profile_edit, name="profile_edit_user"),
    # optional: allow managers to view/edit by id
    path("profile/<int:user_id>/", views_profile.profile_detail, name="profile_detail_by_id"),
    path("profile/<int:user_id>/edit/", views_profile.profile_edit, name="profile_edit_by_id"),
    path("profile/rows/social/", views_profile.social_form_row, name="profile_social_row"),
    path("profile/<int:user_id>/rows/social/", views_profile.social_form_row, name="profile_social_row_user"),
    path("profile/rows/image/",  views_profile.image_form_row,  name="profile_image_row"),
    path("profile/<int:user_id>/rows/image/", views_profile.image_form_row, name="profile_image_row_user"),
    path("profile/rows/custom/", views.profile_custom_row, name="profile_custom_row"),
    path("u/<int:user_id>/profile/row/custom/", views.profile_custom_row, name="profile_custom_row_user"),

    path("subusers/", views.subusers_list, name="subusers"),
    path("subusers/add/", views.subuser_create, name="subuser_create"),
]

urlpatterns += [ path("ok/", login_required(ok), name="ok") ]
