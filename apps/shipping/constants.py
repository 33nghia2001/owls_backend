"""
Vietnam administrative divisions constants.
This is a validated list of provinces/cities in Vietnam.
Used for address validation in orders and shipping.
"""

# 63 provinces and municipalities of Vietnam
# Source: https://en.wikipedia.org/wiki/Provinces_of_Vietnam
VIETNAM_PROVINCES = [
    # Municipalities (Thành phố trực thuộc Trung ương)
    "Hà Nội",
    "Hồ Chí Minh",
    "Đà Nẵng",
    "Hải Phòng",
    "Cần Thơ",
    
    # Northern Region (Miền Bắc)
    "Hà Giang",
    "Cao Bằng",
    "Bắc Kạn",
    "Tuyên Quang",
    "Lào Cai",
    "Điện Biên",
    "Lai Châu",
    "Sơn La",
    "Yên Bái",
    "Hoà Bình",
    "Thái Nguyên",
    "Lạng Sơn",
    "Quảng Ninh",
    "Bắc Giang",
    "Phú Thọ",
    "Vĩnh Phúc",
    "Bắc Ninh",
    "Hải Dương",
    "Hưng Yên",
    "Thái Bình",
    "Hà Nam",
    "Nam Định",
    "Ninh Bình",
    
    # Central Region (Miền Trung)
    "Thanh Hoá",
    "Nghệ An",
    "Hà Tĩnh",
    "Quảng Bình",
    "Quảng Trị",
    "Thừa Thiên Huế",
    "Quảng Nam",
    "Quảng Ngãi",
    "Bình Định",
    "Phú Yên",
    "Khánh Hoà",
    "Ninh Thuận",
    "Bình Thuận",
    
    # Central Highlands (Tây Nguyên)
    "Kon Tum",
    "Gia Lai",
    "Đắk Lắk",
    "Đắk Nông",
    "Lâm Đồng",
    
    # Southern Region (Miền Nam)
    "Bình Phước",
    "Tây Ninh",
    "Bình Dương",
    "Đồng Nai",
    "Bà Rịa - Vũng Tàu",
    "Long An",
    "Tiền Giang",
    "Bến Tre",
    "Trà Vinh",
    "Vĩnh Long",
    "Đồng Tháp",
    "An Giang",
    "Kiên Giang",
    "Hậu Giang",
    "Sóc Trăng",
    "Bạc Liêu",
    "Cà Mau",
]

# Alternative names and common variations for fuzzy matching
PROVINCE_ALIASES = {
    "Hồ Chí Minh": ["HCM", "HCMC", "Ho Chi Minh", "Sài Gòn", "Saigon", "TP.HCM", "TP HCM", "Thành phố Hồ Chí Minh"],
    "Hà Nội": ["Ha Noi", "Hanoi", "TP.Hà Nội", "Thành phố Hà Nội"],
    "Đà Nẵng": ["Da Nang", "TP.Đà Nẵng"],
    "Hải Phòng": ["Hai Phong", "TP.Hải Phòng"],
    "Cần Thơ": ["Can Tho", "TP.Cần Thơ"],
    "Bà Rịa - Vũng Tàu": ["Bà Rịa Vũng Tàu", "Ba Ria Vung Tau", "Vũng Tàu", "Vung Tau"],
    "Thừa Thiên Huế": ["Huế", "Hue", "Thua Thien Hue"],
    "Đắk Lắk": ["Dak Lak", "Đắk Lắc"],
    "Đắk Nông": ["Dak Nong"],
}


def normalize_province_name(name: str) -> str | None:
    """
    Normalize and validate province name.
    Returns the canonical province name or None if not found.
    
    Args:
        name: Province name to validate (can be alias or variation)
    
    Returns:
        Canonical province name or None if invalid
    """
    if not name:
        return None
    
    name = name.strip()
    
    # Direct match
    if name in VIETNAM_PROVINCES:
        return name
    
    # Case-insensitive match
    name_lower = name.lower()
    for province in VIETNAM_PROVINCES:
        if province.lower() == name_lower:
            return province
    
    # Check aliases
    for canonical, aliases in PROVINCE_ALIASES.items():
        if name_lower in [a.lower() for a in aliases]:
            return canonical
    
    # Fuzzy match: remove diacritics and check
    # (Simple implementation - for production, consider using unidecode)
    return None


def is_valid_province(name: str) -> bool:
    """Check if a province name is valid."""
    return normalize_province_name(name) is not None


# Set for O(1) lookup
VIETNAM_PROVINCES_SET = set(VIETNAM_PROVINCES)
