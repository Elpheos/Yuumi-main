from django.db import migrations, models

class Migration(migrations.Migration):

    dependencies = [
        ('members', '0014_store_galerie_description_store_galerie_image_and_more'),  # remplace par la dernière migration appliquée
    ]

    operations = [
        migrations.AddField(
            model_name='store',
            name='super_categorie',
            field=models.CharField(
                max_length=50,
                choices=[
                    ('alimentation', 'Alimentation'),
                    ('restauration', 'Restauration'),
                    ('autres', 'Autres catégories'),
                ],
                default='autres',
            ),
        ),
    ]
