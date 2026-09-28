import os
import subprocess
import google.auth
import google.oauth2.credentials
from google.cloud import firestore

PROJECT_ID = "qwiklabs-gcp-02-9720fb27cdae"

def get_firestore_client():
    try:
        creds, _ = google.auth.default()
        db = firestore.Client(project=PROJECT_ID, credentials=creds)
        # Test connection
        db.collection("test").limit(1).get()
        return db
    except Exception:
        # Fallback to gcloud access token for local development
        token = subprocess.check_output(["gcloud", "auth", "print-access-token"]).decode().strip()
        creds = google.oauth2.credentials.Credentials(token)
        return firestore.Client(project=PROJECT_ID, credentials=creds)

def seed_firestore():
    print(f"Connecting to Firestore for project '{PROJECT_ID}'...")
    db = get_firestore_client()
    
    destinations = [
        {
            "id": "kyoto",
            "name": "Kyoto, Japan",
            "category": "Historical & Temples",
            "description": "Ancient capital of Japan known for classical Buddhist temples, gardens, imperial palaces, and wooden houses.",
            "avg_cost_per_day": 180.0,
            "rating": 4.9,
            "highlights": ["Fushimi Inari Shrine", "Arashiyama Bamboo Grove", "Kinkaku-ji"],
            "best_season": "Autumn / Spring"
        },
        {
            "id": "paris",
            "name": "Paris, France",
            "category": "City & Culture",
            "description": "Global center for art, fashion, gastronomy, and culture with iconic landmarks and world-class museums.",
            "avg_cost_per_day": 220.0,
            "rating": 4.7,
            "highlights": ["Eiffel Tower", "Louvre Museum", "Notre-Dame Cathedral"],
            "best_season": "Spring / Fall"
        },
        {
            "id": "bali",
            "name": "Bali, Indonesia",
            "category": "Beach & Nature",
            "description": "Indonesian island known for its forested volcanic mountains, iconic rice paddies, beaches, and coral reefs.",
            "avg_cost_per_day": 95.0,
            "rating": 4.8,
            "highlights": ["Ubud Monkey Forest", "Uluwatu Temple", "Tegallalang Rice Terraces"],
            "best_season": "Dry Season (April - October)"
        },
        {
            "id": "banff",
            "name": "Banff National Park, Canada",
            "category": "Mountain & Adventure",
            "description": "Canada's oldest national park featuring turquoise glacial lakes, majestic Rocky Mountains, and abundant wildlife.",
            "avg_cost_per_day": 160.0,
            "rating": 4.9,
            "highlights": ["Lake Louise", "Moraine Lake", "Banff Gondola"],
            "best_season": "Summer / Winter"
        }
    ]

    collection_ref = db.collection("destinations")
    for dest in destinations:
        doc_ref = collection_ref.document(dest["id"])
        doc_ref.set(dest)
        print(f"Seeded destination: {dest['name']} ({dest['id']})")

    print("Firestore database seeded successfully!")

if __name__ == "__main__":
    seed_firestore()
