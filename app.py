import os
import json
import resend
from dotenv import load_dotenv
from flask import Flask, render_template, request, jsonify, redirect, url_for, session
from groq import Groq

load_dotenv()

# --- FIXED INITIALIZATION ---
# Initialize the app ONCE at the top, pointing to the templates folder
app = Flask(__name__)
# Use a static secret key so Vercel doesn't log you out on every request
app.secret_key = os.getenv("FLASK_SECRET_KEY", "super-secret-fixed-key-12345")

client = Groq(api_key=os.getenv("GROQ_API_KEY"))
resend.api_key = os.getenv("RESEND_API_KEY")

SYSTEM_PROMPT = """
You are an Email Assistant.
Whenever the user wants to write or modify an email, respond ONLY with valid JSON.
Example:
{
  "type":"email",
  "to":"",
  "subject":"Sick Leave Request",
  "body":"Dear Manager,\\n\\nI am feeling sick today..."
}
Do not use markdown formatting like ```json. Just return the raw JSON object.
"""

@app.route("/")
def index():
    if 'email' not in session:
        return redirect(url_for('login'))
    return render_template("index.html", user_name=session['name'], user_email=session['email'])

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        name = request.form.get("name")
        email = request.form.get("email")
        
        if name and email:
            session['name'] = name
            session['email'] = email
            return redirect(url_for('index'))
        else:
            return render_template("login.html", error="Please provide both fields.")
    
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route("/api/chat", methods=["POST"])
def chat():
    if 'email' not in session:
        return jsonify({"status": "error", "message": "Unauthorized"}), 401

    data = request.json
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    messages.extend(data.get("history", []))
    messages.append({"role": "user", "content": data.get("message")})

    try:
        response = client.chat.completions.create(
            model="openai/gpt-oss-120b", 
            messages=messages,
            temperature=0.3,
            response_format={"type": "json_object"}
        )
        return jsonify({"status": "success", "reply": response.choices[0].message.content})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/api/send", methods=["POST"])
def send():
    if 'email' not in session:
        return jsonify({"status": "error", "message": "Unauthorized"}), 401

    data = request.json
    user_name = session['name']
    user_email = session['email']

    try:
        params = {
            # In testing, Resend requires you to send FROM their onboarding domain
            # When you add a real domain to Resend, change this to "Agent Mail <bot@yourdomain.com>"
            "from": "Agent Mail <onboarding@resend.dev>",
            "to": data["to"],
            "subject": data["subject"],
            "text": data["body"],
            # This ensures replies go to your user, not the bot!
            "reply_to": f"{user_name} <{user_email}>"
        }

        email_response = resend.Emails.send(params)
        return jsonify({"status": "success", "message": "Email sent successfully via Resend!"})
        
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500