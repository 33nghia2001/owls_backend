# Cloudflare Turnstile Integration

Hệ thống đã tích hợp **Cloudflare Turnstile CAPTCHA** để bảo vệ các endpoint nhạy cảm khỏi bot và spam attacks.

## Cấu hình

### 1. Lấy Turnstile Keys

1. Truy cập: https://dash.cloudflare.com/
2. Vào phần **Turnstile**
3. Tạo một site mới và lấy:
   - **Site Key** (dùng cho frontend)
   - **Secret Key** (dùng cho backend)

### 2. Cập nhật `.env`

```env
TURNSTILE_SITEKEY=your-turnstile-sitekey
TURNSTILE_SECRET=your-turnstile-secret
TURNSTILE_TEST_MODE=True  # False in production
```

## Endpoints được bảo vệ

### 1. User Registration (`POST /api/users/register/`)

**Request body:**
```json
{
  "username": "newuser",
  "email": "user@example.com",
  "password": "securepassword123",
  "first_name": "John",
  "last_name": "Doe",
  "turnstile": "turnstile-token-from-frontend"
}
```

### 2. Payment Creation (`POST /api/payments/`)

**Request body:**
```json
{
  "course": 1,
  "amount": 500000,
  "currency": "VND",
  "payment_method": "vnpay",
  "discount": 1,
  "turnstile": "turnstile-token-from-frontend"
}
```

## Frontend Integration

### HTML Example (Remix/React)

```jsx
import { useEffect } from 'react';

export default function RegisterForm() {
  useEffect(() => {
    // Load Turnstile script
    const script = document.createElement('script');
    script.src = 'https://challenges.cloudflare.com/turnstile/v0/api.js';
    script.async = true;
    script.defer = true;
    document.body.appendChild(script);
  }, []);

  const handleSubmit = async (e) => {
    e.preventDefault();
    const formData = new FormData(e.target);
    
    // Get turnstile response
    const turnstileResponse = formData.get('cf-turnstile-response');
    
    const data = {
      username: formData.get('username'),
      email: formData.get('email'),
      password: formData.get('password'),
      first_name: formData.get('first_name'),
      last_name: formData.get('last_name'),
      turnstile: turnstileResponse  // Add this
    };

    const response = await fetch('http://localhost:8000/api/users/register/', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data)
    });

    if (response.ok) {
      // Success
    } else {
      const error = await response.json();
      console.error('Error:', error);
    }
  };

  return (
    <form onSubmit={handleSubmit}>
      <input name="username" required />
      <input name="email" type="email" required />
      <input name="password" type="password" required />
      <input name="first_name" required />
      <input name="last_name" required />
      
      {/* Cloudflare Turnstile Widget */}
      <div 
        className="cf-turnstile" 
        data-sitekey={process.env.NEXT_PUBLIC_TURNSTILE_SITEKEY}
        data-theme="light"
      ></div>
      
      <button type="submit">Register</button>
    </form>
  );
}
```

### Plain HTML Example

```html
<!DOCTYPE html>
<html>
<head>
  <script src="https://challenges.cloudflare.com/turnstile/v0/api.js" async defer></script>
</head>
<body>
  <form id="registerForm">
    <input name="username" placeholder="Username" required />
    <input name="email" type="email" placeholder="Email" required />
    <input name="password" type="password" placeholder="Password" required />
    
    <!-- Turnstile Widget -->
    <div class="cf-turnstile" data-sitekey="YOUR_SITE_KEY"></div>
    
    <button type="submit">Register</button>
  </form>

  <script>
    document.getElementById('registerForm').addEventListener('submit', async (e) => {
      e.preventDefault();
      const formData = new FormData(e.target);
      
      const data = {
        username: formData.get('username'),
        email: formData.get('email'),
        password: formData.get('password'),
        turnstile: formData.get('cf-turnstile-response')
      };

      const response = await fetch('http://localhost:8000/api/users/register/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data)
      });

      if (response.ok) {
        alert('Registration successful!');
      } else {
        const error = await response.json();
        alert('Error: ' + JSON.stringify(error));
      }
    });
  </script>
</body>
</html>
```

## Test Mode

Khi `TURNSTILE_TEST_MODE=True`, Turnstile sẽ **KHÔNG verify** token - hữu ích cho development.

**Test mode enabled:**
- Có thể gửi bất kỳ giá trị nào cho field `turnstile`
- Hoặc skip validation hoàn toàn

**Production:** Set `TURNSTILE_TEST_MODE=False` để bắt buộc verify.

## Error Handling

**Invalid/Missing CAPTCHA:**
```json
{
  "turnstile": ["This field is required."]
}
```

**Verification Failed:**
```json
{
  "turnstile": ["Invalid CAPTCHA token."]
}
```

## Benefits

✅ **Bot Protection** - Ngăn chặn automated registration/payment spam  
✅ **User-friendly** - Không cần giải puzzle phức tạp như reCAPTCHA  
✅ **Privacy-focused** - Cloudflare không track user data  
✅ **Free tier available** - 1M requests/month miễn phí  
✅ **Fast** - Lightweight và không ảnh hưởng UX  

## Rate Limiting Combination

Turnstile hoạt động cùng với rate limiting hiện có:

- **Register:** 5 requests/hour + CAPTCHA
- **Payment:** 20 requests/hour + CAPTCHA
- **Review:** 10 reviews/day (không cần CAPTCHA vì đã có authentication)

Kết hợp cả 2 tạo lớp bảo vệ đa tầng!
