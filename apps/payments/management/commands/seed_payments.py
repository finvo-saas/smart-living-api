"""Seed sample payment transactions and owner payouts for dev."""
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.utils import timezone

from accounts.models import User
from billing.models import Bill, BillStatus
from payments.models import (
    OwnerPayout,
    PaymentMethod,
    PaymentTransaction,
    PaymentTransactionStatus,
    PayoutStatus,
)
from payments.services.helpers import calc_commission


class Command(BaseCommand):
    help = 'Seed sample completed payment + owner payout if bills exist'

    def handle(self, *args, **options):
        owner = User.objects.filter(role='owner').order_by('created_at').first()
        tenant = User.objects.filter(role='renter').order_by('created_at').first()

        if not owner:
            self.stdout.write(self.style.WARNING('No owner user found — run seed_portfolio first.'))
            return

        bill = (
            Bill.objects.filter(is_deleted=False, status=BillStatus.UNPAID)
            .order_by('created_at')
            .first()
        )
        if bill is None:
            bill = Bill.objects.filter(is_deleted=False).order_by('created_at').first()

        if bill is None:
            self.stdout.write(self.style.WARNING('No bills found — run seed_portfolio first.'))
            return

        payer = bill.tenant or tenant or owner
        txn_id = 'BKS-SEED-88421'
        bill_name = f'{bill.month} {bill.year} — {bill.property_name}'

        txn, created = PaymentTransaction.objects.update_or_create(
            transaction_id=txn_id,
            defaults={
                'user': payer,
                'bill': bill,
                'bill_name': bill_name,
                'property_name': bill.property_name,
                'tenant_name': bill.tenant_name,
                'amount': bill.amount,
                'payment_method': PaymentMethod.BKASH,
                'account_number': '01711111111',
                'status': PaymentTransactionStatus.COMPLETED,
                'completed_at': timezone.now(),
                'gateway_payload': {'seed': True},
            },
        )

        bill.status = BillStatus.PAID
        bill.paid_date = timezone.now().date()
        bill.save(update_fields=['status', 'paid_date', 'updated_at'])

        rate_pct, commission_amount, net_amount = calc_commission(Decimal(str(bill.amount)))
        payout, payout_created = OwnerPayout.objects.update_or_create(
            payment_transaction=txn,
            defaults={
                'owner': bill.owner,
                'bill': bill,
                'bill_name': bill_name,
                'tenant_name': bill.tenant_name,
                'property_name': bill.property_name,
                'gross_amount': bill.amount,
                'commission_rate': rate_pct,
                'commission_amount': commission_amount,
                'net_amount': net_amount,
                'payment_method': PaymentMethod.BKASH,
                'transaction_id': txn_id,
                'status': PayoutStatus.PAID,
                'paid_at': txn.completed_at,
                'payout_date': timezone.now().date(),
            },
        )

        action = 'Created' if created else 'Updated'
        self.stdout.write(self.style.SUCCESS(f'{action} seed payment transaction'))
        self.stdout.write(f'  transaction_id={txn.transaction_id}')
        self.stdout.write(f'  bill_id={bill.id}')
        self.stdout.write(f'  payout_id={payout.id} ({("created" if payout_created else "updated")})')
