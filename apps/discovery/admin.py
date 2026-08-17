from django.contrib import admin

from discovery.models import Favorite, SavedSearch, SearchHistory


@admin.register(Favorite)
class FavoriteAdmin(admin.ModelAdmin):
    list_display = ('user', 'property', 'created_at')
    search_fields = ('user__phone', 'property__name')


@admin.register(SavedSearch)
class SavedSearchAdmin(admin.ModelAdmin):
    list_display = ('name', 'user', 'is_active', 'match_count', 'updated_at')
    list_filter = ('is_active',)


@admin.register(SearchHistory)
class SearchHistoryAdmin(admin.ModelAdmin):
    list_display = ('user', 'result_count', 'created_at')
    search_fields = ('user__phone',)
