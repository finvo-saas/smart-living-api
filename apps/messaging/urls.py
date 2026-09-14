from django.urls import path

from core.views_sse import ChatMessagesSSEView
from messaging.views import (
    ChatContactListView,
    ChatDetailView,
    ChatListCreateView,
    ChatMessageListCreateView,
    ChatUnreadCountView,
    ChatUserView,
    NotificationListView,
    NotificationMarkAllReadView,
    NotificationReadView,
    PushConfigView,
    PushSubscribeView,
    PushTestView,
)

urlpatterns = [
    path('chats/', ChatListCreateView.as_view(), name='chat-list'),
    path('chats/unread-count/', ChatUnreadCountView.as_view(), name='chat-unread-count'),
    path('chats/contacts/', ChatContactListView.as_view(), name='chat-contacts'),
    path('chats/users/<uuid:user_id>/', ChatUserView.as_view(), name='chat-user'),
    path('chats/<uuid:pk>/', ChatDetailView.as_view(), name='chat-detail'),
    path(
        'chats/<uuid:pk>/messages/',
        ChatMessageListCreateView.as_view(),
        name='chat-messages',
    ),
    path(
        'chats/<uuid:pk>/messages/stream/',
        ChatMessagesSSEView.as_view(),
        name='chat-messages-sse',
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
    path('push/config/', PushConfigView.as_view(), name='push-config'),
    path('push/subscribe/', PushSubscribeView.as_view(), name='push-subscribe'),
    path('push/test/', PushTestView.as_view(), name='push-test'),
]
