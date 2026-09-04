from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import Role
from core.envelope import api_success
from core.exceptions import ForbiddenError, InvalidError, NotFoundError
from documents.constants import CHECKLIST_CATEGORIES
from documents.models import AgreementRenewal, Checklist, RentalAgreement
from documents.serializers import (
    AgreementRenewalSerializer,
    AgreementRenewalWriteSerializer,
    ChecklistSerializer,
    ChecklistWriteSerializer,
    RentalAgreementSerializer,
    RentalAgreementWriteSerializer,
)
from portfolio.models import Building, Flat, Tenancy, TenancyStatus
from portfolio.serializers import BuildingSerializer, FlatSerializer


def _agreement_qs():
    return RentalAgreement.objects.filter(is_deleted=False).select_related('user')


def _get_agreement(pk):
    try:
        return _agreement_qs().get(pk=pk)
    except RentalAgreement.DoesNotExist as exc:
        raise NotFoundError('Agreement not found.') from exc


def _checklist_qs():
    return Checklist.objects.filter(is_deleted=False).select_related('user')


def _get_checklist(pk):
    try:
        return _checklist_qs().get(pk=pk)
    except Checklist.DoesNotExist as exc:
        raise NotFoundError('Checklist not found.') from exc


class AgreementListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        from django.db.models import Q

        if request.user.role == Role.ADMIN:
            qs = _agreement_qs()
        elif request.user.role == Role.OWNER:
            from listings.models import Property

            owned = Property.objects.filter(owner=request.user).values_list(
                'id',
                flat=True,
            )
            qs = _agreement_qs().filter(
                Q(user=request.user) | Q(property_id__in=owned),
            )
        else:
            qs = _agreement_qs().filter(user=request.user)
        qs = qs.order_by('-created_at')
        return Response(api_success(RentalAgreementSerializer(qs, many=True).data))

    def post(self, request):
        ser = RentalAgreementWriteSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        agreement = ser.create_agreement(request.user)
        return Response(
            api_success(RentalAgreementSerializer(agreement).data),
            status=status.HTTP_201_CREATED,
        )


class AgreementActiveView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        agreement = (
            _agreement_qs()
            .filter(user=request.user, status='active')
            .order_by('-created_at')
            .first()
        )
        data = RentalAgreementSerializer(agreement).data if agreement else None
        return Response(api_success(data))


class AgreementDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request, pk):
        agreement = _get_agreement(pk)
        if agreement.user_id != request.user.id and request.user.role != Role.ADMIN:
            raise ForbiddenError('You cannot update this agreement.')

        ser = RentalAgreementWriteSerializer(data=request.data, partial=True)
        ser.is_valid(raise_exception=True)
        for key, value in ser.validated_data.items():
            setattr(agreement, key, value)
        agreement.save()
        return Response(api_success(RentalAgreementSerializer(agreement).data))


class AgreementRenewalCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        agreement = _get_agreement(pk)
        if agreement.user_id != request.user.id and request.user.role not in (
            Role.OWNER,
            Role.ADMIN,
        ):
            raise ForbiddenError('You cannot renew this agreement.')

        ser = AgreementRenewalWriteSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        data = ser.validated_data.copy()
        data['renewed_by'] = data.get('renewed_by') or str(request.user.id)
        renewal = AgreementRenewal.objects.create(agreement=agreement, **data)

        agreement.start_date = renewal.new_start_date
        agreement.end_date = renewal.new_end_date
        if renewal.new_monthly_rent is not None:
            agreement.monthly_rent = renewal.new_monthly_rent
        agreement.expiry_date = renewal.new_end_date
        agreement.status = 'renewed'
        agreement.save()

        return Response(
            api_success(AgreementRenewalSerializer(renewal).data),
            status=status.HTTP_201_CREATED,
        )


class PRCATemplateListView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        from documents.services.prca_templates import get_template_list
        return Response(api_success(get_template_list()))


class PRCAGenerateTermsView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        from datetime import date as date_type

        from documents.services.prca_templates import generate_terms

        data = request.data
        template_key = data.get('templateKey', 'residential_monthly')
        try:
            start = date_type.fromisoformat(str(data.get('startDate', '')))
            end = date_type.fromisoformat(str(data.get('endDate', '')))
        except (ValueError, TypeError):
            raise InvalidError('startDate and endDate are required (YYYY-MM-DD).')

        notice_days = data.get('noticeDays')
        if notice_days is not None and notice_days != '':
            try:
                notice_days = int(notice_days)
            except (TypeError, ValueError):
                notice_days = None
        else:
            notice_days = None

        special_conditions = data.get('specialConditions')
        if special_conditions is not None and not isinstance(special_conditions, list):
            special_conditions = [str(special_conditions)]

        terms = generate_terms(
            template_key,
            monthly_rent=float(data.get('monthlyRent', 0)),
            deposit=float(data.get('securityDeposit', 0)),
            start_date=start,
            end_date=end,
            notice_days=notice_days,
            special_conditions=special_conditions,
            landlord_name=data.get('landlordName', ''),
            tenant_name=data.get('tenantName', request.user.name or ''),
            property_address=data.get('propertyAddress', ''),
        )
        return Response(api_success(terms))


class AgreementFormDataView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        if user.role == Role.OWNER:
            buildings = Building.objects.filter(owner=user).order_by('-created_at')
            flats = Flat.objects.filter(building__owner=user).select_related('building')
        else:
            tenancy_flat_ids = Tenancy.objects.filter(
                tenant=user,
                status=TenancyStatus.ACTIVE,
            ).values_list('flat_id', flat=True)
            flats = Flat.objects.filter(pk__in=tenancy_flat_ids).select_related('building')
            building_ids = flats.values_list('building_id', flat=True).distinct()
            buildings = Building.objects.filter(pk__in=building_ids)

        return Response(api_success({
            'buildings': BuildingSerializer(buildings, many=True).data,
            'flats': FlatSerializer(flats, many=True).data,
        }))


class ChecklistListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        qs = _checklist_qs().filter(user=request.user).order_by('-created_at')
        return Response(api_success(ChecklistSerializer(qs, many=True).data))

    def post(self, request):
        ser = ChecklistWriteSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        checklist = ser.create_checklist(request.user)
        return Response(
            api_success(ChecklistSerializer(checklist).data),
            status=status.HTTP_201_CREATED,
        )


class ChecklistDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request, pk):
        checklist = _get_checklist(pk)
        if checklist.user_id != request.user.id and request.user.role != Role.ADMIN:
            raise ForbiddenError('You cannot update this checklist.')

        ser = ChecklistWriteSerializer(data=request.data, partial=True)
        ser.is_valid(raise_exception=True)
        for key, value in ser.validated_data.items():
            setattr(checklist, key, value)
        checklist.save()
        return Response(api_success(ChecklistSerializer(checklist).data))


class ChecklistCategoriesView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        return Response(api_success(CHECKLIST_CATEGORIES))


class PRCATemplateListView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request):
        from documents.services.prca_templates import get_template_list

        return Response(api_success(get_template_list()))


class PRCAGenerateTermsView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        from datetime import date as date_type

        from documents.services.prca_templates import generate_terms

        data = request.data
        template_key = data.get('templateKey', 'residential_monthly')
        try:
            start = date_type.fromisoformat(str(data.get('startDate', '')))
            end = date_type.fromisoformat(str(data.get('endDate', '')))
        except (ValueError, TypeError) as exc:
            raise InvalidError('startDate and endDate are required (YYYY-MM-DD).') from exc

        notice_days = data.get('noticeDays')
        if notice_days is not None:
            try:
                notice_days = int(notice_days)
            except (TypeError, ValueError) as exc:
                raise InvalidError('noticeDays must be a number.') from exc

        terms = generate_terms(
            template_key,
            monthly_rent=float(data.get('monthlyRent', 0) or 0),
            deposit=float(data.get('securityDeposit', 0) or 0),
            start_date=start,
            end_date=end,
            notice_days=notice_days,
            special_conditions=data.get('specialConditions'),
            landlord_name=data.get('landlordName', ''),
            tenant_name=data.get('tenantName', request.user.name or ''),
            property_address=data.get('propertyAddress', ''),
        )
        return Response(api_success(terms))


class AgreementSignView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        from django.utils import timezone

        agreement = _get_agreement(pk)
        role = (request.data.get('role') or 'tenant').lower()
        signature = (request.data.get('signature') or '').strip()
        signed_name = (request.data.get('signedName') or request.user.name or '').strip()
        if not signature or len(signature) < 20:
            raise InvalidError('A drawn signature is required.')

        if role == 'owner':
            if request.user.role not in (Role.OWNER, Role.ADMIN):
                raise ForbiddenError('Only owners can apply the landlord signature.')
            agreement.owner_signature = signature
            agreement.owner_signed_at = timezone.now()
            agreement.owner_signed_name = signed_name or 'Owner'
            agreement.save(
                update_fields=[
                    'owner_signature',
                    'owner_signed_at',
                    'owner_signed_name',
                    'updated_at',
                ],
            )
        else:
            if agreement.user_id != request.user.id and request.user.role != Role.ADMIN:
                raise ForbiddenError('You can only sign your own agreement as tenant.')
            agreement.tenant_signature = signature
            agreement.tenant_signed_at = timezone.now()
            agreement.tenant_signed_name = signed_name or request.user.name or 'Tenant'
            agreement.save(
                update_fields=[
                    'tenant_signature',
                    'tenant_signed_at',
                    'tenant_signed_name',
                    'updated_at',
                ],
            )
        return Response(api_success(RentalAgreementSerializer(agreement).data))
