from django.urls import path
from .views.clubs_view import ClubsView, ClubView
from .views.members_view import MembersView, MemberView

urlpatterns = [
    path('clubs/', ClubsView.as_view()),
    path('club/<uuid:uuid>/', ClubView.as_view()),

    path('members/<uuid:club_uuid>/', MembersView.as_view()),
    path('member/<uuid:uuid>/', MemberView.as_view())
]