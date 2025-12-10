# 🎓 Mini LMS - Online Learning Platform

Nền tảng học tập trực tuyến chuyên nghiệp được xây dựng với Django REST Framework và tích hợp thanh toán VNPay.

## 📋 Tính năng chính

### 👥 Quản lý người dùng (Users App)
- ✅ Custom User Model với nhiều vai trò (Student, Instructor, Admin)
- ✅ Hồ sơ giảng viên mở rộng với thống kê
- ✅ Tích hợp Cloudinary cho avatar
- ✅ Social links và notification preferences

### 📚 Quản lý khóa học (Courses App)
- ✅ Danh mục khóa học phân cấp
- ✅ Khóa học với sections và lessons
- ✅ Nhiều loại bài học: Video, Article, Quiz, Assignment
- ✅ Tài liệu đính kèm cho mỗi bài học
- ✅ Quiz với nhiều loại câu hỏi
- ✅ Pricing linh hoạt với discount

### 📝 Đăng ký học (Enrollments App)
- ✅ Theo dõi tiến độ học tập chi tiết
- ✅ Progress tracking cho từng bài học
- ✅ Quiz attempts và scoring
- ✅ Chứng chỉ hoàn thành khóa học

### 💳 Thanh toán (Payments App)
- ✅ **Tích hợp VNPay Payment Gateway**
- ✅ Quản lý giao dịch chi tiết
- ✅ Discount codes và coupons
- ✅ Refund requests
- ✅ Transaction history

### ⭐ Đánh giá (Reviews App)
- ✅ Rating và review cho khóa học
- ✅ Helpful votes cho reviews
- ✅ Instructor replies
- ✅ Report inappropriate reviews
- ✅ Tự động cập nhật average rating

### 🔔 Thông báo (Notifications App)
- ✅ Real-time notifications
- ✅ Email notifications
- ✅ Push notifications preferences
- ✅ System announcements
- ✅ Course-specific announcements

## 🚀 Cài đặt

### 1. Clone repository
```bash
git clone <repository-url>
cd owls/backend
```

### 2. Tạo và kích hoạt môi trường ảo
```bash
python -m venv .venv
.\.venv\Scripts\Activate.ps1  # Windows PowerShell
```

### 3. Cài đặt dependencies
```bash
pip install -r requirements.txt
```

### 4. Cấu hình biến môi trường
Tạo file `.env` từ `.env.example` và cập nhật các giá trị:
```env
DJANGO_SECRET_KEY=your-secret-key
DJANGO_DEBUG=True
DATABASE_URL=sqlite:///db.sqlite3

# VNPay Configuration
VNPAY_TMN_CODE=your_vnpay_tmn_code
VNPAY_HASH_SECRET=your_vnpay_hash_secret
VNPAY_PAYMENT_URL=https://sandbox.vnpayment.vn/paymentv2/vpcpay.html
VNPAY_RETURN_URL=http://localhost:8000/api/payments/vnpay/callback
```

### 5. Chạy migrations
```bash
python manage.py makemigrations
python manage.py migrate
```

### 6. Tạo superuser
```bash
python manage.py createsuperuser
```

### 7. Chạy development server
```bash
python manage.py runserver
```

## 📁 Cấu trúc project

```
backend/
├── apps/
│   ├── users/          # Quản lý người dùng
│   ├── courses/        # Quản lý khóa học
│   ├── enrollments/    # Đăng ký và tiến độ học
│   ├── payments/       # Thanh toán VNPay
│   ├── reviews/        # Đánh giá khóa học
│   └── notifications/  # Hệ thống thông báo
├── backend/
│   ├── settings.py     # Cấu hình Django
│   ├── urls.py         # URL routing
│   └── wsgi.py
├── manage.py
├── requirements.txt
└── .env
```

## 🔐 VNPay Integration

### Đăng ký VNPay
1. Truy cập https://vnpay.vn/
2. Đăng ký tài khoản merchant
3. Lấy TMN Code và Hash Secret
4. Cập nhật vào file `.env`

### Test với Sandbox
VNPay cung cấp môi trường sandbox để test:
- URL: `https://sandbox.vnpayment.vn/paymentv2/vpcpay.html`
- Tài liệu: https://sandbox.vnpayment.vn/apis/docs/

## 📊 Database Models

### Core Models
- **User**: Custom user với roles
- **InstructorProfile**: Hồ sơ giảng viên
- **Course**: Khóa học
- **Section**: Chương học
- **Lesson**: Bài học
- **Enrollment**: Đăng ký học
- **Payment**: Giao dịch thanh toán
- **VNPayTransaction**: Chi tiết giao dịch VNPay
- **Review**: Đánh giá khóa học
- **Notification**: Thông báo

## 🛠️ API Endpoints (Sẽ được implement)

```
/api/auth/          # Authentication
/api/users/         # User management
/api/courses/       # Course management
/api/enrollments/   # Enrollment tracking
/api/payments/      # Payment processing
/api/reviews/       # Course reviews
/api/notifications/ # Notifications
```

## 📝 Development Notes

### Custom User Model
Project sử dụng custom User model (`apps.users.User`). Đảm bảo:
```python
AUTH_USER_MODEL = 'users.User'
```

### Cloudinary Storage
Cấu hình Cloudinary cho media files:
```env
CLOUDINARY_CLOUD_NAME=your_cloud_name
CLOUDINARY_API_KEY=your_api_key
CLOUDINARY_API_SECRET=your_api_secret
```

## 🎯 Next Steps

1. ✅ Models đã hoàn thành
2. 🔄 Implement Serializers
3. 🔄 Implement ViewSets
4. 🔄 Setup URL routing
5. 🔄 VNPay payment integration
6. 🔄 JWT Authentication
7. 🔄 API Documentation với drf-spectacular

## 📄 License

This project is licensed under the MIT License.

## 👨‍💻 Author

Created with ❤️ for Online Learning Platform
