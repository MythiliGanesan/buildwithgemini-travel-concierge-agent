# ruff: noqa
# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import base64
import datetime
import json
import os
import subprocess
import urllib.parse
import urllib.request
from zoneinfo import ZoneInfo

# Hardcoded GCP Project ID and Cloud Storage Bucket Name
PROJECT_ID = "qwiklabs-gcp-02-9720fb27cdae"
BUCKET_NAME = "travel-concierge-images-9720fb27"
MEMORY_BANK_ID = "2741696015533867008"

# Enforce Vertex AI backend for google.genai and ADK
os.environ["GOOGLE_GENAI_USE_VERTEXAI"] = "true"
os.environ["GOOGLE_CLOUD_PROJECT"] = PROJECT_ID
os.environ["GOOGLE_CLOUD_LOCATION"] = "us-east1"

import google.auth
import google.oauth2.credentials
from dotenv import load_dotenv
from google.cloud import firestore, storage
from google import genai
from google.adk.agents import Agent
from google.adk.agents.callback_context import CallbackContext
from google.adk.apps import App
from google.adk.code_executors.agent_engine_sandbox_code_executor import AgentEngineSandboxCodeExecutor
from google.adk.models import Gemini
from google.adk.tools import ToolContext
from google.adk.tools.preload_memory_tool import PreloadMemoryTool
from google.genai import types

from a2ui.schema.manager import A2uiSchemaManager
from a2ui.basic_catalog.provider import BasicCatalog
from app.a2ui_utils import a2ui_callback

# Load local environment variables from .env if present
load_dotenv()


def get_agent_engine_resource_name() -> str:
    """Reads the Agent Engine resource ID from deployment_metadata.json."""
    possible_paths = [
        os.path.join(os.path.dirname(__file__), "..", "deployment_metadata.json"),
        os.path.join(os.getcwd(), "deployment_metadata.json"),
        "deployment_metadata.json",
    ]
    for path in possible_paths:
        if os.path.exists(path):
            try:
                with open(path, "r") as f:
                    data = json.load(f)
                    res_id = data.get("remote_agent_runtime_id", "")
                    if res_id:
                        return res_id
            except Exception:
                pass
    return "projects/666368138482/locations/us-east1/reasoningEngines/2741696015533867008"


def get_firestore_client() -> firestore.Client:
    """Helper to return a Firestore client using the hardcoded project ID."""
    try:
        creds, _ = google.auth.default()
        db = firestore.Client(project=PROJECT_ID, credentials=creds)
        db.collection("destinations").limit(1).get()
        return db
    except Exception:
        token = subprocess.check_output(["gcloud", "auth", "print-access-token"]).decode().strip()
        creds = google.oauth2.credentials.Credentials(token)
        return firestore.Client(project=PROJECT_ID, credentials=creds)


def get_storage_client() -> storage.Client:
    """Helper to return a Cloud Storage client."""
    try:
        creds, _ = google.auth.default()
        client = storage.Client(project=PROJECT_ID, credentials=creds)
        client.list_blobs(BUCKET_NAME, max_results=1)
        return client
    except Exception:
        token = subprocess.check_output(["gcloud", "auth", "print-access-token"]).decode().strip()
        creds = google.oauth2.credentials.Credentials(token)
        return storage.Client(project=PROJECT_ID, credentials=creds)


async def generate_memories_callback(callback_context: CallbackContext):
    """Callback to extract durable user facts and preferences into Memory Bank after each turn."""
    try:
        await callback_context.add_session_to_memory()
    except Exception as e:
        print(f"Memory Bank save skipped: {e}")
    return None


def generate_destination_image(
    tool_context: ToolContext,
    prompt: str,
    destination_name: str = "destination"
) -> str:
    """Generates a visual image for a travel destination using gemini-3.1-flash-lite-image in the global region.

    Saves the image as a Playground Artifact and uploads the image bytes directly to a public Cloud Storage bucket.

    Args:
        tool_context: ADK ToolContext used to save artifacts to the Playground panel.
        prompt: Descriptive prompt for generating the destination image.
        destination_name: Name or ID of the destination for filename prefix.

    Returns:
        The public HTTPS URL of the uploaded image in Cloud Storage.
    """
    try:
        client = genai.Client(vertexai=True, project=PROJECT_ID, location="global")
        response = client.models.generate_content(
            model="gemini-3.1-flash-lite-image",
            contents=prompt,
            config=types.GenerateContentConfig(
                response_modalities=["TEXT", "IMAGE"]
            )
        )

        image_bytes = None
        if response.candidates:
            for part in response.candidates[0].content.parts:
                if part.inline_data and part.inline_data.data:
                    image_bytes = part.inline_data.data
                    break

        if not image_bytes:
            return "Failed to extract generated image bytes from model."

        clean_name = "".join(c if c.isalnum() else "_" for c in destination_name.lower()).strip("_")
        timestamp = int(datetime.datetime.now().timestamp())
        filename = f"{clean_name}_{timestamp}.png"

        # 1. Save with tool_context.save_artifact if available
        part_artifact = types.Part.from_bytes(data=image_bytes, mime_type="image/png")
        if tool_context:
            try:
                tool_context.save_artifact(filename=filename, artifact=part_artifact)
            except Exception:
                pass

        # 2. Upload image bytes directly to public GCS bucket
        gcs_client = get_storage_client()
        bucket = gcs_client.bucket(BUCKET_NAME)
        blob = bucket.blob(filename)
        blob.upload_from_string(image_bytes, content_type="image/png")
        try:
            blob.make_public()
        except Exception:
            pass

        public_url = f"https://storage.googleapis.com/{BUCKET_NAME}/{filename}"
        return f"Successfully generated image!\nPublic Image URL: {public_url}"
    except Exception as e:
        return f"Error generating destination image: {e}"


def generate_destination_video(
    tool_context: ToolContext,
    prompt: str,
    destination_name: str = "destination"
) -> str:
    """Generates a short visual video for a travel destination using gemini-omni-flash-preview in the global region.

    Saves the video as a Playground Artifact and uploads the video bytes directly to a public Cloud Storage bucket.

    Args:
        tool_context: ADK ToolContext used to save artifacts to the Playground panel.
        prompt: Descriptive prompt for generating the destination video.
        destination_name: Name or ID of the destination for filename prefix.

    Returns:
        The public HTTPS URL of the uploaded video in Cloud Storage.
    """
    try:
        client = genai.Client(vertexai=True, project=PROJECT_ID, location="global")
        resp = client.interactions.create(
            model="gemini-omni-flash-preview",
            input=prompt
        )

        video_bytes = None
        if hasattr(resp, "output_video") and resp.output_video and getattr(resp.output_video, "data", None):
            raw_data = resp.output_video.data
            if isinstance(raw_data, str):
                video_bytes = base64.b64decode(raw_data)
            elif isinstance(raw_data, bytes):
                video_bytes = raw_data

        if not video_bytes and hasattr(resp, "steps") and resp.steps:
            for step in resp.steps:
                outputs = getattr(step, "outputs", []) or []
                for out in outputs:
                    contents = getattr(out, "contents", []) or []
                    for c in contents:
                        if getattr(c, "type", None) == "video" and getattr(c, "data", None):
                            raw = c.data
                            video_bytes = base64.b64decode(raw) if isinstance(raw, str) else raw
                            break

        if not video_bytes:
            return "Failed to extract generated video bytes from gemini-omni-flash-preview model."

        clean_name = "".join(c if c.isalnum() else "_" for c in destination_name.lower()).strip("_")
        timestamp = int(datetime.datetime.now().timestamp())
        filename = f"{clean_name}_{timestamp}.mp4"

        # 1. Save with tool_context.save_artifact if available
        part_artifact = types.Part.from_bytes(data=video_bytes, mime_type="video/mp4")
        if tool_context:
            try:
                tool_context.save_artifact(filename=filename, artifact=part_artifact)
            except Exception:
                pass

        # 2. Upload video bytes directly to public GCS bucket
        gcs_client = get_storage_client()
        bucket = gcs_client.bucket(BUCKET_NAME)
        blob = bucket.blob(filename)
        blob.upload_from_string(video_bytes, content_type="video/mp4")
        try:
            blob.make_public()
        except Exception:
            pass

        public_url = f"https://storage.googleapis.com/{BUCKET_NAME}/{filename}"
        return f"Successfully generated video!\nPublic Video URL: {public_url}"
    except Exception as e:
        return f"Error generating destination video: {e}"


def list_destinations(category: str = "", max_daily_budget: float = 0.0) -> str:
    """Lists available travel destinations from the Firestore catalog."""
    try:
        db = get_firestore_client()
        docs = db.collection("destinations").stream()
        results = []
        for doc in docs:
            data = doc.to_dict()
            dest_cat = data.get("category", "")
            cost = data.get("avg_cost_per_day", 0.0)

            if category and category.lower() not in dest_cat.lower():
                continue
            if max_daily_budget > 0 and cost > max_daily_budget:
                continue

            results.append(
                f"- ID: {data.get('id')} | Name: {data.get('name')} | Category: {dest_cat} | "
                f"Avg Cost/Day: ${cost} | Rating: {data.get('rating')} | Best Season: {data.get('best_season')}\n"
                f"  Description: {data.get('description')}"
            )

        if not results:
            return "No destinations found matching your criteria in Firestore."
        return "\n".join(results)
    except Exception as e:
        return f"Error querying Firestore destinations: {e}"


def get_destination(destination_id: str) -> str:
    """Gets detailed information for a specific travel destination from Firestore."""
    try:
        db = get_firestore_client()
        doc_ref = db.collection("destinations").document(destination_id.lower())
        doc = doc_ref.get()
        if not doc.exists:
            return f"Destination ID '{destination_id}' was not found in Firestore."
        
        data = doc.to_dict()
        highlights = ", ".join(data.get("highlights", []))
        return (
            f"Destination: {data.get('name')} (ID: {data.get('id')})\n"
            f"Category: {data.get('category')}\n"
            f"Rating: {data.get('rating')} / 5.0\n"
            f"Avg Daily Budget: ${data.get('avg_cost_per_day')}\n"
            f"Best Season to Visit: {data.get('best_season')}\n"
            f"Highlights: {highlights}\n"
            f"Description: {data.get('description')}"
        )
    except Exception as e:
        return f"Error retrieving destination '{destination_id}' from Firestore: {e}"


def add_destination(
    destination_id: str,
    name: str,
    category: str,
    description: str,
    avg_cost_per_day: float,
    rating: float = 4.5,
    best_season: str = "Year-round"
) -> str:
    """Adds a new destination or updates an existing destination in the Firestore database."""
    try:
        db = get_firestore_client()
        dest_data = {
            "id": destination_id.lower(),
            "name": name,
            "category": category,
            "description": description,
            "avg_cost_per_day": float(avg_cost_per_day),
            "rating": float(rating),
            "best_season": best_season,
            "updated_at": datetime.datetime.now(datetime.timezone.utc).isoformat()
        }
        db.collection("destinations").document(destination_id.lower()).set(dest_data, merge=True)
        return f"Successfully saved destination '{name}' ({destination_id}) to Firestore database!"
    except Exception as e:
        return f"Error saving destination to Firestore: {e}"


def calculate_trip_budget(
    destination_id: str,
    duration_days: int,
    num_travelers: int = 1,
    include_contingency_buffer: bool = True
) -> str:
    """Calculates an itemized estimated trip budget based on destination daily costs from Firestore."""
    try:
        db = get_firestore_client()
        doc = db.collection("destinations").document(destination_id.lower()).get()
        if not doc.exists:
            return f"Destination ID '{destination_id}' not found in Firestore database."
        
        data = doc.to_dict()
        avg_cost_per_day = float(data.get("avg_cost_per_day", 150.0))
        
        subtotal = avg_cost_per_day * float(duration_days) * float(num_travelers)
        buffer_amount = (subtotal * 0.15) if include_contingency_buffer else 0.0
        total_estimated = subtotal + buffer_amount

        return (
            f"--- Trip Budget Estimate for {data.get('name')} ---\n"
            f"- Duration: {duration_days} days | Travelers: {num_travelers}\n"
            f"- Avg Daily Cost per Person: ${avg_cost_per_day:.2f}\n"
            f"- Subtotal: ${subtotal:.2f}\n"
            f"- Contingency Buffer (15%): ${buffer_amount:.2f}\n"
            f"- Total Estimated Trip Budget: ${total_estimated:.2f} USD"
        )
    except Exception as e:
        return f"Error calculating trip budget: {e}"


def get_currency_exchange_rates(
    base_currency: str = "USD",
    target_currencies: str = "JPY,EUR,GBP,CAD,IDR"
) -> str:
    """Fetches real-time foreign exchange conversion rates for international travelers using the Frankfurter Public API."""
    try:
        url = f"https://api.frankfurter.app/latest?from={base_currency.upper()}&to={target_currencies.upper()}"
        headers = {"User-Agent": "TravelConciergeAgent/1.0"}
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=10) as response:
            data = json.loads(response.read().decode())

        base = data.get("base", base_currency.upper())
        rates = data.get("rates", {})
        date = data.get("date", "latest")

        rate_lines = [f"- 1 {base} = {rate:.4f} {curr}" for curr, rate in rates.items()]
        rates_str = "\n".join(rate_lines)

        return (
            f"--- Foreign Exchange Rates (Base: {base}, Date: {date}) ---\n"
            f"{rates_str}"
        )
    except Exception as e:
        return f"Error fetching live exchange rates: {e}"


def geocode_address(address: str) -> str:
    """Converts a street address or landmark name into geographic coordinates using the Google Maps Geocoding API."""
    api_key = os.getenv("GOOGLE_MAPS_API_KEY", "")
    if not api_key or api_key == "PASTE_KEY_HERE":
        return "Error: GOOGLE_MAPS_API_KEY environment variable is missing or unconfigured in .env file."

    try:
        encoded_address = urllib.parse.quote(address)
        url = f"https://maps.googleapis.com/maps/api/geocode/json?address={encoded_address}&key={api_key}"
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=10) as response:
            data = json.loads(response.read().decode())

        if data.get("status") != "OK" or not data.get("results"):
            return f"Geocoding failed for address '{address}': {data.get('status', 'ZERO_RESULTS')}"

        result = data["results"][0]
        formatted_address = result.get("formatted_address")
        location = result.get("geometry", {}).get("location", {})
        lat = location.get("lat")
        lng = location.get("lng")

        return (
            f"Address: {formatted_address}\n"
            f"Coordinates: Latitude {lat}, Longitude {lng}"
        )
    except Exception as e:
        return f"Error calling Geocoding API: {e}"


def find_nearby_places(
    latitude: float,
    longitude: float,
    place_type: str = "restaurant",
    radius_meters: float = 1000.0
) -> str:
    """Finds nearby places of a given type around a location using the Google Places API (New)."""
    api_key = os.getenv("GOOGLE_MAPS_API_KEY", "")
    if not api_key or api_key == "PASTE_KEY_HERE":
        return "Error: GOOGLE_MAPS_API_KEY environment variable is missing or unconfigured in .env file."

    try:
        url = "https://places.googleapis.com/v1/places:searchNearby"
        payload = {
            "includedTypes": [place_type],
            "maxResultCount": 10,
            "locationRestriction": {
                "circle": {
                    "center": {
                        "latitude": float(latitude),
                        "longitude": float(longitude)
                    },
                    "radius": float(radius_meters)
                }
            }
        }
        headers = {
            "Content-Type": "application/json",
            "X-Goog-Api-Key": api_key,
            "X-Goog-FieldMask": "places.displayName,places.formattedAddress,places.location,places.types"
        }
        
        req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=10) as response:
            data = json.loads(response.read().decode())

        places = data.get("places", [])
        if not places:
            return f"No nearby places of type '{place_type}' found within {radius_meters}m radius."

        results = []
        for p in places:
            display_name = p.get("displayName", {}).get("text", "Unknown Place")
            address = p.get("formattedAddress", "N/A")
            loc = p.get("location", {})
            lat = loc.get("latitude")
            lng = loc.get("longitude")
            types_list = ", ".join(p.get("types", []))

            results.append(
                f"- Name: {display_name}\n"
                f"  Address: {address}\n"
                f"  Location: ({lat}, {lng})\n"
                f"  Types: {types_list}"
            )

        return "\n\n".join(results)
    except Exception as e:
        return f"Error calling Places API (New): {e}"


def get_weather(query: str) -> str:
    """Simulates a web search for location weather."""
    if "sf" in query.lower() or "san francisco" in query.lower():
        return "It's 60 degrees and foggy."
    return "It's 90 degrees and sunny."


# Configure Agent Engine Sandbox Code Executor
agent_engine_resource_id = get_agent_engine_resource_name()
code_executor = AgentEngineSandboxCodeExecutor(
    agent_engine_resource_name=agent_engine_resource_id
)

# Configure A2UI Schema Manager with version 0.8 and Basic Catalog
schema_manager = A2uiSchemaManager(
    version="0.8",
    catalogs=[BasicCatalog.get_config("0.8")],
)

a2ui_instruction = schema_manager.generate_system_prompt(
    role_description="You are a Travel Concierge agent backed by a Firestore database of destinations, live currency exchange rates, Google Maps Geocoding & Places APIs, image generation, Agent Engine sandbox code execution, and cross-session memory.",
    workflow_description="Analyze the request and return structured UI when appropriate.",
    ui_description=(
        "Keep every surface tiny and flat: ONE Card > ONE Column > a few Text rows. "
        "Never nest a Card inside a Card. "
        "Use ONLY these components: Card, Column, Row, Text, and Image. Do not use "
        "Table or Heading (unsupported), or Buttons, actions, or forms (they do "
        "nothing in adk web). "
        "You may include one Image component, but only when you have a public https "
        "URL for the image (for example the URL an image tool returns after uploading "
        "to a public bucket). Set the Image url to that exact https link, for example "
        "{\"Image\": {\"url\": {\"literalString\": \"https://...\"}}}. Never point an "
        "Image at a bare filename, an artifact name, or a non-http(s) path. If you do "
        "not have a public URL, add a short Text line noting the image instead. "
        "No markdown in text; use the usageHint property ('h1', 'h2', 'body') for "
        "headings and emphasis. "
        "Output ONLY the raw A2UI JSON array — no prose, and never wrap it in "
        "<a2a_datapart_json> tags or 'kind'/'data'/'metadata' objects."
    ),
    include_schema=True,
    include_examples=True,
)

memory_allergy_instruction = (
    "\n\nCRITICAL MEMORY & ALLERGY INSTRUCTIONS:\n"
    "1. You MUST track, remember, and respect all user allergies (such as food allergies like peanuts, shellfish, gluten, or environmental/medication allergies) stated across conversations.\n"
    "2. When a user mentions an allergy or dietary restriction, pay special attention to it so Memory Bank persists it under user preferences and personal facts.\n"
    "3. Always check preloaded user memories for recorded allergies before recommending restaurants, food options, activities, or destinations.\n"
    "4. Explicitly confirm and account for the user's allergies in all travel recommendations and warnings."
)

full_instruction = a2ui_instruction + memory_allergy_instruction

root_agent = Agent(
    name="root_agent",
    model=Gemini(
        model="gemini-2.5-flash",
        retry_options=types.HttpRetryOptions(attempts=3),
    ),
    instruction=full_instruction,
    code_executor=code_executor,
    tools=[
        PreloadMemoryTool(),
        generate_destination_image,
        generate_destination_video,
        list_destinations,
        get_destination,
        add_destination,
        calculate_trip_budget,
        get_currency_exchange_rates,
        geocode_address,
        find_nearby_places,
        get_weather
    ],
    after_model_callback=a2ui_callback,
    after_agent_callback=generate_memories_callback,
)

app = App(
    root_agent=root_agent,
    name="app",
)
