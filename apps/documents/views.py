from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import Role
from core.envelope import api_success
from core.exceptions import ForbiddenError, NotFoundError
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
        qs = _agreement_qs().filter(user=request.user).order_by('-created_at')
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
