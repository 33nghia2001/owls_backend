"""
Management command to update search vectors for all products.

Usage:
    python manage.py update_search_vectors
    python manage.py update_search_vectors --batch-size=500

This command should be run:
1. After initial deployment to populate search vectors
2. Periodically via cron/celery if search_vector auto-update is not enabled
3. After bulk product imports

For production, consider running this during off-peak hours.
"""
from django.core.management.base import BaseCommand
from django.contrib.postgres.search import SearchVector
from django.db import connection, transaction
from apps.products.models import Product


class Command(BaseCommand):
    help = 'Update PostgreSQL search vectors for all products'

    def add_arguments(self, parser):
        parser.add_argument(
            '--batch-size',
            type=int,
            default=1000,
            help='Number of products to update per batch (default: 1000)'
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Force update all products, even if search_vector is already set'
        )

    def handle(self, *args, **options):
        batch_size = options['batch_size']
        force = options['force']
        
        # Count products to update
        if force:
            queryset = Product.objects.all()
        else:
            queryset = Product.objects.filter(search_vector__isnull=True)
        
        total = queryset.count()
        
        if total == 0:
            self.stdout.write(self.style.SUCCESS('No products need search vector updates.'))
            return
        
        self.stdout.write(f'Updating search vectors for {total} products...')
        
        # Method 1: Use raw SQL for best performance
        # This is MUCH faster than Django ORM for bulk updates
        try:
            self._update_via_sql(force)
            self.stdout.write(self.style.SUCCESS(f'Successfully updated {total} product search vectors.'))
            return
        except Exception as e:
            self.stdout.write(self.style.WARNING(f'SQL method failed: {e}. Falling back to ORM...'))
        
        # Method 2: Fallback to Django ORM (slower but more compatible)
        updated = 0
        
        search_vector = SearchVector('name', weight='A', config='simple') + \
                       SearchVector('description', weight='B', config='simple') + \
                       SearchVector('sku', weight='A', config='simple')
        
        for start in range(0, total, batch_size):
            with transaction.atomic():
                batch = queryset.order_by('id')[start:start + batch_size]
                batch_ids = list(batch.values_list('id', flat=True))
                
                Product.objects.filter(id__in=batch_ids).update(
                    search_vector=search_vector
                )
                
                updated += len(batch_ids)
                self.stdout.write(f'  Updated {updated}/{total} products...')
        
        self.stdout.write(self.style.SUCCESS(f'Successfully updated {updated} product search vectors.'))

    def _update_via_sql(self, force=False):
        """
        Update search vectors using raw SQL for maximum performance.
        Uses PostgreSQL's to_tsvector directly.
        """
        where_clause = "" if force else "WHERE search_vector IS NULL"
        
        sql = f"""
            UPDATE products
            SET search_vector = 
                setweight(to_tsvector('simple', coalesce(name, '')), 'A') ||
                setweight(to_tsvector('simple', coalesce(description, '')), 'B') ||
                setweight(to_tsvector('simple', coalesce(sku, '')), 'A')
            {where_clause}
        """
        
        with connection.cursor() as cursor:
            cursor.execute(sql)
