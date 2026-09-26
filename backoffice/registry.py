"""Explicit backoffice catalogue, independent of ModelAdmin and its templates."""
from django.apps import apps

GROUPS = {
    'users': 'สมาชิก', 'auth': 'กลุ่มสิทธิ์', 'courses': 'คอร์สและการเรียน',
    'payments': 'การชำระเงิน', 'quizzes': 'ข้อสอบและคำศัพท์',
    'community': 'ชุมชน', 'affiliates': 'ตัวแทนและคอมมิชชัน',
    'support': 'ช่วยเหลือและ AI', 'system_config': 'ตั้งค่าระบบ',
}
LABELS = {
    'user': 'นักเรียนและสมาชิก', 'group': 'กลุ่มสิทธิ์', 'course': 'คอร์สเรียน',
    'module': 'หมวดบทเรียน', 'lesson': 'บทเรียน', 'enrollment': 'สิทธิ์การเรียน',
    'progress': 'ความคืบหน้า', 'note': 'โน้ตนักเรียน', 'gamescore': 'คะแนนเกม',
    'payment': 'รายการชำระเงิน', 'slipblacklistpattern': 'เงื่อนไขสลิปต้องสงสัย',
    'slipverificationlog': 'ประวัติตรวจสลิป', 'quiz': 'ชุดข้อสอบ',
    'quizquestion': 'คำถาม', 'quizattempt': 'ผลการสอบ', 'vocabulary': 'คำศัพท์',
    'post': 'โพสต์', 'postimage': 'ภาพประกอบโพสต์', 'comment': 'ความคิดเห็น', 'postlike': 'ถูกใจ',
    'affiliateprofile': 'ตัวแทน', 'affiliateclick': 'ประวัติคลิก',
    'affiliatecommission': 'ค่าคอมมิชชัน', 'affiliatecouponlog': 'ประวัติคูปอง',
    'affiliatepayout': 'รายการถอนเงิน', 'supportticket': 'คำร้องช่วยเหลือ',
    'chatlog': 'ประวัติแชต', 'conversationsession': 'เซสชันสนทนา',
    'araigogusession': 'สนทนา Araigogu', 'araigogumessage': 'ข้อความ Araigogu',
    'systemsetting': 'ตั้งค่าระบบ', 'lifetimestudentimport': 'นักเรียนตลอดชีพ',
    'migrationrequest': 'คำขอย้ายระบบ',
}
READ_ONLY = {'progress', 'note', 'quizattempt', 'slipverificationlog', 'affiliateclick',
             'affiliatecouponlog', 'postlike', 'chatlog', 'conversationsession',
             'araigogusession', 'araigogumessage'}
PROTECTED_DELETE = {'user', 'payment', 'affiliatepayout', 'affiliatecommission', 'affiliateprofile'}

COLUMNS = {
    'user': ['id', 'email', 'name', 'role', 'total_spent', 'is_active'],
    'course': ['id', 'title', 'price', 'is_active', 'sort_order'],
    'lesson': ['id', 'title', 'course', 'module', 'is_free', 'sort_order'],
    'enrollment': ['id', 'user', 'course', 'status', 'video_expires_at', 'is_lifetime_video'],
    'payment': ['id', 'user', 'course', 'amount', 'status', 'submitted_at'],
    'affiliatepayout': ['id', 'user', 'amount', 'status', 'requested_at'],
}

def catalogue():
    return {f'{app}/{model._meta.model_name}': model
            for app in GROUPS for model in apps.get_app_config(app).get_models()
            if model._meta.model_name in LABELS}

def allowed(user, model, action='view'):
    name = model._meta.model_name
    if not user.is_active or not user.is_staff:
        return False
    if action != 'view' and name in READ_ONLY:
        return False
    if action == 'delete' and name in PROTECTED_DELETE:
        return False
    if (name in {'group', 'systemsetting'} or (name == 'user' and action != 'view')) and not user.is_superuser:
        return False
    return user.has_perm(f'{model._meta.app_label}.{action}_{name}')

def menu(user):
    groups = []
    for app, label in GROUPS.items():
        items = [{'key': key, 'label': LABELS[model._meta.model_name]}
                 for key, model in catalogue().items()
                 if model._meta.app_label == app and allowed(user, model)]
        if items:
            groups.append({'label': label, 'items': items})
    return groups
