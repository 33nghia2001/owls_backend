"""
Script để reset PostgreSQL database
Xóa tất cả tables và chạy lại migrations từ đầu

⚠️ CRITICAL WARNING: This script will DELETE ALL DATA in the database!
Only use in development environment.
"""

import os
import django
import sys

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from django.db import connection
from django.core.management import call_command
from django.conf import settings

def reset_database():
    """Drop tất cả tables và tạo lại từ đầu"""
    
    # CRITICAL SECURITY: Prevent running in production
    if not settings.DEBUG:
        print("\n" + "="*70)
        print("🚨 CRITICAL ERROR: reset_db.py MUST NOT run in production!")
        print("="*70)
        print("\nThis script will DELETE ALL DATA in the database.")
        print("DEBUG mode is currently: False")
        print("\nIf you really need to reset production database:")
        print("1. Create a full database backup first")
        print("2. Set DJANGO_DEBUG=True temporarily in .env")
        print("3. Re-run this script")
        print("4. Set DJANGO_DEBUG=False after reset")
        print("\nOr manually run SQL commands with explicit confirmation.")
        print("="*70 + "\n")
        sys.exit(1)
    
    # Double confirmation for safety
    env_confirm = os.environ.get('CONFIRM_RESET_DB', '')
    if env_confirm != 'YES':
        print("\n" + "="*70)
        print("⚠️  ADDITIONAL SAFETY CHECK REQUIRED")
        print("="*70)
        print("\nTo proceed, set environment variable:")
        print("  CONFIRM_RESET_DB=YES")
        print("\nExample:")
        print("  Windows: $env:CONFIRM_RESET_DB='YES'; python reset_db.py")
        print("  Linux:   CONFIRM_RESET_DB=YES python reset_db.py")
        print("="*70 + "\n")
        sys.exit(1)
    
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
