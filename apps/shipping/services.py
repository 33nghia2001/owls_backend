"""
Shipping provider integration services for GHN and GHTK.
"""
import httpx
import logging
from abc import ABC, abstractmethod
from typing import Optional
from decimal import Decimal
from dataclasses import dataclass
from django.conf import settings

logger = logging.getLogger(__name__)


@dataclass
class ShippingQuote:
    """Shipping fee calculation result."""
    provider: str
    service_type: str
    service_name: str
    fee: Decimal
    estimated_days: int
    insurance_fee: Decimal = Decimal('0')
    total_fee: Decimal = Decimal('0')
    
    def __post_init__(self):
        self.total_fee = self.fee + self.insurance_fee


@dataclass
class CreateOrderResult:
    """Result from creating shipping order."""
    success: bool
    tracking_number: str = ''
    order_code: str = ''
    expected_delivery: str = ''
    error: str = ''


@dataclass
class TrackingInfo:
    """Shipment tracking information."""
    status: str
    status_description: str
    location: str = ''
    timestamp: str = ''
    events: list = None
    
    def __post_init__(self):
        if self.events is None:
            self.events = []


class ShippingProvider(ABC):
    """Abstract base class for shipping providers."""
    
    @abstractmethod
    def calculate_fee(
        self,
        from_district_id: int,
        from_ward_code: str,
        to_district_id: int,
        to_ward_code: str,
        weight: int,  # grams
        length: int = 0,  # cm
        width: int = 0,
        height: int = 0,
        service_type: int = None,
        insurance_value: int = 0,
    ) -> list[ShippingQuote]:
        """Calculate shipping fee."""
        pass
    
    @abstractmethod
    def get_services(self, from_district: int, to_district: int) -> list[dict]:
        """Get available shipping services for route."""
        pass
    
    @abstractmethod
    def create_order(
        self,
        to_name: str,
        to_phone: str,
        to_address: str,
        to_ward_code: str,
        to_district_id: int,
        weight: int,
        cod_amount: int = 0,
        items: list = None,
        note: str = '',
        **kwargs
    ) -> CreateOrderResult:
        """Create shipping order."""
        pass
    
    @abstractmethod
    def track_order(self, tracking_number: str) -> TrackingInfo:
        """Track shipping order."""
        pass
    
    @abstractmethod
    def cancel_order(self, order_code: str) -> bool:
        """Cancel shipping order."""
        pass


class GHNProvider(ShippingProvider):
    """
    Giao Hàng Nhanh (GHN) API integration.
    API Docs: https://api.ghn.vn/home/docs/detail
    """
    
    BASE_URL = 'https://online-gateway.ghn.vn/shiip/public-api'
    SANDBOX_URL = 'https://dev-online-gateway.ghn.vn/shiip/public-api'
    
    # Service types
    SERVICE_EXPRESS = 2  # Hàng nhẹ
    SERVICE_STANDARD = 5  # Hàng nặng
    
    def __init__(self):
        self.token = getattr(settings, 'GHN_TOKEN', '')
        self.shop_id = getattr(settings, 'GHN_SHOP_ID', '')
        self.sandbox = getattr(settings, 'GHN_SANDBOX', True)
        self.base_url = self.SANDBOX_URL if self.sandbox else self.BASE_URL
        
        # Default warehouse info (can be configured per vendor)
        self.default_from_district_id = getattr(settings, 'GHN_FROM_DISTRICT_ID', 1542)  # Quận 1, HCM
        self.default_from_ward_code = getattr(settings, 'GHN_FROM_WARD_CODE', '21012')
    
    def _get_headers(self, shop_id: str = None) -> dict:
        return {
            'Token': self.token,
            'ShopId': str(shop_id or self.shop_id),
            'Content-Type': 'application/json',
        }
    
    async def _async_request(self, method: str, endpoint: str, data: dict = None, shop_id: str = None) -> dict:
        """Make async HTTP request to GHN API."""
        url = f"{self.base_url}{endpoint}"
        headers = self._get_headers(shop_id)
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                if method == 'GET':
                    response = await client.get(url, headers=headers, params=data)
                else:
                    response = await client.post(url, headers=headers, json=data)
                
                response.raise_for_status()
                result = response.json()
                
                if result.get('code') != 200:
                    logger.error(f"GHN API error: {result.get('message')}")
                    raise Exception(result.get('message', 'Unknown GHN error'))
                
                return result.get('data', {})
                
            except httpx.HTTPStatusError as e:
                logger.error(f"GHN HTTP error: {e.response.status_code} - {e.response.text}")
                raise
            except Exception as e:
                logger.error(f"GHN request error: {str(e)}")
                raise
    
    def _sync_request(self, method: str, endpoint: str, data: dict = None, shop_id: str = None) -> dict:
        """Make sync HTTP request to GHN API."""
        url = f"{self.base_url}{endpoint}"
        headers = self._get_headers(shop_id)
        
        try:
            with httpx.Client(timeout=30.0) as client:
                if method == 'GET':
                    response = client.get(url, headers=headers, params=data)
                else:
                    response = client.post(url, headers=headers, json=data)
                
                response.raise_for_status()
                result = response.json()
                
                if result.get('code') != 200:
                    logger.error(f"GHN API error: {result.get('message')}")
                    raise Exception(result.get('message', 'Unknown GHN error'))
                
                return result.get('data', {})
                
        except httpx.HTTPStatusError as e:
            logger.error(f"GHN HTTP error: {e.response.status_code} - {e.response.text}")
            raise
        except Exception as e:
            logger.error(f"GHN request error: {str(e)}")
            raise
    
    def get_provinces(self) -> list[dict]:
        """Get list of provinces."""
        data = self._sync_request('GET', '/master-data/province')
        return data if isinstance(data, list) else []
    
    def get_districts(self, province_id: int) -> list[dict]:
        """Get districts in a province."""
        data = self._sync_request('POST', '/master-data/district', {'province_id': province_id})
        return data if isinstance(data, list) else []
    
    def get_wards(self, district_id: int) -> list[dict]:
        """Get wards in a district."""
        data = self._sync_request('POST', '/master-data/ward', {'district_id': district_id})
        return data if isinstance(data, list) else []
    
    def get_services(self, from_district: int, to_district: int) -> list[dict]:
        """Get available shipping services for route."""
        data = self._sync_request('POST', '/v2/shipping-order/available-services', {
            'shop_id': int(self.shop_id),
            'from_district': from_district,
            'to_district': to_district,
        })
        return data if isinstance(data, list) else []
    
    def calculate_fee(
        self,
        from_district_id: int = None,
        from_ward_code: str = None,
        to_district_id: int = None,
        to_ward_code: str = None,
        weight: int = 500,  # grams
        length: int = 20,
        width: int = 20,
        height: int = 10,
        service_type: int = None,
        insurance_value: int = 0,
    ) -> list[ShippingQuote]:
        """
        Calculate shipping fee.
        Returns list of quotes for available services if service_type not specified.
        """
        from_district_id = from_district_id or self.default_from_district_id
        from_ward_code = from_ward_code or self.default_from_ward_code
        
        quotes = []
        
        # Get available services
        if service_type:
            services = [{'service_type_id': service_type}]
        else:
            try:
                services = self.get_services(from_district_id, to_district_id)
            except Exception:
                # Fallback to standard services
                services = [
                    {'service_type_id': self.SERVICE_EXPRESS, 'short_name': 'Express'},
                    {'service_type_id': self.SERVICE_STANDARD, 'short_name': 'Standard'},
                ]
        
        for service in services:
            try:
                payload = {
                    'shop_id': int(self.shop_id),
                    'service_type_id': service.get('service_type_id'),
                    'from_district_id': from_district_id,
                    'from_ward_code': from_ward_code,
                    'to_district_id': to_district_id,
                    'to_ward_code': to_ward_code,
                    'weight': weight,
                    'length': length,
                    'width': width,
                    'height': height,
                    'insurance_value': insurance_value,
                }
                
                data = self._sync_request('POST', '/v2/shipping-order/fee', payload)
                
                if data:
                    quotes.append(ShippingQuote(
                        provider='GHN',
                        service_type=str(service.get('service_type_id')),
                        service_name=service.get('short_name', 'GHN Delivery'),
                        fee=Decimal(str(data.get('total', 0))),
                        insurance_fee=Decimal(str(data.get('insurance', 0))),
                        estimated_days=self._estimate_delivery_days(service.get('service_type_id')),
                    ))
            except Exception as e:
                logger.warning(f"Failed to get quote for service {service}: {e}")
                continue
        
        return quotes
    
    def _estimate_delivery_days(self, service_type_id: int) -> int:
        """Estimate delivery days based on service type."""
        if service_type_id == self.SERVICE_EXPRESS:
            return 2
        return 4
    
    def create_order(
        self,
        to_name: str,
        to_phone: str,
        to_address: str,
        to_ward_code: str,
        to_district_id: int,
        weight: int,
        cod_amount: int = 0,
        items: list = None,
        note: str = '',
        service_type_id: int = None,
        from_district_id: int = None,
        from_ward_code: str = None,
        insurance_value: int = 0,
        **kwargs
    ) -> CreateOrderResult:
        """Create shipping order in GHN system."""
        
        from_district_id = from_district_id or self.default_from_district_id
        from_ward_code = from_ward_code or self.default_from_ward_code
        service_type_id = service_type_id or self.SERVICE_EXPRESS
        
        # Format items
        formatted_items = []
        for item in (items or []):
            formatted_items.append({
                'name': item.get('name', 'Product'),
                'quantity': item.get('quantity', 1),
                'weight': item.get('weight', 200),
            })
        
        payload = {
            'to_name': to_name,
            'to_phone': to_phone,
            'to_address': to_address,
            'to_ward_code': to_ward_code,
            'to_district_id': to_district_id,
            'from_district_id': from_district_id,
            'from_ward_code': from_ward_code,
            'weight': weight,
            'service_type_id': service_type_id,
            'payment_type_id': 2 if cod_amount > 0 else 1,  # 1=seller pays, 2=buyer pays
            'cod_amount': cod_amount,
            'insurance_value': insurance_value,
            'required_note': 'KHONGCHOXEMHANG',  # Don't allow inspection
            'note': note,
            'items': formatted_items,
        }
        
        try:
            data = self._sync_request('POST', '/v2/shipping-order/create', payload)
            
            return CreateOrderResult(
                success=True,
                tracking_number=data.get('order_code', ''),
                order_code=data.get('order_code', ''),
                expected_delivery=data.get('expected_delivery_time', ''),
            )
        except Exception as e:
            logger.error(f"Failed to create GHN order: {e}")
            return CreateOrderResult(success=False, error=str(e))
    
    def track_order(self, tracking_number: str) -> TrackingInfo:
        """Track shipping order by tracking number."""
        try:
            data = self._sync_request('POST', '/v2/shipping-order/detail', {
                'order_code': tracking_number,
            })
            
            # GHN status mapping
            status_map = {
                'ready_to_pick': ('pending', 'Chờ lấy hàng'),
                'picking': ('picked_up', 'Đang lấy hàng'),
                'picked': ('in_transit', 'Đã lấy hàng'),
                'storing': ('in_transit', 'Đang lưu kho'),
                'transporting': ('in_transit', 'Đang vận chuyển'),
                'sorting': ('in_transit', 'Đang phân loại'),
                'delivering': ('out_for_delivery', 'Đang giao hàng'),
                'delivered': ('delivered', 'Đã giao hàng'),
                'delivery_fail': ('failed', 'Giao hàng thất bại'),
                'return': ('returned', 'Đang hoàn trả'),
                'returned': ('returned', 'Đã hoàn trả'),
                'cancel': ('cancelled', 'Đã hủy'),
            }
            
            ghn_status = data.get('status', '').lower()
            status, description = status_map.get(ghn_status, ('unknown', ghn_status))
            
            # Get tracking log
            events = []
            for log in data.get('log', []):
                events.append({
                    'status': log.get('status', ''),
                    'timestamp': log.get('updated_date', ''),
                })
            
            return TrackingInfo(
                status=status,
                status_description=description,
                events=events,
            )
        except Exception as e:
            logger.error(f"Failed to track GHN order {tracking_number}: {e}")
            return TrackingInfo(status='error', status_description=str(e))
    
    def cancel_order(self, order_code: str) -> bool:
        """Cancel shipping order."""
        try:
            self._sync_request('POST', '/v2/switch-status/cancel', {
                'order_codes': [order_code],
            })
            return True
        except Exception as e:
            logger.error(f"Failed to cancel GHN order {order_code}: {e}")
            return False
    
    def get_print_url(self, order_code: str) -> str:
        """Get URL to print shipping label."""
        return f"{self.base_url}/v2/a5/gen-token?order_codes={order_code}"


class GHTKProvider(ShippingProvider):
    """
    Giao Hàng Tiết Kiệm (GHTK) API integration.
    API Docs: https://docs.giaohangtietkiem.vn/
    """
    
    BASE_URL = 'https://services.giaohangtietkiem.vn'
    SANDBOX_URL = 'https://services.ghtklab.com'
    
    def __init__(self):
        self.token = getattr(settings, 'GHTK_TOKEN', '')
        self.sandbox = getattr(settings, 'GHTK_SANDBOX', True)
        self.base_url = self.SANDBOX_URL if self.sandbox else self.BASE_URL
        
        # Default pickup address
        self.default_pick_province = getattr(settings, 'GHTK_PICK_PROVINCE', 'Hồ Chí Minh')
        self.default_pick_district = getattr(settings, 'GHTK_PICK_DISTRICT', 'Quận 1')
        self.default_pick_ward = getattr(settings, 'GHTK_PICK_WARD', 'Phường Bến Nghé')
        self.default_pick_address = getattr(settings, 'GHTK_PICK_ADDRESS', '')
    
    def _get_headers(self) -> dict:
        return {
            'Token': self.token,
            'Content-Type': 'application/json',
        }
    
    def _sync_request(self, method: str, endpoint: str, data: dict = None) -> dict:
        """Make sync HTTP request to GHTK API."""
        url = f"{self.base_url}{endpoint}"
        headers = self._get_headers()
        
        try:
            with httpx.Client(timeout=30.0) as client:
                if method == 'GET':
                    response = client.get(url, headers=headers, params=data)
                else:
                    response = client.post(url, headers=headers, json=data)
                
                response.raise_for_status()
                result = response.json()
                
                if not result.get('success'):
                    raise Exception(result.get('message', 'Unknown GHTK error'))
                
                return result
                
        except httpx.HTTPStatusError as e:
            logger.error(f"GHTK HTTP error: {e.response.status_code}")
            raise
        except Exception as e:
            logger.error(f"GHTK request error: {str(e)}")
            raise
    
    def get_services(self, from_district: int, to_district: int) -> list[dict]:
        """GHTK auto-selects service based on route."""
        return [
            {'service_type': 'road', 'name': 'Đường bộ'},
            {'service_type': 'fly', 'name': 'Đường bay'},
        ]
    
    def calculate_fee(
        self,
        from_district_id: int = None,
        from_ward_code: str = None,
        to_district_id: int = None,
        to_ward_code: str = None,
        weight: int = 500,
        length: int = 0,
        width: int = 0,
        height: int = 0,
        service_type: int = None,
        insurance_value: int = 0,
        # GHTK specific params
        pick_province: str = None,
        pick_district: str = None,
        province: str = None,
        district: str = None,
        address: str = '',
        value: int = 0,
    ) -> list[ShippingQuote]:
        """
        Calculate shipping fee.
        GHTK uses province/district names instead of IDs.
        """
        payload = {
            'pick_province': pick_province or self.default_pick_province,
            'pick_district': pick_district or self.default_pick_district,
            'province': province,
            'district': district,
            'address': address,
            'weight': weight,
            'value': value or insurance_value,
        }
        
        quotes = []
        
        for transport in ['road', 'fly']:
            try:
                payload['transport'] = transport
                data = self._sync_request('POST', '/services/shipment/fee', payload)
                fee_data = data.get('fee', {})
                
                quotes.append(ShippingQuote(
                    provider='GHTK',
                    service_type=transport,
                    service_name='Đường bay' if transport == 'fly' else 'Đường bộ',
                    fee=Decimal(str(fee_data.get('fee', 0))),
                    insurance_fee=Decimal(str(fee_data.get('insurance_fee', 0))),
                    estimated_days=2 if transport == 'fly' else 4,
                ))
            except Exception as e:
                logger.warning(f"GHTK fee calculation failed for {transport}: {e}")
                continue
        
        return quotes
    
    def create_order(
        self,
        to_name: str,
        to_phone: str,
        to_address: str,
        to_ward_code: str = None,
        to_district_id: int = None,
        weight: int = 500,
        cod_amount: int = 0,
        items: list = None,
        note: str = '',
        # GHTK specific
        province: str = '',
        district: str = '',
        ward: str = '',
        pick_province: str = None,
        pick_district: str = None,
        pick_ward: str = None,
        pick_address: str = None,
        pick_name: str = 'OWLS Shop',
        pick_tel: str = '',
        value: int = 0,
        **kwargs
    ) -> CreateOrderResult:
        """Create shipping order in GHTK system."""
        
        payload = {
            'products': [{'name': item.get('name', 'Product'), 'weight': item.get('weight', 0.2)} for item in (items or [])],
            'order': {
                'id': kwargs.get('order_id', ''),
                'pick_name': pick_name,
                'pick_address': pick_address or self.default_pick_address,
                'pick_province': pick_province or self.default_pick_province,
                'pick_district': pick_district or self.default_pick_district,
                'pick_ward': pick_ward or self.default_pick_ward,
                'pick_tel': pick_tel,
                'name': to_name,
                'address': to_address,
                'province': province,
                'district': district,
                'ward': ward,
                'tel': to_phone,
                'email': kwargs.get('email', ''),
                'hamlet': 'Khác',
                'is_freeship': 1 if cod_amount == 0 else 0,
                'pick_money': cod_amount,
                'value': value,
                'note': note,
                'transport': kwargs.get('transport', 'road'),
            }
        }
        
        try:
            data = self._sync_request('POST', '/services/shipment/order', payload)
            order_data = data.get('order', {})
            
            return CreateOrderResult(
                success=True,
                tracking_number=order_data.get('label', ''),
                order_code=order_data.get('partner_id', ''),
                expected_delivery=order_data.get('estimated_deliver_time', ''),
            )
        except Exception as e:
            logger.error(f"Failed to create GHTK order: {e}")
            return CreateOrderResult(success=False, error=str(e))
    
    def track_order(self, tracking_number: str) -> TrackingInfo:
        """Track shipping order."""
        try:
            data = self._sync_request('GET', f'/services/shipment/v2/{tracking_number}')
            order = data.get('order', {})
            
            status_map = {
                -1: ('cancelled', 'Đã hủy'),
                1: ('pending', 'Chưa tiếp nhận'),
                2: ('picked_up', 'Đã tiếp nhận'),
                3: ('in_transit', 'Đã lấy hàng'),
                4: ('in_transit', 'Đã nhập kho'),
                5: ('out_for_delivery', 'Đang giao hàng'),
                6: ('delivered', 'Đã giao hàng'),
                7: ('failed', 'Không giao được'),
                8: ('failed', 'Delay giao hàng'),
                9: ('failed', 'Không lấy được'),
                10: ('failed', 'Delay lấy hàng'),
                12: ('returned', 'Đã hoàn trả'),
                13: ('returned', 'Đang hoàn trả'),
            }
            
            ghtk_status = order.get('status', 1)
            status, description = status_map.get(ghtk_status, ('unknown', 'Không xác định'))
            
            return TrackingInfo(
                status=status,
                status_description=description,
                location=order.get('ship_address', ''),
            )
        except Exception as e:
            logger.error(f"Failed to track GHTK order {tracking_number}: {e}")
            return TrackingInfo(status='error', status_description=str(e))
    
    def cancel_order(self, order_code: str) -> bool:
        """Cancel shipping order."""
        try:
            self._sync_request('POST', f'/services/shipment/cancel/{order_code}')
            return True
        except Exception as e:
            logger.error(f"Failed to cancel GHTK order {order_code}: {e}")
            return False


# Factory function
def get_shipping_provider(provider: str = 'GHN') -> ShippingProvider:
    """Get shipping provider instance by name."""
    providers = {
        'GHN': GHNProvider,
        'GHTK': GHTKProvider,
    }
    
    provider_class = providers.get(provider.upper())
    if not provider_class:
        raise ValueError(f"Unknown shipping provider: {provider}")
    
    return provider_class()
