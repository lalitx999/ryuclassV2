# 🐍 RyuClass Backend (Django REST API & Admin Portal)

ส่วนประมวลผลหลังบ้านของระบบ RyuClass พัฒนาด้วย **Django 5.0** และ **Django REST Framework (DRF)** พร้อมหน้าบริหารจัดการ **Django Unfold Admin UI**

---

## 📌 คุณสมบัติสำคัญ

* **Django Unfold Admin Theme:** หน้าบริหารจัดการสไตล์ Tailwind CSS พร้อม KPI Dashboard ในหน้าแรก
* **Slip QC & Verification:** ตรวจสอบสลิป ปลูกสิทธิ์การเข้าเรียน (Enrollment) อัตโนมัติเมื่อกดอนุมัติ
* **Access Control & Expiry:** คำนวณวันหมดอายุคลิปบทเรียน และการเข้าถึงระบบ Zoom
* **Affiliate & Commissions:** ระบบตัวแทนจำหน่าย คำนวณค่าคอมมิชชันและคำขอถอนเงิน (Payouts)
* **JWT Authentication:** ล็อกอินและออก Token สำหรับ Frontend (`/api/token/`, `/api/token/refresh/`)

---

## 🚀 การใช้งานสำหรับนักพัฒนา (Developer Guide)

### เปิดใช้งาน Virtual Environment และรันเซิร์ฟเวอร์:

```bash
cd backend
source venv/bin/activate
python manage.py runserver
```

### URL สำคัญ:
* **Admin Dashboard:** `http://127.0.0.1:8000/admin/`
* **API Endpoints:** `http://127.0.0.1:8000/api/`
