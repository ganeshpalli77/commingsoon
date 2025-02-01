from flask import Flask, request, jsonify, render_template, send_from_directory
import json
import os
import re
from datetime import datetime
from flask_cors import CORS
from typing import Dict, List, Optional
import hashlib
import logging
from dataclasses import dataclass, asdict
from email_validator import validate_email, EmailNotValidError

@dataclass
class Subscriber:
    email: str
    joined_date: str
    status: str  # active, unsubscribed, bounced
    verification_token: str
    verified: bool
    last_updated: str
    metadata: Dict

app = Flask(__name__, static_folder='static')
CORS(app)

EMAILS_FILE = "subscribers.json"
logging.basicConfig(level=logging.INFO)

class SubscriberManager:
    def __init__(self, storage_file: str):
        self.storage_file = storage_file
        self.subscribers: Dict[str, Subscriber] = {}
        self.load_subscribers()

    def load_subscribers(self) -> None:
        try:
            if os.path.exists(self.storage_file):
                with open(self.storage_file, "r") as file:
                    data = json.load(file)
                    self.subscribers = {
                        email: Subscriber(**sub_data)
                        for email, sub_data in data.items()
                    }
        except Exception as e:
            logging.error(f"Error loading subscribers: {str(e)}")
            self.subscribers = {}

    def save_subscribers(self) -> None:
        try:
            data = {
                email: asdict(subscriber)
                for email, subscriber in self.subscribers.items()
            }
            with open(self.storage_file, "w") as file:
                json.dump(data, file, indent=4)
        except Exception as e:
            logging.error(f"Error saving subscribers: {str(e)}")

    def add_subscriber(self, email: str, metadata: Optional[Dict] = None) -> Dict:
        try:
            # Validate email
            valid = validate_email(email)
            email = valid.email
        except EmailNotValidError as e:
            return {"error": str(e)}, 400

        # Check if email exists
        if email.lower() in self.subscribers:
            return {"error": "Email already exists"}, 409

        # Create verification token
        verification_token = hashlib.sha256(
            f"{email}{datetime.now().isoformat()}".encode()
        ).hexdigest()

        subscriber = Subscriber(
            email=email.lower(),
            joined_date=datetime.now().isoformat(),
            status="pending",
            verification_token=verification_token,
            verified=False,
            last_updated=datetime.now().isoformat(),
            metadata=metadata or {}
        )

        self.subscribers[email.lower()] = subscriber
        self.save_subscribers()
        return {"message": "Subscriber added successfully"}, 201

    def verify_subscriber(self, token: str) -> Dict:
        for email, subscriber in self.subscribers.items():
            if subscriber.verification_token == token:
                subscriber.verified = True
                subscriber.status = "active"
                subscriber.last_updated = datetime.now().isoformat()
                self.save_subscribers()
                return {"message": "Email verified successfully"}, 200
        return {"error": "Invalid verification token"}, 400

    def get_subscriber_stats(self) -> Dict:
        total = len(self.subscribers)
        active = sum(1 for s in self.subscribers.values() if s.status == "active")
        unverified = sum(1 for s in self.subscribers.values() if not s.verified)
        return {
            "total": total,
            "active": active,
            "unverified": unverified,
            "last_updated": datetime.now().isoformat()
        }

subscriber_manager = SubscriberManager(EMAILS_FILE)

@app.route("/subscribe", methods=["POST"])
def subscribe():
    data = request.get_json()
    email = data.get("email", "").strip()
    metadata = data.get("metadata", {})
    
    response, status_code = subscriber_manager.add_subscriber(email, metadata)
    return jsonify(response), status_code

@app.route("/verify/<token>")
def verify_email(token):
    response, status_code = subscriber_manager.verify_subscriber(token)
    return jsonify(response), status_code

@app.route("/subscribers/stats")
def get_stats():
    return jsonify(subscriber_manager.get_subscriber_stats())

# Original routes remain unchanged
@app.route("/")
def home():
    return render_template("project2.html")

@app.route('/static/<path:filename>')
def serve_static(filename):
    return send_from_directory(app.static_folder, filename)

if __name__ == "__main__":
    app.run(debug=True)