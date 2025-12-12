"""
Vietnam administrative divisions constants.
Updated for new administrative structure effective 01/07/2025.

After the merger (Nghị quyết 202/2025/QH15), Vietnam has 34 provinces/cities:
- 6 municipalities (thành phố trực thuộc TW)
- 28 provinces

Used for address validation in orders and shipping.
"""

# 34 provinces and municipalities of Vietnam (after 01/07/2025 merger)
# Source: https://bankervn.com/danh-sach-cac-tinh-thanh-viet-nam/
VIETNAM_PROVINCES = [
    # 6 Municipalities (Thành phố trực thuộc Trung ương)
    "Hà Nội",
    "Hồ Chí Minh",  # Merged: Bình Dương + TPHCM + Bà Rịa – Vũng Tàu
    "Đà Nẵng",       # Merged: Quảng Nam + TP. Đà Nẵng
    "Hải Phòng",     # Merged: Hải Dương + TP. Hải Phòng
    "Cần Thơ",       # Merged: Sóc Trăng + Hậu Giang + TP. Cần Thơ
    "Huế",           # Upgraded from Thừa Thiên Huế
    
    # 28 Provinces (Tỉnh)
    # Northern Region (Miền Bắc) - 15 tỉnh thành
    "Bắc Ninh",      # Merged: Bắc Giang + Bắc Ninh
    "Cao Bằng",
    "Điện Biên",
    "Hưng Yên",      # Merged: Thái Bình + Hưng Yên
    "Lai Châu",
    "Lạng Sơn",
    "Lào Cai",       # Merged: Lào Cai + Yên Bái
    "Ninh Bình",     # Merged: Hà Nam + Ninh Bình + Nam Định
    "Phú Thọ",       # Merged: Hòa Bình + Vĩnh Phúc + Phú Thọ
    "Quảng Ninh",
    "Sơn La",
    "Thái Nguyên",   # Merged: Bắc Kạn + Thái Nguyên
    "Thanh Hóa",
    "Tuyên Quang",   # Merged: Hà Giang + Tuyên Quang
    
    # Central Region (Miền Trung) - 11 tỉnh thành
    "Đắk Lắk",       # Merged: Phú Yên + Đắk Lắk
    "Gia Lai",       # Merged: Gia Lai + Bình Định
    "Hà Tĩnh",
    "Khánh Hòa",     # Merged: Khánh Hòa + Ninh Thuận
    "Lâm Đồng",      # Merged: Đắk Nông + Lâm Đồng + Bình Thuận
    "Nghệ An",
    "Quảng Ngãi",    # Merged: Quảng Ngãi + Kon Tum
    "Quảng Trị",     # Merged: Quảng Bình + Quảng Trị
    
    # Southern Region (Miền Nam) - 8 tỉnh thành
    "An Giang",      # Merged: Kiên Giang + An Giang
    "Cà Mau",        # Merged: Bạc Liêu + Cà Mau
    "Đồng Nai",      # Merged: Bình Phước + Đồng Nai
    "Đồng Tháp",     # Merged: Tiền Giang + Đồng Tháp
    "Tây Ninh",      # Merged: Long An + Tây Ninh
    "Vĩnh Long",     # Merged: Bến Tre + Vĩnh Long + Trà Vinh
]

# Legacy provinces (before 01/07/2025) - for backward compatibility
# Maps old province names to new merged province names
LEGACY_PROVINCE_MAPPING = {
    # Merged into Hồ Chí Minh
    "Bình Dương": "Hồ Chí Minh",
    "Bà Rịa - Vũng Tàu": "Hồ Chí Minh",
    "Bà Rịa Vũng Tàu": "Hồ Chí Minh",
    # Merged into Đà Nẵng
    "Quảng Nam": "Đà Nẵng",
    # Merged into Hải Phòng
    "Hải Dương": "Hải Phòng",
    # Merged into Cần Thơ
    "Sóc Trăng": "Cần Thơ",
    "Hậu Giang": "Cần Thơ",
    # Huế (renamed from Thừa Thiên Huế)
    "Thừa Thiên Huế": "Huế",
    # Merged into Bắc Ninh
    "Bắc Giang": "Bắc Ninh",
    # Merged into Hưng Yên
    "Thái Bình": "Hưng Yên",
    # Merged into Lào Cai
    "Yên Bái": "Lào Cai",
    # Merged into Ninh Bình
    "Hà Nam": "Ninh Bình",
    "Nam Định": "Ninh Bình",
    # Merged into Phú Thọ
    "Hòa Bình": "Phú Thọ",
    "Vĩnh Phúc": "Phú Thọ",
    # Merged into Thái Nguyên
    "Bắc Kạn": "Thái Nguyên",
    # Merged into Tuyên Quang
    "Hà Giang": "Tuyên Quang",
    # Merged into Đắk Lắk
    "Phú Yên": "Đắk Lắk",
    # Merged into Gia Lai
    "Bình Định": "Gia Lai",
    # Merged into Khánh Hòa
    "Ninh Thuận": "Khánh Hòa",
    # Merged into Lâm Đồng
    "Đắk Nông": "Lâm Đồng",
    "Bình Thuận": "Lâm Đồng",
    # Merged into Quảng Ngãi
    "Kon Tum": "Quảng Ngãi",
    # Merged into Quảng Trị
    "Quảng Bình": "Quảng Trị",
    # Merged into An Giang
    "Kiên Giang": "An Giang",
    # Merged into Cà Mau
    "Bạc Liêu": "Cà Mau",
    # Merged into Đồng Nai
    "Bình Phước": "Đồng Nai",
    # Merged into Đồng Tháp
    "Tiền Giang": "Đồng Tháp",
    # Merged into Tây Ninh
    "Long An": "Tây Ninh",
    # Merged into Vĩnh Long
    "Bến Tre": "Vĩnh Long",
    "Trà Vinh": "Vĩnh Long",
}

# Alternative names and common variations for fuzzy matching
PROVINCE_ALIASES = {
    "Hồ Chí Minh": ["HCM", "HCMC", "Ho Chi Minh", "Sài Gòn", "Saigon", "TP.HCM", "TP HCM", "Thành phố Hồ Chí Minh", "TPHCM"],
    "Hà Nội": ["Ha Noi", "Hanoi", "TP.Hà Nội", "Thành phố Hà Nội"],
    "Đà Nẵng": ["Da Nang", "TP.Đà Nẵng"],
    "Hải Phòng": ["Hai Phong", "TP.Hải Phòng"],
    "Cần Thơ": ["Can Tho", "TP.Cần Thơ"],
    "Huế": ["Hue", "TP.Huế", "Thành phố Huế", "Thừa Thiên Huế"],
    "Đắk Lắk": ["Dak Lak", "Đắk Lắc"],
    "Khánh Hòa": ["Khánh Hoà", "Khanh Hoa"],
    "Thanh Hóa": ["Thanh Hoá", "Thanh Hoa"],
}


def normalize_province_name(name: str) -> str | None:
    """
    Normalize and validate province name.
    Returns the canonical province name or None if not found.
    
    Handles:
    - Direct matches with current 34 provinces
    - Legacy province names (automatically mapped to new merged provinces)
    - Common aliases and variations
    
    Args:
        name: Province name to validate (can be alias or variation)
    
    Returns:
        Canonical province name or None if invalid
    """
    if not name:
        return None
    
    name = name.strip()
    
    # Direct match with current provinces
    if name in VIETNAM_PROVINCES:
        return name
    
    # Case-insensitive match with current provinces
    name_lower = name.lower()
    for province in VIETNAM_PROVINCES:
        if province.lower() == name_lower:
            return province
    
    # Check legacy province mapping (old provinces -> new merged provinces)
    for legacy, new_province in LEGACY_PROVINCE_MAPPING.items():
        if legacy.lower() == name_lower:
            return new_province
    
    # Check aliases
    for canonical, aliases in PROVINCE_ALIASES.items():
        if name_lower in [a.lower() for a in aliases]:
            return canonical
    
    return None


def is_valid_province(name: str) -> bool:
    """Check if a province name is valid (includes legacy names)."""
    return normalize_province_name(name) is not None


def get_legacy_mapping(old_province: str) -> str | None:
    """
    Get the new province name for a legacy (pre-merger) province.
    Returns None if the province was not merged.
    """
    return LEGACY_PROVINCE_MAPPING.get(old_province)


# Set for O(1) lookup
VIETNAM_PROVINCES_SET = set(VIETNAM_PROVINCES)
