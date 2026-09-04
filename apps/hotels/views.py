from datetime import datetime

from django.db import IntegrityError
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from core.envelope import api_success
from core.exceptions import ConflictError, ForbiddenError, InvalidError, NotFoundError
from hotels.models import (
    Hotel,
    HotelBooking,
    HotelBookingStatus,
    HotelReview,
    PaymentStatus,
    Room,
)
from hotels.serializers import (
    HotelBookingCancelSerializer,
    HotelBookingCreateSerializer,
    HotelBookingSerializer,
    HotelPricingUpdateSerializer,
    HotelRegistrationSerializer,
    HotelReviewCreateSerializer,
    HotelReviewSerializer,
    HotelSerializer,
    RoomSerializer,
    RoomWriteSerializer,
)
from hotels.services.cancellation import calculate_cancellation_refund
from hotels.services.pricing import calculate_booking_fees, room_pricing_for_range


def _hotel_qs():
    return Hotel.objects.filter(is_deleted=False).select_related('owner')


def _serialize_hotel(hotel, request=None):
    return HotelSerializer(hotel, context={'request': request}).data


def _serialize_hotels(qs, request=None):
    return HotelSerializer(qs, many=True, context={'request': request}).data


def _serialize_booking(booking, request=None):
    return HotelBookingSerializer(booking, context={'request': request}).data


def _serialize_bookings(qs, request=None):
    return HotelBookingSerializer(qs, many=True, context={'request': request}).data


def _get_hotel(pk):
    try:
        return _hotel_qs().get(pk=pk)
    except Hotel.DoesNotExist as exc:
        raise NotFoundError('Hotel not found.') from exc


def _assert_hotel_owner(hotel, user):
    if hotel.owner_id != user.id and user.role != 'admin':
        raise ForbiddenError('Only the hotel owner can perform this action.')


def _room_date_conflict(room_id, check_in, check_out, exclude_id=None):
    qs = HotelBooking.objects.filter(
        room_id=room_id,
        is_deleted=False,
        status__in=[
            HotelBookingStatus.CONFIRMED,
            HotelBookingStatus.CHECKED_IN,
            HotelBookingStatus.PENDING,
        ],
    ).filter(check_in__lt=check_out, check_out__gt=check_in)
    if exclude_id:
        qs = qs.exclude(pk=exclude_id)
    return qs.exists()


class HotelListCreateView(APIView):
    def get_permissions(self):
        if self.request.method == 'GET':
            return [AllowAny()]
        return [IsAuthenticated()]

    def get(self, request):
        qs = _hotel_qs()
        city = request.query_params.get('city')
        area = request.query_params.get('area')
        hotel_type = request.query_params.get('type')
        min_rating = request.query_params.get('minRating')

        if city:
            qs = qs.filter(city__iexact=city.strip())
        if area:
            qs = qs.filter(area__iexact=area.strip())
        if hotel_type and hotel_type != 'all':
            qs = qs.filter(type=hotel_type)
        if min_rating:
            try:
                qs = qs.filter(average_rating__gte=float(min_rating))
            except ValueError:
                pass
        qs = qs.filter(flagged_unavailable_at__isnull=True)

        check_in = request.query_params.get('checkIn')
        check_out = request.query_params.get('checkOut')
        if check_in and check_out:
            from datetime import date as date_cls

            try:
                start = date_cls.fromisoformat(check_in)
                end = date_cls.fromisoformat(check_out)
            except ValueError:
                start = end = None
            if start and end:
                open_ids = []
                for hotel in qs.prefetch_related('rooms'):
                    for room in hotel.rooms.filter(available=True):
                        if not _room_date_conflict(room.id, start, end):
                            open_ids.append(hotel.id)
                            break
                qs = qs.filter(id__in=open_ids)

        return Response(api_success(_serialize_hotels(qs, request)))

    def post(self, request):
        if request.user.role not in ('owner', 'admin'):
            raise ForbiddenError('Only owners can register hotels.')
        serializer = HotelRegistrationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        hotel = serializer.create_hotel(request.user)
        return Response(
            api_success(_serialize_hotel(hotel, request)),
            status=status.HTTP_201_CREATED,
        )


class OwnerHotelsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        qs = _hotel_qs().filter(owner=request.user).order_by('-updated_at')
        return Response(api_success(_serialize_hotels(qs, request)))


class HotelDetailView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, pk):
        hotel = _get_hotel(pk)
        return Response(api_success(_serialize_hotel(hotel, request)))


class HotelPricingUpdateView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request, pk):
        hotel = _get_hotel(pk)
        _assert_hotel_owner(hotel, request.user)
        serializer = HotelPricingUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        if 'pricingRules' in data:
            hotel.pricing_rules = data['pricingRules']
        if 'cancellationPolicy' in data:
            hotel.cancellation_policy = data['cancellationPolicy']
        if 'advancePaymentPercent' in data:
            hotel.advance_payment_percent = data['advancePaymentPercent']
        hotel.save()
        return Response(api_success(_serialize_hotel(hotel, request)))


class HotelRoomListCreateView(APIView):
    def get_permissions(self):
        if self.request.method == 'GET':
            return [AllowAny()]
        return [IsAuthenticated()]

    def get(self, request, pk):
        hotel = _get_hotel(pk)
        rooms = hotel.rooms.all().order_by('floor', 'room_number')
        data = RoomSerializer(rooms, many=True, context={'request': request}).data
        return Response(api_success(data))

    def post(self, request, pk):
        hotel = _get_hotel(pk)
        _assert_hotel_owner(hotel, request.user)
        serializer = RoomWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            room = serializer.save(hotel=hotel)
        except IntegrityError as exc:
            raise InvalidError('A room with this number already exists.') from exc
        hotel.refresh_room_counts()
        return Response(
            api_success(RoomSerializer(room, context={'request': request}).data),
            status=status.HTTP_201_CREATED,
        )


class HotelRoomDetailView(APIView):
    def get_permissions(self):
        if self.request.method == 'GET':
            return [AllowAny()]
        return [IsAuthenticated()]

    def _get_room(self, hotel, room_id):
        try:
            return Room.objects.get(pk=room_id, hotel=hotel)
        except Room.DoesNotExist as exc:
            raise NotFoundError('Room not found.') from exc

    def get(self, request, pk, room_id):
        hotel = _get_hotel(pk)
        room = self._get_room(hotel, room_id)
        return Response(
            api_success(RoomSerializer(room, context={'request': request}).data),
        )

    def patch(self, request, pk, room_id):
        hotel = _get_hotel(pk)
        _assert_hotel_owner(hotel, request.user)
        room = self._get_room(hotel, room_id)
        serializer = RoomWriteSerializer(room, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        try:
            room = serializer.save()
        except IntegrityError as exc:
            raise InvalidError('A room with this number already exists.') from exc
        hotel.refresh_room_counts()
        return Response(
            api_success(RoomSerializer(room, context={'request': request}).data),
        )

    def delete(self, request, pk, room_id):
        hotel = _get_hotel(pk)
        _assert_hotel_owner(hotel, request.user)
        room = self._get_room(hotel, room_id)
        has_active = HotelBooking.objects.filter(
            room=room,
            is_deleted=False,
            status__in=[
                HotelBookingStatus.CONFIRMED,
                HotelBookingStatus.CHECKED_IN,
                HotelBookingStatus.PENDING,
            ],
        ).exists()
        if has_active:
            raise ConflictError('Cannot delete a room with active bookings.')
        room.delete()
        hotel.refresh_room_counts()
        return Response(api_success({'deleted': True}))


class HotelBookingsView(APIView):
    def get_permissions(self):
        if self.request.method == 'GET':
            return [AllowAny()]
        return [IsAuthenticated()]

    def get(self, request, pk):
        hotel = _get_hotel(pk)
        qs = HotelBooking.objects.filter(
            hotel=hotel,
            is_deleted=False,
        ).exclude(status=HotelBookingStatus.CANCELLED).order_by('-created_at')
        data = _serialize_bookings(qs, request)

        # Public calendar needs dates only; owners/admins get full guest details
        user = request.user
        is_owner = (
            user
            and user.is_authenticated
            and (hotel.owner_id == user.id or getattr(user, 'role', None) == 'admin')
        )
        if not is_owner:
            data = [
                {
                    'id': row['id'],
                    'hotelId': row['hotelId'],
                    'roomId': row['roomId'],
                    'userId': '',
                    'guestName': '',
                    'guestPhone': '',
                    'checkIn': row['checkIn'],
                    'checkOut': row['checkOut'],
                    'guests': row.get('guests', 1),
                    'status': row['status'],
                    'paymentStatus': 'pending',
                    'totalAmount': 0,
                    'advanceAmount': 0,
                    'remainingAmount': 0,
                    'createdAt': row.get('createdAt', ''),
                    'updatedAt': row.get('updatedAt', ''),
                }
                for row in data
            ]
        return Response(api_success(data))

    def post(self, request, pk):
        hotel = _get_hotel(pk)
        serializer = HotelBookingCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        try:
            room = Room.objects.select_related('hotel').get(pk=data['roomId'], hotel=hotel)
        except Room.DoesNotExist as exc:
            raise NotFoundError('Room not found for this hotel.') from exc

        if not room.available:
            raise InvalidError('This room is not available.')

        nights = (data['checkOut'] - data['checkIn']).days
        if nights < hotel.minimum_stay:
            raise InvalidError(f'Minimum stay is {hotel.minimum_stay} night(s).')

        if room.capacity < data['guests']:
            raise InvalidError(f'Room capacity is {room.capacity} guests.')

        if _room_date_conflict(room.id, data['checkIn'], data['checkOut']):
            raise ConflictError('Room is already booked for these dates.')

        fees = calculate_booking_fees(room, data['checkIn'], data['checkOut'], hotel)
        payment_method = data.get('paymentMethod') or ''
        payment_status = data.get('paymentStatus') or PaymentStatus.PENDING

        if payment_method == 'cash':
            payment_status = PaymentStatus.PENDING
            booking_status = HotelBookingStatus.PENDING
        elif payment_status == PaymentStatus.PAID:
            booking_status = HotelBookingStatus.CONFIRMED
        elif payment_status == PaymentStatus.PARTIAL:
            booking_status = HotelBookingStatus.CONFIRMED
        else:
            booking_status = HotelBookingStatus.PENDING

        advance = fees['advanceAmount']
        if data.get('advanceAmount') is not None and payment_status == PaymentStatus.PARTIAL:
            advance = int(data['advanceAmount'])

        booking = HotelBooking.objects.create(
            hotel=hotel,
            room=room,
            user=request.user,
            guest_name=data['guestName'].strip(),
            guest_phone=data['guestPhone'].strip(),
            guest_email=data.get('guestEmail') or '',
            check_in=data['checkIn'],
            check_out=data['checkOut'],
            check_in_time=hotel.check_in_time,
            check_out_time=hotel.check_out_time,
            guests=data['guests'],
            status=booking_status,
            payment_status=payment_status,
            total_amount=fees['total'],
            advance_amount=advance,
            remaining_amount=fees['total'] - advance,
            payment_method=payment_method,
            transaction_id=data.get('transactionId') or '',
            special_requests=data.get('specialRequests') or '',
            fee_breakdown=fees,
        )
        hotel.refresh_room_counts()
        return Response(
            api_success(_serialize_booking(booking, request)),
            status=status.HTTP_201_CREATED,
        )


class MyHotelBookingsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        qs = HotelBooking.objects.filter(
            user=request.user,
            is_deleted=False,
        ).order_by('-created_at')
        return Response(api_success(_serialize_bookings(qs, request)))


class HotelBookingCancelView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, booking_id):
        serializer = HotelBookingCancelSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        reason = serializer.validated_data.get('reason') or ''

        try:
            booking = HotelBooking.objects.select_related('hotel', 'room').get(
                pk=booking_id,
                is_deleted=False,
            )
        except HotelBooking.DoesNotExist as exc:
            raise NotFoundError('Booking not found.') from exc

        user = request.user
        if booking.user_id != user.id and booking.hotel.owner_id != user.id and user.role != 'admin':
            raise ForbiddenError('You cannot cancel this booking.')

        if booking.status in (HotelBookingStatus.CANCELLED, HotelBookingStatus.COMPLETED):
            raise InvalidError('Booking cannot be cancelled.')

        refund = calculate_cancellation_refund(booking)
        booking.status = HotelBookingStatus.CANCELLED
        booking.cancelled_at = timezone.now()
        booking.cancellation_refund_amount = refund['refundAmount']
        booking.cancellation_note = reason.strip()
        if refund['refundAmount'] > 0:
            booking.payment_status = (
                PaymentStatus.REFUNDED
                if refund['refundPercent'] == 100
                else PaymentStatus.PARTIAL
            )
        booking.save()
        booking.hotel.refresh_room_counts()
        payload = _serialize_booking(booking, request)
        payload['cancellation'] = refund
        return Response(api_success(payload))


class HotelReviewListCreateView(APIView):
    def get_permissions(self):
        if self.request.method == 'GET':
            return [AllowAny()]
        return [IsAuthenticated()]

    def get(self, request, pk):
        hotel = _get_hotel(pk)
        reviews = HotelReview.objects.filter(hotel=hotel).select_related('user')
        data = HotelReviewSerializer(reviews, many=True, context={'request': request}).data
        return Response(api_success(data))

    def post(self, request, pk):
        hotel = _get_hotel(pk)
        serializer = HotelReviewCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        booking = None
        if data.get('bookingId'):
            try:
                booking = HotelBooking.objects.get(
                    pk=data['bookingId'],
                    hotel=hotel,
                    user=request.user,
                )
            except HotelBooking.DoesNotExist as exc:
                raise NotFoundError('Booking not found.') from exc

        review = HotelReview.objects.create(
            hotel=hotel,
            booking=booking,
            user=request.user,
            rating=data['rating'],
            comment=data['comment'].strip(),
            images=data.get('images') or [],
        )
        hotel.refresh_rating_cache()
        return Response(
            api_success(HotelReviewSerializer(review, context={'request': request}).data),
            status=status.HTTP_201_CREATED,
        )


class RoomPricingListView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, pk):
        hotel = _get_hotel(pk)
        room_id = request.query_params.get('roomId')
        if not room_id:
            raise InvalidError('roomId query parameter is required.')

        try:
            room = Room.objects.get(pk=room_id, hotel=hotel)
        except Room.DoesNotExist as exc:
            raise NotFoundError('Room not found.') from exc

        start_str = request.query_params.get('startDate') or request.query_params.get('checkIn')
        end_str = request.query_params.get('endDate') or request.query_params.get('checkOut')

        if start_str and end_str:
            start = datetime.strptime(start_str, '%Y-%m-%d').date()
            end = datetime.strptime(end_str, '%Y-%m-%d').date()
            data = room_pricing_for_range(room, start, end, hotel)
        elif start_str:
            single = datetime.strptime(start_str, '%Y-%m-%d').date()
            data = room_pricing_for_range(room, single, single, hotel)
        else:
            from datetime import date, timedelta
            today = date.today()
            data = room_pricing_for_range(room, today, today + timedelta(days=30), hotel)

        return Response(api_success(data))


class RoomPricingDetailView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, pk, room_id):
        hotel = _get_hotel(pk)
        try:
            room = Room.objects.get(pk=room_id, hotel=hotel)
        except Room.DoesNotExist as exc:
            raise NotFoundError('Room not found.') from exc

        start_str = request.query_params.get('startDate') or request.query_params.get('checkIn')
        end_str = request.query_params.get('endDate') or request.query_params.get('checkOut')

        if start_str and end_str:
            start = datetime.strptime(start_str, '%Y-%m-%d').date()
            end = datetime.strptime(end_str, '%Y-%m-%d').date()
            data = room_pricing_for_range(room, start, end, hotel)
        else:
            from datetime import date, timedelta
            today = date.today()
            data = room_pricing_for_range(room, today, today + timedelta(days=30), hotel)

        return Response(api_success(data))
