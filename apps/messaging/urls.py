from django.urls import path

from messaging.views import (
    ChatDetailView,
    ChatListCreateView,
    ChatMessageListCreateView,
    ChatUnreadCountView,
    ChatUserView,
    NotificationListView,
    NotificationMarkAllReadView,
    NotificationReadView,
)

urlpatterns = [
    path('chats/', ChatListCreateView.as_view(), name='chat-list'),
    path('chats/unread-count/', ChatUnreadCountView.as_view(), name='chat-unread-count'),
    path('chats/users/<uuid:user_id>/', ChatUserView.as_view(), name='chat-user'),
    path('chats/<uuid:pk>/', ChatDetailView.as_view(), name='chat-detail'),
    path(
        'chats/<uuid:pk>/messages/',
        ChatMessageListCreateView.as_view(),
        name='chat-messages',
    ),
    path('notifications/', NotificationListView.as_view(), name='notification-list'),
    path(
        'notifications/mark-all-read/',
        NotificationMarkAllReadView.as_view(),
        name='notification-mark-all-read',
    ),
    path(
        'notifications/<uuid:pk>/read/',
        NotificationReadView.as_view(),
        name='notification-read',
    ),
]
