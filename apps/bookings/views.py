from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from bookings.models import PropertyBooking
from bookings.serializers import (
    PropertyBookingCreateSerializer,
    PropertyBookingSerializer,
    PropertyBookingStatusSerializer,
)
from bookings.services.workflow import create_booking, patch_status
from admin_api.permissions import IsPlatformAdmin
from core.envelope import api_success
from core.exceptions import ForbiddenError, NotFoundError
from django.db.models import Q


def _serialize(booking, request=None):
    return PropertyBookingSerializer(booking, context={'request': request}).data


def _serialize_many(qs, request=None):
    return PropertyBookingSerializer(qs, many=True, context={'request': request}).data


class PropertyBookingListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = PropertyBookingCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        booking = create_booking(request.user, serializer.validated_data)
        return Response(
            api_success(_serialize(booking, request)),
            status=status.HTTP_201_CREATED,
        )


class MyPropertyBookingsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        qs = (
            PropertyBooking.objects.filter(renter=request.user, is_deleted=False)
            .select_related('renter', 'owner')
            .order_by('-created_at')
        )
        return Response(api_success(_serialize_many(qs, request)))


class OwnerPropertyBookingsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        qs = (
            PropertyBooking.objects.filter(owner=request.user, is_deleted=False)
            .select_related('renter', 'owner')
            .order_by('-created_at')
        )
        return Response(api_success(_serialize_many(qs, request)))


class PropertyBookingDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        try:
            booking = PropertyBooking.objects.select_related('renter', 'owner').get(
                pk=pk,
                is_deleted=False,
            )
        except PropertyBooking.DoesNotExist as exc:
            raise NotFoundError('Booking not found.') from exc

        user = request.user
        if booking.renter_id != user.id and booking.owner_id != user.id and user.role != 'admin':
            raise ForbiddenError('You cannot view this booking.')
        return Response(api_success(_serialize(booking, request)))


class PropertyBookingStatusView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request, pk):
        serializer = PropertyBookingStatusSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        booking = patch_status(
            request.user,
            pk,
            data['status'],
            data.get('reason'),
        )
        return Response(api_success(_serialize(booking, request)))


class AdminPropertyBookingsView(APIView):
    permission_classes = [IsAuthenticated, IsPlatformAdmin]

    def get(self, request):
        from core.paging import paginated_response, query_flag, search_term

        property_qs = (
            PropertyBooking.objects.filter(is_deleted=False)
            .select_related('renter', 'owner')
            .order_by('-created_at')
        )
        term = search_term(request)
        if term:
            property_qs = property_qs.filter(
                Q(property_name__icontains=term)
                | Q(renter_name__icontains=term)
                | Q(owner_name__icontains=term)
                | Q(renter_phone__icontains=term),
            )
        status_filter = query_flag(request, 'status')
        if status_filter:
            property_qs = property_qs.filter(status=status_filter)
        type_filter = query_flag(request, 'type') or query_flag(request, 'propertyType')
        if type_filter and type_filter != 'hotel':
            property_qs = property_qs.filter(property_type=type_filter)

        property_rows = []
        if type_filter != 'hotel':
            property_rows = _serialize_many(property_qs, request)

        hotel_rows = []
        if type_filter in ('', 'hotel'):
            try:
                from hotels.models import HotelBooking
                from hotels.serializers import HotelBookingSerializer

                hotel_qs = (
                    HotelBooking.objects.filter(is_deleted=False)
                    .select_related('hotel', 'hotel__owner', 'user', 'room')
                    .order_by('-created_at')
                )
                if term:
                    hotel_qs = hotel_qs.filter(
                        Q(hotel__name__icontains=term)
                        | Q(guest_name__icontains=term)
                        | Q(guest_phone__icontains=term)
                        | Q(hotel__owner__name__icontains=term),
                    )
                for booking in hotel_qs:
                    hotel = booking.hotel
                    owner = hotel.owner
                    raw = HotelBookingSerializer(
                        booking,
                        context={'request': request},
                    ).data
                    mapped_status = raw.get('status') or booking.status
                    if mapped_status == 'confirmed':
                        mapped_status = 'approved'
                    elif mapped_status == 'checked-in':
                        mapped_status = 'approved'
                    elif mapped_status == 'checked-out':
                        mapped_status = 'completed'
                    if status_filter and mapped_status != status_filter:
                        continue
                    hotel_rows.append(
                        {
                            'id': str(booking.id),
                            'propertyId': str(hotel.id),
                            'propertyName': hotel.name,
                            'propertyType': 'hotel',
                            'propertyAddress': hotel.address or '',
                            'propertyImage': None,
                            'renterId': str(booking.user_id),
                            'renterName': booking.guest_name
                            or (booking.user.name if booking.user_id else ''),
                            'renterPhone': booking.guest_phone
                            or (booking.user.phone if booking.user_id else ''),
                            'renterEmail': booking.guest_email or '',
                            'ownerId': str(owner.id) if owner else '',
                            'ownerName': (owner.name or owner.phone) if owner else '',
                            'ownerPhone': owner.phone if owner else '',
                            'status': mapped_status,
                            'bookingMode': 'request',
                            'moveInDate': (
                                booking.check_in.isoformat() if booking.check_in else None
                            ),
                            'moveOutDate': (
                                booking.check_out.isoformat()
                                if booking.check_out
                                else None
                            ),
                            'duration': None,
                            'rent': float(booking.total_amount or 0),
                            'deposit': float(booking.advance_amount or 0),
                            'totalAmount': float(booking.total_amount or 0),
                            'message': '',
                            'specialRequests': booking.special_requests or '',
                            'createdAt': raw.get('createdAt'),
                            'updatedAt': raw.get('updatedAt'),
                        },
                    )
            except Exception:  # noqa: BLE001
                hotel_rows = []

        merged = list(property_rows) + hotel_rows
        merged.sort(key=lambda row: row.get('createdAt') or '', reverse=True)
        return paginated_response(
            request,
            merged,
            serialize_page=lambda rows: rows,
        )
