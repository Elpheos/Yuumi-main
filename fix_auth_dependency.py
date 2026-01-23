import sqlite3

# Connexion à ta base
conn = sqlite3.connect("db.sqlite3")
c = conn.cursor()

# Supprimer la migration auth.0013_user_favoris si elle dépend d'une migration members qui n'existe plus
c.execute("""
DELETE FROM django_migrations
WHERE app='auth' AND name='0013_user_favoris';
""")

conn.commit()
conn.close()

print("Migration auth.0013_user_favoris supprimée de la table django_migrations !")
