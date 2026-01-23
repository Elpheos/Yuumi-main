# Yuumi Django Project - AI Coding Guidelines

## Architecture Overview
Yuumi is a Django web application for local store discovery. Core components:
- **Single App Structure**: All business logic in `members/` app (models, views, forms, templates)
- **URL Hierarchy**: `/<departement>/<ville>/<store-slug>/` for store details
- **Data Flow**: Stores → ProductFamilies → Products (nested inline formsets)

## Key Patterns & Conventions

### Model Relationships
- Use `OneToOneField` for store ownership: `owner = models.OneToOneField(User, related_name="store")`
- Many-to-many favorites: `User.add_to_class("favoris", models.ManyToManyField(Store))`
- Inline formsets for hierarchical data: `FamilyFormSet` manages `ProductFamily` + `ProductFormSet`

### URL & View Patterns
- Department/city filtering: `Store.objects.filter(departement__iexact=departement, ville__iexact=ville)`
- Slug-based lookups: `get_object_or_404(Store, slug=slug, departement=departement, ville=ville)`
- AJAX endpoints return `JsonResponse` (e.g., `search_product`, `toggle_favoris`)

### Form Handling
- Autocomplete with `django-autocomplete-light`: Forwarded fields for chained selects (departement → ville)
- Inline formsets: `prefix=f"products_{family.id}"` for dynamic form management
- File uploads: `request.FILES` in `StoreForm` for photo handling

### Context Processors
- `menu_context`: Provides `menu_supercategories` dict with categorized store data
- Dynamic menu building based on current URL path parsing

### Geocoding Integration
- Automatic geocoding on `Store.save()` using `geopy.Nominatim`
- Fallback handling: Wrap in try/except, skip on failure

## Development Workflow
- **Run Server**: `python manage.py runserver` (activate venv first)
- **Database**: SQLite for dev (`db.sqlite3`), PostgreSQL for prod
- **Static Files**: `collectstatic` to `mystaticfiles/`, served via WhiteNoise
- **Migrations**: Standard Django migrations in `members/migrations/`

## Code Style Notes
- French comments and variable names (e.g., `commerces`, `derniers_arrivants`)
- Template inheritance: `{% extends "members/master.html" %}`
- Bootstrap 5 + FontAwesome for frontend
- Email notifications: SMTP via `send_mail()` for store claims

## Common Patterns
- Permission checks: `if request.user != store.owner and not request.user.is_superuser: raise PermissionDenied`
- Random selection: `choice(list(commerces_with_photo))` for featured images
- Case-insensitive filtering: `__iexact` for department/city matching
- Slug generation: `slugify()` in model `save()` method

Reference: `members/models.py`, `members/views.py`, `members/forms.py` exemplify core patterns.</content>
<parameter name="filePath">c:\Users\User\Documents\Yuumi-main\Yuumi-main-main\.github\copilot-instructions.md