from django import template

register = template.Library()
APP_LABELS = {
    'users': 'สมาชิก', 'courses': 'คอร์สและการเรียน', 'payments': 'การชำระเงิน',
    'quizzes': 'แบบทดสอบและคำศัพท์', 'affiliates': 'ตัวแทนและคอมมิชชัน',
    'support': 'ช่วยเหลือและประวัติ AI', 'system_config': 'ตั้งค่าระบบ', 'auth': 'สิทธิ์การใช้งาน',
}
MODEL_LABELS = {
    'User': 'นักเรียนและสมาชิก', 'Course': 'คอร์สเรียน', 'Module': 'หมวดบทเรียน',
    'Lesson': 'วิดีโอและบทเรียน', 'Enrollment': 'สิทธิ์การเรียน', 'Progress': 'ความคืบหน้าการเรียน',
    'Note': 'โน้ตของนักเรียน', 'GameScore': 'คะแนนเกม', 'Payment': 'รายการชำระเงิน',
    'SlipBlacklistPattern': 'เงื่อนไขสลิปต้องสงสัย', 'SlipVerificationLog': 'ประวัติตรวจสลิป',
    'Quiz': 'ชุดแบบทดสอบ', 'QuizQuestion': 'คลังข้อสอบ', 'QuizAttempt': 'ผลการสอบ',
    'Vocabulary': 'คลังคำศัพท์', 'AffiliateProfile': 'โปรไฟล์ตัวแทน',
    'AffiliateClick': 'ประวัติคลิกลิงก์', 'AffiliateCommission': 'ค่าคอมมิชชัน',
    'AffiliateCouponLog': 'ประวัติคูปอง', 'AffiliatePayout': 'รายการถอนเงิน',
    'SupportTicket': 'คำร้องขอความช่วยเหลือ', 'ChatLog': 'ประวัติแชต AI',
    'ConversationSession': 'เซสชันการสนทนา', 'SystemSetting': 'การตั้งค่า',
    'LifetimeStudentImport': 'นำเข้านักเรียนตลอดชีพ', 'MigrationRequest': 'คำขอย้ายระบบ',
    'Group': 'กลุ่มสิทธิ์',
}

@register.filter
def app_label(app):
    return APP_LABELS.get(app['app_label'], app['name'])

@register.filter
def model_label(model):
    return MODEL_LABELS.get(model['object_name'], model['name'])
