import subprocess
import json

# Exécuter la commande Docker pour lister les collections
def main():
    cmd = "docker exec backend_chat-mongodb-1 mongosh --quiet --eval 'db.getMongo().getDBs().databases.forEach(function(d) { print(d.name); print(\"---\"); db = db.getSiblingDB(d.name); db.getCollectionNames().forEach(function(c) { print(\"  \" + c); }); print(\"\"); })'"
    
    try:
        output = subprocess.check_output(cmd, shell=True, text=True)
        print("Collections MongoDB:")
        print(output)
    except subprocess.CalledProcessError as e:
        print(f"Erreur: {e}")

if __name__ == "__main__":
    main() 