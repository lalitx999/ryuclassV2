import os
import time
import json
import re
import logging
import requests
from decimal import Decimal, InvalidOperation
from datetime import timedelta
from django.conf import settings
from django.utils import timezone
from django.db import transaction

from .models import Payment, SlipVerificationLog
from courses.models import Enrollment
from courses.services import AccessService
from users.models import User

logger = logging.getLogger(__name__)

EASYSLIP_API_URL = 'https://developer.easyslip.com/api/v1/verify'

def save_slip_file(slip_file, user_id):
    """
    Saves an uploaded slip file safely.
    Tries settings.SLIPS_STORAGE_DIR first.
    If writing fails due to an OSError (e.g. read-only filesystem Errno 30 or permission error),
    it automatically falls back to backend/storage/slips/.
    Returns (filename, target_path).
    """
    ext = os.path.splitext(slip_file.name)[1] or '.jpg'
    filename = f"slip_{user_id}_{int(time.time())}{ext}"

    primary_dir = getattr(settings, 'SLIPS_STORAGE_DIR', str(settings.BASE_DIR / 'storage' / 'slips'))
    fallback_dir = str(settings.BASE_DIR / 'storage' / 'slips')

    try:
        os.makedirs(primary_dir, exist_ok=True)
        target_path = os.path.join(primary_dir, filename)
        with open(target_path, 'wb+') as destination:
            for chunk in slip_file.chunks():
                destination.write(chunk)
        logger.info(f"Successfully saved slip {filename} to primary path: {target_path}")
        return filename, target_path
    except OSError as e:
        logger.warning(f"Failed to save slip to primary path {primary_dir} due to OSError: {e}. Falling back to {fallback_dir}")
        os.makedirs(fallback_dir, exist_ok=True)
        target_path = os.path.join(fallback_dir, filename)
        with open(target_path, 'wb+') as destination:
            for chunk in slip_file.chunks():
                destination.write(chunk)
        logger.info(f"Successfully saved slip {filename} to fallback path: {target_path}")
        return filename, target_path

@transaction.atomic
def approve_payment_transaction(payment, reviewed_by=None, trans_ref=None):
    """
    Unified canonical approval function for all entry points:
    1. Admin API Review (/api/admin/payments/<id>/review/)
    2. Legacy Backoffice Admin View
    3. EasySlip Auto Verification

    Atomically:
    - Increments user.total_spent by payment.amount
    - Recalculates lifetime tier unlocks
    - Grants/extends enrollment duration (video_expires_at & zoom_expires_at)
    - Updates payment.status to 'approved'
    """
    if payment.status == 'approved':
        return payment

    user = payment.user
    current_spent = Decimal(str(user.total_spent or '0'))
    payment_amt = Decimal(str(payment.amount or '0'))
    user.total_spent = current_spent + payment_amt
    user.save(update_fields=['total_spent'])
    AccessService.recalculate_lifetime_unlocks(user.id)

    enrollment, _ = Enrollment.objects.get_or_create(user=user, course=payment.course)
    enrollment.is_active = True
    enrollment.status = 'ACTIVE'
    enrollment.payment_id = payment.id
    enrollment.activated_at = timezone.now()

    if payment.duration_days >= 999:
        enrollment.is_lifetime_video = True
    else:
        base_date = max(enrollment.video_expires_at or timezone.localdate(), timezone.localdate())
        enrollment.video_expires_at = base_date + timedelta(days=payment.duration_days)
        if payment.is_zoom_included:
            zoom_base = max(enrollment.zoom_expires_at or timezone.localdate(), timezone.localdate())
            enrollment.zoom_expires_at = zoom_base + timedelta(days=payment.duration_days)
    enrollment.save()

    payment.status = 'approved'
    payment.rejection_reason = ''
    if trans_ref:
        payment.trans_ref = trans_ref
    payment.reviewed_at = timezone.now()
    if reviewed_by:
        payment.reviewed_by = reviewed_by
    payment.save()

    return payment

def verify_slip_easyslip(payment, target_path):
    """
    Sends the uploaded slip image to EasySlip API (v1/verify).
    Parses verification response:
    - Checks transferred amount vs payment.amount
    - Checks merchant account number (if configured)
    - Checks for duplicate slip (trans_ref)
    - If valid: auto-approves payment via approve_payment_transaction.
    - Creates SlipVerificationLog entry.
    Returns (success: bool, message: str, log_object: SlipVerificationLog).
    """
    api_key = getattr(settings, 'EASYSLIP_API_KEY', os.getenv('EASYSLIP_API_KEY', ''))
    merchant_account = getattr(settings, 'MERCHANT_ACCOUNT_NUMBER', os.getenv('MERCHANT_ACCOUNT_NUMBER', '')).strip()

    if not api_key:
        log = SlipVerificationLog.objects.create(
            payment=payment,
            user=payment.user,
            status='pending',
            error_message='EASYSLIP_API_KEY is not configured'
        )
        return False, 'ยังไม่ได้ตั้งค่า EASYSLIP_API_KEY', log

    try:
        headers = {
            'Authorization': f'Bearer {api_key}'
        }
        import mimetypes
        fname = os.path.basename(target_path)
        mime_type, _ = mimetypes.guess_type(target_path)
        mime_type = mime_type or 'image/jpeg'

        with open(target_path, 'rb') as f:
            files = {'file': (fname, f, mime_type)}
            response = requests.post(EASYSLIP_API_URL, headers=headers, files=files, timeout=30)

        raw_text = response.text
        try:
            res_json = response.json()
        except Exception:
            res_json = {'status': response.status_code, 'message': raw_text}

        # Check HTTP or EasySlip status
        api_status = res_json.get('status', response.status_code)
        if response.status_code != 200 or api_status != 200:
            err_msg = res_json.get('message') or res_json.get('error') or f"EasySlip API HTTP {response.status_code}"
            log = SlipVerificationLog.objects.create(
                payment=payment,
                user=payment.user,
                status='pending',
                raw_response=raw_text,
                error_message=err_msg
            )
            return False, f"ตรวจสอบสลิปไม่สำเร็จ: {err_msg}", log

        data = res_json.get('data', {})
        trans_ref = data.get('transRef') or data.get('payload', '')
        
        # Amount extraction
        verified_amount = None
        amount_data = data.get('amount', {})
        if isinstance(amount_data, dict):
            verified_amount_val = amount_data.get('amount') or amount_data.get('local', {}).get('amount')
            if verified_amount_val is not None:
                verified_amount = Decimal(str(verified_amount_val))
        elif isinstance(amount_data, (int, float, str)):
            verified_amount = Decimal(str(amount_data))

        # Bank and receiver extraction
        receiver_data = data.get('receiver', {})
        receiver_account_data = receiver_data.get('account', {})
        receiver_proxy_data = receiver_data.get('proxy', {})
        
        receiver_bank = receiver_data.get('bank', {}).get('name', '') or receiver_data.get('bank', {}).get('short', '')
        receiver_account = str(receiver_account_data.get('value', '') or receiver_proxy_data.get('value', ''))

        # Check duplicate slip trans_ref
        if trans_ref:
            duplicate_exists = Payment.objects.filter(
                trans_ref=trans_ref,
                status='approved'
            ).exclude(id=payment.id).exists()

            if duplicate_exists:
                log = SlipVerificationLog.objects.create(
                    payment=payment,
                    user=payment.user,
                    status='rejected',
                    verified_amount=verified_amount,
                    verified_bank=receiver_bank,
                    verified_account=receiver_account,
                    raw_response=raw_text,
                    error_message='สลิปนี้ถูกใช้งานไปแล้ว (Duplicate Slip trans_ref)'
                )
                payment.status = 'rejected'
                payment.rejection_reason = 'สลิปนี้ถูกใช้งานไปแล้วในระบบ'
                payment.trans_ref = trans_ref
                payment.save(update_fields=['status', 'rejection_reason', 'trans_ref'])
                return False, 'สลิปนี้ถูกใช้งานไปแล้วในระบบ', log

        # Check amount match
        if verified_amount is None or abs(verified_amount - payment.amount) > Decimal('0.01'):
            err_msg = f"ยอดเงินในสลิป (฿{verified_amount}) ไม่ตรงกับยอดที่ต้องชำระ (฿{payment.amount})"
            log = SlipVerificationLog.objects.create(
                payment=payment,
                user=payment.user,
                status='suspicious',
                verified_amount=verified_amount,
                verified_bank=receiver_bank,
                verified_account=receiver_account,
                raw_response=raw_text,
                error_message=err_msg
            )
            if trans_ref:
                payment.trans_ref = trans_ref
                payment.save(update_fields=['trans_ref'])
            return False, err_msg, log

        # Check merchant account match (if merchant_account configured)
        if merchant_account:
            clean_merchant = re.sub(r'\D', '', merchant_account)
            clean_receiver = re.sub(r'\D', '', receiver_account)
            if clean_merchant and clean_receiver and not clean_receiver.endswith(clean_merchant[-4:]):
                err_msg = f"บัญชีผู้รับในสลิป ({receiver_account}) ไม่ตรงกับบัญชีของทางร้าน ({merchant_account})"
                log = SlipVerificationLog.objects.create(
                    payment=payment,
                    user=payment.user,
                    status='suspicious',
                    verified_amount=verified_amount,
                    verified_bank=receiver_bank,
                    verified_account=receiver_account,
                    raw_response=raw_text,
                    error_message=err_msg
                )
                if trans_ref:
                    payment.trans_ref = trans_ref
                    payment.save(update_fields=['trans_ref'])
                return False, err_msg, log

        # ── SUCCESS: Auto-Approve Payment & Grant Course Access ───
        approve_payment_transaction(payment, trans_ref=trans_ref)

        log = SlipVerificationLog.objects.create(
            payment=payment,
            user=payment.user,
            status='approved',
            verified_amount=verified_amount,
            verified_bank=receiver_bank,
            verified_account=receiver_account,
            raw_response=raw_text
        )

        return True, "ตรวจสอบสลิปผ่าน EasySlip สำเร็จ และเปิดสิทธิ์การเรียนให้อัตโนมัติแล้ว", log

    except Exception as e:
        logger.error(f"Error calling EasySlip API for payment {payment.id}: {e}", exc_info=True)
        log = SlipVerificationLog.objects.create(
            payment=payment,
            user=payment.user,
            status='pending',
            error_message=str(e)
        )
        return False, f"เกิดข้อผิดพลาดในการเชื่อมต่อระบบตรวจสลิป: {str(e)}", log
