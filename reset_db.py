"""
Script để reset PostgreSQL database
Xóa tất cả tables và chạy lại migrations từ đầu
"""

import os
import django
import sys

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from django.db import connection
from django.core.management import call_command

def reset_database():
    """Drop tất cả tables và tạo lại từ đầu"""
    
    with connection.cursor() as cursor:
        # Lấy danh sách tất cả tables
        cursor.execute("""
            SELECT tablename FROM pg_tables 
            WHERE schemaname = 'public'
        """)
        tables = cursor.fetchall()
        
        if not tables:
            print("✓ Database đã sạch, không có tables nào.")
            return
        
        print(f"\n🗑️  Tìm thấy {len(tables)} tables:")
        for table in tables:
            print(f"   - {table[0]}")
        
        # Xác nhận
        confirm = input("\n⚠️  Bạn có chắc muốn XÓA TẤT CẢ tables? (yes/no): ")
        
        if confirm.lower() != 'yes':
            print("❌ Hủy bỏ.")
            return
        
        # Drop tất cả tables (CASCADE sẽ tự động xóa dependencies)
        print("\n🔥 Đang xóa tables...")
        for table in tables:
            table_name = table[0]
            try:
                cursor.execute(f'DROP TABLE IF EXISTS "{table_name}" CASCADE')
                print(f"   ✓ Đã xóa {table_name}")
            except Exception as e:
                print(f"   ⚠️  Không xóa được {table_name}: {e}")
        
        print("\n✅ Đã xóa tất cả tables!")
    
    # Chạy migrations
    print("\n📦 Đang chạy migrations...")
    call_command('migrate')
    
    print("\n🎉 Reset database hoàn tất!")
    print("\n📝 Bước tiếp theo:")
    print("   1. python manage.py createsuperuser")
    print("   2. Thêm dữ liệu mẫu nếu cần")


if __name__ == '__main__':
    try:
        reset_database()
    except Exception as e:
        print(f"\n❌ Lỗi: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
