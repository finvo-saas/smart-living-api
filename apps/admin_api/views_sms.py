"""Platform admin SMS: packages, owner wallets, send history."""

from __future__ import annotations

from django.db.models import Q
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import Role, User
from admin_api.permissions import IsPlatformAdmin, admin_has_permission
from core.envelope import api_success
from core.exceptions import ForbiddenError, InvalidError, NotFoundError
from core.paging import paginated_response, search_term
from mess.models import OwnerSMSAccount, SMSCreditPackage, SMSMessage
from mess.serializers import SMSMessageSerializer
from mess.services.sms_credits import (
    admin_adjust_credits,
    platform_sms_overview,
    serialize_ledger,
    serialize_owner_wallet_row,
    serialize_package,
    serialize_wallet,
)


class AdminSMSOverviewView(APIView):
    permission_classes = [IsAuthenticated, IsPlatformAdmin]
    admin_permission = 'sms.view'

    def get(self, request):
        return Response(api_success(platform_sms_overview()))


class AdminSMSPackageListCreateView(APIView):
    permission_classes = [IsAuthenticated, IsPlatformAdmin]
    admin_permission = 'sms.view'

    def get(self, request):
        include_inactive = request.query_params.get('all') in ('1', 'true', 'yes')
        qs = SMSCreditPackage.objects.all().order_by(
            'sort_order', 'credits', 'package_key'
        )
        if not include_inactive:
            qs = qs.filter(is_active=True)
        return Response(api_success([serialize_package(p) for p in qs]))

    def post(self, request):
        if not admin_has_permission(
            getattr(request.user, 'admin_role', None), 'sms.manage'
        ):
            raise ForbiddenError('Missing admin permission: sms.manage')
        data = request.data or {}
        package_key = (data.get('packageKey') or data.get('package_key') or '').strip()
        label = (data.get('label') or '').strip()
        credits = data.get('credits')
        price = data.get('priceBdt', data.get('price_bdt', data.get('price')))
        if not package_key or not label:
            raise InvalidError('packageKey and label are required.')
        try:
            credits = int(credits)
            price = float(price)
        except (TypeError, ValueError) as exc:
            raise InvalidError('credits and priceBdt must be numbers.') from exc
        if credits <= 0 or price < 0:
            raise InvalidError('credits must be > 0 and priceBdt >= 0.')
        if SMSCreditPackage.objects.filter(package_key=package_key).exists():
            raise InvalidError('packageKey already exists.')
        pkg = SMSCreditPackage.objects.create(
            package_key=package_key,
            label=label,
            credits=credits,
            price_bdt=price,
            description=(data.get('description') or '').strip(),
            is_active=bool(data.get('isActive', data.get('is_active', True))),
            sort_order=int(data.get('sortOrder', data.get('sort_order', 0)) or 0),
        )
        return Response(
            api_success(serialize_package(pkg)),
            status=status.HTTP_201_CREATED,
        )


class AdminSMSPackageDetailView(APIView):
    permission_classes = [IsAuthenticated, IsPlatformAdmin]
    admin_permission = 'sms.manage'

    def _get(self, pk) -> SMSCreditPackage:
        try:
            return SMSCreditPackage.objects.get(pk=pk)
        except SMSCreditPackage.DoesNotExist as exc:
            raise NotFoundError('SMS package not found.') from exc

    def patch(self, request, pk):
        pkg = self._get(pk)
        data = request.data or {}
        if 'label' in data:
            pkg.label = str(data['label']).strip() or pkg.label
        if 'credits' in data:
            pkg.credits = int(data['credits'])
            if pkg.credits <= 0:
                raise InvalidError('credits must be > 0.')
        if 'priceBdt' in data or 'price_bdt' in data or 'price' in data:
            pkg.price_bdt = data.get('priceBdt', data.get('price_bdt', data.get('price')))
        if 'description' in data:
            pkg.description = str(data['description'] or '').strip()
        if 'isActive' in data or 'is_active' in data:
            pkg.is_active = bool(data.get('isActive', data.get('is_active')))
        if 'sortOrder' in data or 'sort_order' in data:
            pkg.sort_order = int(data.get('sortOrder', data.get('sort_order', 0)) or 0)
        if 'packageKey' in data or 'package_key' in data:
            new_key = str(data.get('packageKey', data.get('package_key'))).strip()
            if (
                new_key
                and new_key != pkg.package_key
                and SMSCreditPackage.objects.filter(package_key=new_key).exists()
            ):
                raise InvalidError('packageKey already exists.')
            if new_key:
                pkg.package_key = new_key
        pkg.save()
        return Response(api_success(serialize_package(pkg)))

    def delete(self, request, pk):
        pkg = self._get(pk)
        # Soft-deactivate rather than hard-delete so purchase history stays meaningful
        pkg.is_active = False
        pkg.save(update_fields=['is_active', 'updated_at'])
        return Response(api_success(serialize_package(pkg)))


class AdminSMSWalletListView(APIView):
    permission_classes = [IsAuthenticated, IsPlatformAdmin]
    admin_permission = 'sms.view'

    def get(self, request):
        qs = OwnerSMSAccount.objects.select_related('owner').order_by('-updated_at')
        term = search_term(request)
        if term:
            qs = qs.filter(
                Q(owner__name__icontains=term) | Q(owner__phone__icontains=term)
            )
        return paginated_response(
            request,
            qs,
            serialize_page=lambda page: [
                serialize_owner_wallet_row(a) for a in page
            ],
        )


class AdminSMSWalletDetailView(APIView):
    permission_classes = [IsAuthenticated, IsPlatformAdmin]
    admin_permission = 'sms.view'

    def get(self, request, owner_id):
        try:
            owner = User.objects.get(pk=owner_id)
        except User.DoesNotExist as exc:
            raise NotFoundError('Owner not found.') from exc
        if owner.role not in (Role.OWNER, Role.ADMIN):
            raise InvalidError('User is not an owner account.')
        account = OwnerSMSAccount.objects.filter(owner=owner).select_related('owner').first()
        if account is None:
            from mess.services.sms_credits import ensure_monthly_free_quota

            account = ensure_monthly_free_quota(owner)
            account = OwnerSMSAccount.objects.select_related('owner').get(pk=account.pk)
        limit = min(int(request.query_params.get('limit') or 100), 300)
        messages = (
            SMSMessage.objects.filter(sent_by=owner)
            .select_related('mess')
            .order_by('-created_at')[:limit]
        )
        return Response(
            api_success(
                {
                    'wallet': serialize_owner_wallet_row(account),
                    'ownerWallet': serialize_wallet(owner),
                    'ledger': serialize_ledger(owner, limit=limit),
                    'messages': SMSMessageSerializer(messages, many=True).data,
                }
            )
        )


class AdminSMSWalletAdjustView(APIView):
    permission_classes = [IsAuthenticated, IsPlatformAdmin]
    admin_permission = 'sms.manage'

    def post(self, request, owner_id):
        try:
            owner = User.objects.get(pk=owner_id)
        except User.DoesNotExist as exc:
            raise NotFoundError('Owner not found.') from exc
        credits = request.data.get('credits')
        note = (request.data.get('note') or '').strip()
        try:
            credits = int(credits)
        except (TypeError, ValueError) as exc:
            raise InvalidError('credits must be an integer.') from exc
        account = admin_adjust_credits(
            owner, credits, note=note, admin_user=request.user
        )
        account = OwnerSMSAccount.objects.select_related('owner').get(pk=account.pk)
        return Response(
            api_success(
                {
                    'wallet': serialize_owner_wallet_row(account),
                    'ledger': serialize_ledger(owner, limit=20),
                }
            )
        )


class AdminSMSMessageListView(APIView):
    permission_classes = [IsAuthenticated, IsPlatformAdmin]
    admin_permission = 'sms.view'

    def get(self, request):
        qs = SMSMessage.objects.select_related('mess', 'sent_by').order_by(
            '-created_at'
        )
        term = search_term(request)
        if term:
            qs = qs.filter(
                Q(content__icontains=term)
                | Q(mess__name__icontains=term)
                | Q(sent_by__phone__icontains=term)
                | Q(sent_by__name__icontains=term)
            )
        owner_id = request.query_params.get('ownerId') or request.query_params.get(
            'owner_id'
        )
        if owner_id:
            qs = qs.filter(sent_by_id=owner_id)
        mess_id = request.query_params.get('messId') or request.query_params.get(
            'mess_id'
        )
        if mess_id:
            qs = qs.filter(mess_id=mess_id)
        status_filter = request.query_params.get('status')
        if status_filter:
            qs = qs.filter(status=status_filter)
        start = request.query_params.get('startDate')
        end = request.query_params.get('endDate')
        if start:
            qs = qs.filter(created_at__date__gte=start)
        if end:
            qs = qs.filter(created_at__date__lte=end)

        return paginated_response(
            request,
            qs,
            serialize_page=lambda page: SMSMessageSerializer(page, many=True).data,
        )
