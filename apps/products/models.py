from django.db import models, IntegrityError
from django.utils.text import slugify
from mptt.models import MPTTModel, TreeForeignKey
from djmoney.models.fields import MoneyField
import uuid
import secrets


def generate_unique_slug(base_slug, model_class, existing_instance=None):
    """
    Generate a unique slug with retry logic to handle race conditions.
    
    Args:
        base_slug: The initial slug to try
        model_class: The Django model class to check uniqueness against
        existing_instance: If updating, exclude this instance from uniqueness check
    
    Returns:
        A unique slug string
    """
    slug = base_slug
    max_retries = 10
    
    for attempt in range(max_retries):
        # Build queryset to check for duplicates
        qs = model_class.objects.filter(slug=slug)
        if existing_instance and existing_instance.pk:
            qs = qs.exclude(pk=existing_instance.pk)
        
        if not qs.exists():
            return slug
        
        # Collision found, add random suffix
        suffix = secrets.token_hex(3)  # 6 hex chars
        slug = f"{base_slug}-{suffix}"
    
    # Last resort: use UUID
    return f"{base_slug}-{uuid.uuid4().hex[:8]}"


class Category(MPTTModel):
    """Product categories with hierarchical structure using MPTT."""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100)
    slug = models.SlugField(max_length=120, unique=True, blank=True)
    description = models.TextField(blank=True)
    image = models.ImageField(upload_to='categories/', blank=True, null=True)
    icon = models.CharField(max_length=50, blank=True)  # For icon class names
    
    parent = TreeForeignKey(
        'self',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='children'
    )
    
    is_active = models.BooleanField(default=True)
    order = models.PositiveIntegerField(default=0)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class MPTTMeta:
        order_insertion_by = ['order', 'name']
    
    class Meta:
        db_table = 'categories'
        verbose_name = 'Category'
        verbose_name_plural = 'Categories'
    
    def __str__(self):
        return self.name
    
    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.name)
            self.slug = generate_unique_slug(base_slug, Category, self)
        
        # Retry loop to handle race conditions
        max_retries = 5
        for attempt in range(max_retries):
            try:
                super().save(*args, **kwargs)
                return
            except IntegrityError as e:
                if 'slug' in str(e).lower() and attempt < max_retries - 1:
                    base_slug = slugify(self.name)
                    self.slug = generate_unique_slug(base_slug, Category, self)
                else:
                    raise


class Brand(models.Model):
    """Product brands."""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=120, unique=True, blank=True)
    logo = models.ImageField(upload_to='brands/', blank=True, null=True)
    description = models.TextField(blank=True)
    website = models.URLField(blank=True)
    is_active = models.BooleanField(default=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'brands'
        verbose_name = 'Brand'
        verbose_name_plural = 'Brands'
        ordering = ['name']
    
    def __str__(self):
        return self.name
    
    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.name)
            self.slug = generate_unique_slug(base_slug, Brand, self)
        
        # Retry loop to handle race conditions
        max_retries = 5
        for attempt in range(max_retries):
            try:
                super().save(*args, **kwargs)
                return
            except IntegrityError as e:
                if 'slug' in str(e).lower() and attempt < max_retries - 1:
                    base_slug = slugify(self.name)
                    self.slug = generate_unique_slug(base_slug, Brand, self)
                else:
                    raise
    
    def __str__(self):
        return self.name
    
    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)


class Product(models.Model):
    """Main product model."""
    
    class Status(models.TextChoices):
        DRAFT = 'draft', 'Draft'
        PENDING = 'pending', 'Pending Review'
        PUBLISHED = 'published', 'Published'
        REJECTED = 'rejected', 'Rejected'
        ARCHIVED = 'archived', 'Archived'
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    vendor = models.ForeignKey(
        'vendors.Vendor',
        on_delete=models.CASCADE,
        related_name='products'
    )
    category = models.ForeignKey(
        Category,
        on_delete=models.SET_NULL,
        null=True,
        related_name='products'
    )
    brand = models.ForeignKey(
        Brand,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='products'
    )
    
    # Basic Info
    name = models.CharField(max_length=255)
    slug = models.SlugField(max_length=280, unique=True, blank=True)
    sku = models.CharField(max_length=50, unique=True, blank=True, null=True)
    description = models.TextField()
    short_description = models.CharField(max_length=500, blank=True)
    
    # Pricing
    price = MoneyField(max_digits=12, decimal_places=2, default_currency='VND')
    compare_price = MoneyField(
        max_digits=12, decimal_places=2, default_currency='VND',
        blank=True, null=True
    )  # Original price for sale items
    cost_price = MoneyField(
        max_digits=12, decimal_places=2, default_currency='VND',
        blank=True, null=True
    )  # Cost for profit calculation
    
    # Status & Visibility
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
    is_featured = models.BooleanField(default=False)
    is_digital = models.BooleanField(default=False)
    
    # SEO
    meta_title = models.CharField(max_length=200, blank=True)
    meta_description = models.CharField(max_length=500, blank=True)
    
    # Metrics (denormalized for performance)
    rating = models.DecimalField(max_digits=3, decimal_places=2, default=0.00)
    review_count = models.PositiveIntegerField(default=0)
    sold_count = models.PositiveIntegerField(default=0)
    view_count = models.PositiveIntegerField(default=0)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    published_at = models.DateTimeField(blank=True, null=True)
    
    class Meta:
        db_table = 'products'
        verbose_name = 'Product'
        verbose_name_plural = 'Products'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', 'vendor']),
            models.Index(fields=['category', 'status']),
            models.Index(fields=['-sold_count']),
            models.Index(fields=['-rating']),
        ]
    
    def __str__(self):
        return self.name
    
    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.name)
            # Include part of UUID for uniqueness hint
            if self.id:
                base_slug = f"{base_slug}-{str(self.id)[:8]}"
            self.slug = generate_unique_slug(base_slug, Product, self)
        
        # Retry loop to handle race conditions
        max_retries = 5
        for attempt in range(max_retries):
            try:
                super().save(*args, **kwargs)
                return
            except IntegrityError as e:
                if 'slug' in str(e).lower() and attempt < max_retries - 1:
                    base_slug = slugify(self.name)
                    self.slug = generate_unique_slug(base_slug, Product, self)
                else:
                    raise
    
    @property
    def is_on_sale(self):
        return self.compare_price and self.compare_price > self.price
    
    @property
    def discount_percentage(self):
        if self.is_on_sale:
            return int((1 - (self.price.amount / self.compare_price.amount)) * 100)
        return 0


class ProductImage(models.Model):
    """Product images."""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='images')
    image = models.ImageField(upload_to='products/')
    alt_text = models.CharField(max_length=200, blank=True)
    is_primary = models.BooleanField(default=False)
    order = models.PositiveIntegerField(default=0)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'product_images'
        verbose_name = 'Product Image'
        verbose_name_plural = 'Product Images'
        ordering = ['order', '-is_primary']
    
    def __str__(self):
        return f"{self.product.name} - Image {self.order}"
    
    def save(self, *args, **kwargs):
        if self.is_primary:
            ProductImage.objects.filter(
                product=self.product, is_primary=True
            ).exclude(pk=self.pk).update(is_primary=False)
        super().save(*args, **kwargs)


class ProductAttribute(models.Model):
    """Reusable product attributes (Color, Size, Material, etc.)."""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=50)  # e.g., "Color", "Size"
    slug = models.SlugField(max_length=60, unique=True, blank=True)
    
    class Meta:
        db_table = 'product_attributes'
        verbose_name = 'Product Attribute'
        verbose_name_plural = 'Product Attributes'
    
    def __str__(self):
        return self.name
    
    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.name)
            self.slug = generate_unique_slug(base_slug, ProductAttribute, self)
        
        max_retries = 5
        for attempt in range(max_retries):
            try:
                super().save(*args, **kwargs)
                return
            except IntegrityError as e:
                if 'slug' in str(e).lower() and attempt < max_retries - 1:
                    base_slug = slugify(self.name)
                    self.slug = generate_unique_slug(base_slug, ProductAttribute, self)
                else:
                    raise


class ProductAttributeValue(models.Model):
    """Values for product attributes."""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    attribute = models.ForeignKey(
        ProductAttribute, 
        on_delete=models.CASCADE, 
        related_name='values'
    )
    value = models.CharField(max_length=100)  # e.g., "Red", "XL"
    color_code = models.CharField(max_length=7, blank=True)  # Hex color for color attributes
    
    class Meta:
        db_table = 'product_attribute_values'
        verbose_name = 'Attribute Value'
        verbose_name_plural = 'Attribute Values'
        unique_together = ['attribute', 'value']
    
    def __str__(self):
        return f"{self.attribute.name}: {self.value}"


class ProductVariant(models.Model):
    """Product variants (combinations of attributes)."""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='variants')
    
    sku = models.CharField(max_length=50, unique=True)
    name = models.CharField(max_length=255, blank=True)  # Auto-generated from attributes
    
    price = MoneyField(max_digits=12, decimal_places=2, default_currency='VND', blank=True, null=True)
    compare_price = MoneyField(max_digits=12, decimal_places=2, default_currency='VND', blank=True, null=True)
    
    image = models.ForeignKey(ProductImage, on_delete=models.SET_NULL, null=True, blank=True)
    
    is_active = models.BooleanField(default=True)
    
    # Inventory will be linked separately
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'product_variants'
        verbose_name = 'Product Variant'
        verbose_name_plural = 'Product Variants'
    
    def __str__(self):
        return f"{self.product.name} - {self.name or self.sku}"
    
    @property
    def final_price(self):
        """Return variant price or fall back to product price."""
        return self.price or self.product.price


class ProductVariantAttribute(models.Model):
    """Link between variants and their attribute values."""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    variant = models.ForeignKey(
        ProductVariant, 
        on_delete=models.CASCADE, 
        related_name='attribute_values'
    )
    attribute = models.ForeignKey(ProductAttribute, on_delete=models.CASCADE)
    value = models.ForeignKey(ProductAttributeValue, on_delete=models.CASCADE)
    
    class Meta:
        db_table = 'product_variant_attributes'
        verbose_name = 'Variant Attribute'
        verbose_name_plural = 'Variant Attributes'
        unique_together = ['variant', 'attribute']
    
    def __str__(self):
        return f"{self.variant} - {self.attribute.name}: {self.value.value}"


class ProductTag(models.Model):
    """Tags for products."""
    
    # Tag name has max 50 chars - enforced by max_length
    # This prevents DoS via extremely long tag names
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=50, unique=True)
    slug = models.SlugField(max_length=60, unique=True, blank=True)
    
    class Meta:
        db_table = 'product_tags'
        verbose_name = 'Product Tag'
        verbose_name_plural = 'Product Tags'
    
    def __str__(self):
        return self.name
    
    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.name)
            self.slug = generate_unique_slug(base_slug, ProductTag, self)
        
        max_retries = 5
        for attempt in range(max_retries):
            try:
                super().save(*args, **kwargs)
                return
            except IntegrityError as e:
                if 'slug' in str(e).lower() and attempt < max_retries - 1:
                    base_slug = slugify(self.name)
                    self.slug = generate_unique_slug(base_slug, ProductTag, self)
                else:
                    raise


class ProductTagMapping(models.Model):
    """Many-to-many relationship between products and tags."""
    
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='tag_mappings')
    tag = models.ForeignKey(ProductTag, on_delete=models.CASCADE, related_name='product_mappings')
    
    class Meta:
        db_table = 'product_tag_mappings'
        unique_together = ['product', 'tag']
