# backend/settings/__init__.py

from os import environ
from split_settings.tools import optional, include

# 1. Lấy tên môi trường từ biến ENV, mặc định là 'local'
# Các giá trị có thể là: 'local', 'production', 'staging', 'test'
ENV = environ.get('DJANGO_ENV', 'local')

# 2. Định nghĩa danh sách các files settings cần load theo thứ tự ưu tiên
base_settings = [
    # Load cấu hình gốc đầu tiên (chứa Apps, Middleware, Database chung...)
    'base.py',

    # Tiếp theo load cấu hình riêng theo môi trường (local.py hoặc production.py)
    # File này sẽ override các giá trị trùng lặp trong base.py
    f'{ENV}.py',

    # (Tuỳ chọn) Load file local_settings.py nếu tồn tại.
    # File này thường nằm trong .gitignore, dùng để dev override tạm thời
    # mà không sợ commit nhầm lên git.
    optional('local_settings.py'),
]

# 3. Thực thi include
include(*base_settings)