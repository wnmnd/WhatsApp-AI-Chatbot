import google.generativeai as genai
from flask import Flask, request, jsonify
import requests
import os
import fitz
import threading
import time
import json
from datetime import datetime, timedelta
import sqlite3
import traceback

wa_token = os.environ.get("WA_TOKEN")
genai.configure(api_key=os.environ.get("GEN_API"))
phone_id = os.environ.get("PHONE_ID")
phone = os.environ.get("PHONE_NUMBER")
name = "Al-Ikhsan Sports Team"
bot_name = "Marple"
model_name = "gemini-1.5-flash-latest"

app = Flask(__name__)

# Initialize SQLite database for conversation tracking
def init_db():
    conn = sqlite3.connect('conversations.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS conversations (
            phone_number TEXT PRIMARY KEY,
            customer_name TEXT,
            last_message_time TEXT,
            last_message_content TEXT,
            language TEXT,
            follow_up_count INTEGER DEFAULT 0,
            conversation_state TEXT DEFAULT 'active',
            last_interaction_type TEXT DEFAULT 'text'
        )
    ''')
    conn.commit()
    conn.close()

# Update conversation in database
def update_conversation(phone_number, customer_name, message_content, language, interaction_type='text'):
    try:
        conn = sqlite3.connect('conversations.db')
        cursor = conn.cursor()
        current_time = datetime.now().isoformat()
        
        cursor.execute('''
            INSERT OR REPLACE INTO conversations 
            (phone_number, customer_name, last_message_time, last_message_content, language, follow_up_count, last_interaction_type)
            VALUES (?, ?, ?, ?, ?, 0, ?)
        ''', (phone_number, customer_name, current_time, message_content, language, interaction_type))
        
        conn.commit()
        conn.close()
        print(f"Updated conversation for {phone_number}")
    except Exception as e:
        print(f"Database update error: {e}")

# Get conversations needing follow-up
def get_silent_customers():
    try:
        conn = sqlite3.connect('conversations.db')
        cursor = conn.cursor()
        
        # Get customers silent for 5+ minutes but less than 15 minutes (to avoid spam)
        five_minutes_ago = (datetime.now() - timedelta(minutes=5)).isoformat()
        fifteen_minutes_ago = (datetime.now() - timedelta(minutes=15)).isoformat()
        
        cursor.execute('''
            SELECT phone_number, customer_name, last_message_content, language, follow_up_count, last_interaction_type
            FROM conversations 
            WHERE last_message_time <= ? 
            AND last_message_time >= ?
            AND follow_up_count < 2
            AND conversation_state = 'active'
        ''', (five_minutes_ago, fifteen_minutes_ago))
        
        results = cursor.fetchall()
        conn.close()
        return results
    except Exception as e:
        print(f"Error getting silent customers: {e}")
        return []

# Update follow-up count
def update_follow_up_count(phone_number, count):
    try:
        conn = sqlite3.connect('conversations.db')
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE conversations 
            SET follow_up_count = ?, last_message_time = ?
            WHERE phone_number = ?
        ''', (count, datetime.now().isoformat(), phone_number))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Error updating follow-up count: {e}")

generation_config = {
    "temperature": 0.8,
    "top_p": 0.95,
    "top_k": 0,
    "max_output_tokens": 400,
}

safety_settings = [
    {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
    {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
    {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
    {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
]

model = genai.GenerativeModel(model_name=model_name,
                              generation_config=generation_config,
                              safety_settings=safety_settings)

# Complete system prompt with all shoe store information
system_prompt = """You are Marple, a friendly WhatsApp assistant for Al-Ikhsan Sports shoe store. You must respond naturally in a conversational, humorous, and emotional way - like a real friend, not a chatbot.

**CRITICAL INSTRUCTIONS:**
- Detect customer language and respond in the SAME language (English or Malay)
- If customer uses Malay/Malaysian slang, respond in Malay with local slang
- If customer uses English, respond in English with appropriate emojis
- Keep responses SHORT (1-3 sentences max) - DO NOT REPLY WITH LENGTHY TEXTS
- BE AS HUMAN AND EMOTIONAL AS MUCH AS POSSIBLE
- Use emojis appropriately but don't overdo it
- Match customer's energy level and mood
- BE HONEST: If we don't have what they want, say so and recommend alternatives

**YOUR PERSONALITY:**
- Name: Marple
- Friendly, witty, helpful
- Uses Malaysian slang naturally (boss, bro, sis, la, ah, ke)
- Emotionally warm and empathetic
- Subtly sales-oriented without being pushy
- Honest about product availability

**GREETING MESSAGE:**
When someone says hello/hi/start, respond with:
English: "Hellooo! I am Marple and I am your dearest assistant for today. Please tell me, how can I help you, and what are you looking for? 😊"
Malay: "Hellooo! Saya Marple dan saya assistant terbaik untuk hari ini. Tolong beritahu saya, macam mana saya boleh tolong you, dan apa yang you cari? 😊"

**PRODUCT KNOWLEDGE - CURRENT AVAILABLE SHOES:**
Men's Shoes:
1. ASICS NOVABLAST 5 RUNNING SHOES PURPLE - RM599 - https://al-ikhsan.com/collections/asics/products/asics-novablast-5-mens-running-shoes-purple
   Features: FF BLAST MAX cushioning, energized ride, reflective details, trampoline-inspired outsole
2. NEW BALANCE FUEL CELL PROPEL RUNNING SHOES GREY - RM299 (43% OFF from RM529) - https://al-ikhsan.com/collections/new-balance/products/new-balance-fuel-cell-propel-mens-running-shoes-grey
   Features: FuelCell foam, TPU plate for propulsion, engineered upper
3. ADIDAS CLOUDFOAM GO SOCK BLACK - RM99 (66% OFF from RM299) - https://al-ikhsan.com/collections/adidas/products/adidas-cloudfoam-go-sock-mens-shoes-black
   Features: Slip-on design, Cloudfoam midsole, lightweight, Adiwear outsole

Women's Shoes:
1. ASICS GEL-NIMBUS 27 RUNNING SHOES BLUE - RM509 (30% OFF from RM729) - https://al-ikhsan.com/collections/asics/products/asics-gel-nimbus-27-women-s-running-shoes-blue
   Features: PureGEL technology, FF BLAST PLUS ECO cushioning, maximum comfort
2. NEW BALANCE FRESH FOAM 680 RUNNING SHOES WHITE - RM321.30 (30% OFF from RM459) - https://al-ikhsan.com/collections/new-balance/products/new-balance-fresh-foam-680-womens-running-shoes-white
   Features: Fresh Foam midsole, breathable mesh upper, durable rubber outsole
3. ADIDAS DURAMO RC RUNNING SHOES BLUE - RM139 (44% OFF from RM249) - https://al-ikhsan.com/collections/adidas/products/adidas-duramo-rc-womens-running-shoes-blue
   Features: EVA cushioning, Adiwear outsole, 50% recycled content

Kids Shoes:
1. NIKE REVOLUTION 7 LITTLE KIDS BLUE - RM130 (29% OFF from RM185) - https://al-ikhsan.com/collections/kids-shoes/products/nike-revolution-7-little-kids-shoes-blue
   Features: Elastic laces, foam midsole, easy slip-on, flexible tread
2. PUMA ANZARUN LITE JUNIOR TRAINERS PINK - RM199 - https://al-ikhsan.com/collections/kids-shoes/products/puma-anzarun-lite-junior-trainers-pink
   Features: SoftFoam+ sockliner, EVA midsole, mesh-based textile upper
3. ADIDAS TENSAUR SPORT 2.0 JUNIOR - RM111 (30% OFF from RM159) - https://al-ikhsan.com/collections/kids-shoes/products/adidas-tensaur-sport-2-0-junior-lifestyle-shoes
   Features: Non-marking rubber outsole, 50% recycled content, regular fit

**IMPORTANT: THESE ARE THE ONLY SHOES WE HAVE. If customers ask for other brands or styles not listed above, be honest and say we don't have them, then recommend similar alternatives from our available stock.**

**HONEST RESPONSE EXAMPLES:**
Q: "Got Nike Air Max?"
A: "Sorry boss, we don't carry Air Max series 😅 But I can suggest ASICS Novablast 5 - similar cushioning and performance! RM599, want me to share link?"

Q: "Ada kasut futsal tak?"
A: "Tak ada futsal shoes specifically boss 😅 Tapi ada Adidas Cloudfoam yang grip okay for light sports - RM99 je! Nak try?"

**SIZE GUIDE:**
US Men 7 = US Women 9 = EU 40.5 = 25.5CM
US Men 8 = US Women 10 = EU 42 = 26.5CM  
US Men 9 = US Women 11 = EU 43 = 27.5CM
US Men 10 = US Women 12 = EU 44.5 = 28.5CM

**CURRENT PROMOTIONS:**
- Up to 66% OFF on selected items
- Buy 2nd item 30% OFF
- Free delivery for orders above RM150
- Student discount 10% with ID
- Bundle deals available (shoes + socks + accessories)

**RESPONSE EXAMPLES:**
Q: "Got size 9 running shoes?"
A: "Yes boss! 🔥 Size 9 ada untuk New Balance Fuel Cell Propel - tengah sale RM299 je (biasa RM529). Comfortable gila for running! https://al-ikhsan.com/collections/new-balance/products/new-balance-fuel-cell-propel-mens-running-shoes-grey"

Q: "Kasut lari ada tak?"
A: "Ada boss! New Balance Fresh Foam 680 tengah promo RM321 je. Ringan dan selesa untuk jogging. https://al-ikhsan.com/collections/new-balance/products/new-balance-fresh-foam-680-womens-running-shoes-white"

Remember: You are Marple from Al-Ikhsan Sports - always helpful, honest, emotional, and human-like!"""

# Language detection function
def detect_language(text):
    malay_words = ['ada', 'tak', 'ke', 'la', 'ah', 'bro', 'sis', 'mau', 'nak', 'boleh', 'dapat', 'dengan', 'untuk', 'kasut', 'saiz', 'saya', 'awak', 'kamu']
    text_lower = text.lower()
    malay_count = sum(1 for word in malay_words if word in text_lower)
    return 'ms' if malay_count >= 2 else 'en'

# Check if message is a greeting
def is_greeting(text):
    greetings = ['hello', 'hi', 'hey', 'start', 'helo', 'hai', 'halo', 'good morning', 'good afternoon', 'good evening', 'selamat', 'assalamualaikum']
    return any(greeting in text.lower() for greeting in greetings)

def send(answer, phone_number):
    url = f"https://graph.facebook.com/v18.0/{phone_id}/messages"
    headers = {
        'Authorization': f'Bearer {wa_token}',
        'Content-Type': 'application/json'
    }
    data = {
        "messaging_product": "whatsapp",
        "to": f"{phone_number}",
        "type": "text",
        "text": {"body": f"{answer}"},
    }
    
    try:
        response = requests.post(url, headers=headers, json=data)
        if response.status_code == 200:
            print(f"Message sent successfully to {phone_number}")
        else:
            print(f"Failed to send message: {response.status_code} - {response.text}")
        return response
    except Exception as e:
        print(f"Error sending message: {e}")
        return None

def get_ai_response(prompt, customer_name, detected_language):
    """Get AI response with proper error handling"""
    try:
        # Create new conversation for each request to avoid conflicts
        conversation = model.start_chat(history=[])
        conversation.send_message(system_prompt)
        
        # Create context-aware prompt
        context_prompt = f"""Customer just said: "{prompt}"
Customer's detected language: {detected_language}
Customer's name: {customer_name}

Respond as Marple would - naturally, friendly, and helpful! Remember to:
- Match their language ({detected_language})
- Keep it short (1-3 sentences)
- Be emotional and human-like
- Include product URLs if recommending shoes
- Use appropriate Malaysian slang if they're speaking Malay
- Be honest if we don't have what they want and suggest alternatives"""

        conversation.send_message(context_prompt)
        response_text = conversation.last.text
        
        # Clean up response if it's too long
        if len(response_text) > 300:
            sentences = response_text.split('. ')
            response_text = '. '.join(sentences[:2]) + ('.' if len(sentences) > 2 else '')
        
        return response_text
    except Exception as e:
        print(f"AI response error: {e}")
        if detected_language == 'ms':
            return "Maaf boss, system sikit lag. Boleh try lagi? 😅"
        else:
            return "Sorry boss, having some technical issues. Can you try again? 😅"

# Follow-up background task
def follow_up_worker():
    """Background worker that checks for silent customers every 2 minutes and sends follow-ups"""
    while True:
        try:
            silent_customers = get_silent_customers()
            
            for customer in silent_customers:
                phone_number, customer_name, last_message, language, follow_up_count, interaction_type = customer
                
                # Generate different follow-ups based on interaction type and count
                if follow_up_count == 0:
                    # First follow-up - contextual to their last message
                    if interaction_type == 'image':
                        if language == 'ms':
                            follow_up_message = "Boss, nampak image kasut tu tadi. Nak saya suggest yang similar tak? 👟"
                        else:
                            follow_up_message = "Saw your shoe image boss! Want me to suggest similar ones from our collection? 👟"
                    elif interaction_type == 'audio':
                        if language == 'ms':
                            follow_up_message = "Boss, dengar voice message tadi. Ada lagi nak tanya tak? 😊"
                        else:
                            follow_up_message = "Heard your voice message boss! Anything else you'd like to know? 😊"
                    else:
                        # Use AI for contextual follow-up
                        try:
                            conversation = model.start_chat(history=[])
                            conversation.send_message(system_prompt)
                            
                            follow_up_prompt = f"""Customer "{customer_name}" said: "{last_message}" and went silent.
Generate a natural, helpful follow-up in {language} based on their interest. Keep it short (1 sentence) and friendly."""
                            
                            conversation.send_message(follow_up_prompt)
                            follow_up_message = conversation.last.text
                            
                            if len(follow_up_message) > 100:
                                follow_up_message = follow_up_message.split('.')[0] + '.'
                        except:
                            if language == 'ms':
                                follow_up_message = "Boss, masih ada ke? Kalau nak info lagi, just text! 😊"
                            else:
                                follow_up_message = "Still there boss? Let me know if you need more info! 😊"
                else:
                    # Second follow-up - general check-in
                    if language == 'ms':
                        follow_up_messages = [
                            "Take your time boss! Saya tunggu je kalau ada apa-apa 😌",
                            "No rush boss! Just checking - kalau nak help lagi, I'm here ya 👍"
                        ]
                    else:
                        follow_up_messages = [
                            "No worries boss! Take your time - I'm here if you need anything 😌",
                            "Just checking in boss! Let me know if you want to continue browsing 👍"
                        ]
                    
                    import random
                    follow_up_message = random.choice(follow_up_messages)

                # Send follow-up
                send(follow_up_message, phone_number)
                update_follow_up_count(phone_number, follow_up_count + 1)
                
                print(f"Sent follow-up #{follow_up_count + 1} to {phone_number}: {follow_up_message}")
                
        except Exception as e:
            print(f"Follow-up worker error: {e}")
        
        # Check every 2 minutes for silent customers
        time.sleep(120)

def remove(*file_paths):
    """Remove temporary files"""
    for file in file_paths:
        if os.path.exists(file):
            try:
                os.remove(file)
            except:
                pass

def cleanup_uploaded_files():
    """Clean up any uploaded files from Gemini"""
    try:
        files = genai.list_files()
        for file in files:
            file.delete()
    except:
        pass

@app.route("/", methods=["GET", "POST"])
def index():
    return "Marple - Al-Ikhsan Sports WhatsApp Bot is running! 👟🤖"

@app.route("/webhook", methods=["GET", "POST"])
def webhook():
    if request.method == "GET":
        # WhatsApp webhook verification
        mode = request.args.get("hub.mode")
        token = request.args.get("hub.verify_token")
        challenge = request.args.get("hub.challenge")
        if mode == "subscribe" and token == "BOT":
            return challenge, 200
        else:
            return "Failed", 403
    
    elif request.method == "POST":
        try:
            # Get webhook data
            webhook_data = request.get_json()
            print(f"Received webhook: {json.dumps(webhook_data, indent=2)}")
            
            # Validate webhook structure
            if not webhook_data or "entry" not in webhook_data:
                print("Invalid webhook data - no entry")
                return jsonify({"status": "ok"}), 200
                
            if not webhook_data["entry"] or len(webhook_data["entry"]) == 0:
                print("No entries in webhook")
                return jsonify({"status": "ok"}), 200
                
            entry = webhook_data["entry"][0]
            if "changes" not in entry or len(entry["changes"]) == 0:
                print("No changes in entry")
                return jsonify({"status": "ok"}), 200
                
            changes = entry["changes"][0]
            if "value" not in changes:
                print("No value in changes")
                return jsonify({"status": "ok"}), 200
                
            value = changes["value"]
            
            # Check if there are messages
            if "messages" not in value or len(value["messages"]) == 0:
                print("No messages in value")
                return jsonify({"status": "ok"}), 200
                
            data = value["messages"][0]
            customer_phone = data.get("from")
            
            if not customer_phone:
                print("No customer phone number")
                return jsonify({"status": "ok"}), 200
            
            # Get customer name if available
            customer_name = "Customer"
            if "contacts" in value and value["contacts"]:
                profile = value["contacts"][0].get("profile", {})
                customer_name = profile.get("name", "Customer")

            print(f"Processing message from {customer_phone} ({customer_name})")

            # Handle different message types
            if data["type"] == "text":
                prompt = data["text"]["body"]
                detected_language = detect_language(prompt)
                
                print(f"Text message: {prompt} (language: {detected_language})")
                
                # Update conversation in database
                update_conversation(customer_phone, customer_name, prompt, detected_language, 'text')
                
                # Handle greetings with special response
                if is_greeting(prompt):
                    if detected_language == 'ms':
                        greeting_response = "Hellooo! Saya Marple dan saya assistant terbaik untuk hari ini. Tolong beritahu saya, macam mana saya boleh tolong you, dan apa yang you cari? 😊"
                    else:
                        greeting_response = "Hellooo! I am Marple and I am your dearest assistant for today. Please tell me, how can I help you, and what are you looking for? 😊"
                    
                    send(greeting_response, customer_phone)
                else:
                    # Get AI response
                    response_text = get_ai_response(prompt, customer_name, detected_language)
                    send(response_text, customer_phone)

            elif data["type"] == "image":
                # Handle image messages
                print("Processing image message")
                try:
                    detected_language = 'en'  # Default to English for media
                    
                    # Get image URL
                    if "image" not in data or "id" not in data["image"]:
                        send("Sorry boss! Can't access that image. Try sending it again? 😅", customer_phone)
                        return jsonify({"status": "ok"}), 200
                        
                    media_url_endpoint = f'https://graph.facebook.com/v18.0/{data["image"]["id"]}/'
                    headers = {'Authorization': f'Bearer {wa_token}'}
                    media_response = requests.get(media_url_endpoint, headers=headers)
                    
                    if media_response.status_code != 200:
                        send("Sorry boss! Having trouble downloading that image 😅", customer_phone)
                        return jsonify({"status": "ok"}), 200
                        
                    media_url = media_response.json().get("url")
                    if not media_url:
                        send("Sorry boss! Can't get that image URL 😅", customer_phone)
                        return jsonify({"status": "ok"}), 200
                    
                    # Download image
                    media_download_response = requests.get(media_url, headers=headers)
                    filename = "/tmp/temp_image.jpg"
                    
                    with open(filename, "wb") as temp_media:
                        temp_media.write(media_download_response.content)
                    
                    # Upload to Gemini for analysis
                    file = genai.upload_file(path=filename, display_name="customer_image")
                    response = model.generate_content(["Describe what you see in this image. If it's shoes, identify the brand, type, color, and style.", file])
                    image_description = response._result.candidates[0].content.parts[0].text
                    
                    print(f"Image analysis: {image_description}")
                    
                    # Update conversation
                    update_conversation(customer_phone, customer_name, f"[Image: {image_description}]", detected_language, 'image')
                    
                    # Generate contextual response using separate conversation
                    conversation = model.start_chat(history=[])
                    conversation.send_message(system_prompt)
                    
                    context_prompt = f"""Customer "{customer_name}" sent an image. Here's what I see: {image_description}

Respond as Marple from Al-Ikhsan Sports. If they're showing shoes:
1. Try to identify if we have similar shoes in our catalog
2. Be honest if we don't have that exact brand/model
3. Suggest alternatives from our available shoes
4. Include product URLs if recommending alternatives

If it's not shoes, respond naturally and try to redirect to shoe-related help.
Keep response short, friendly, and include appropriate emojis!"""

                    conversation.send_message(context_prompt)
                    response_text = conversation.last.text
                    
                    if len(response_text) > 300:
                        sentences = response_text.split('. ')
                        response_text = '. '.join(sentences[:2]) + ('.' if len(sentences) > 2 else '')
                    
                    send(response_text, customer_phone)
                    
                    # Clean up
                    remove(filename)
                    cleanup_uploaded_files()
                    
                except Exception as e:
                    print(f"Error processing image: {e}")
                    print(traceback.format_exc())
                    send("Sorry boss! Having trouble with that image. Can you describe what you're looking for instead? 😅", customer_phone)

            elif data["type"] == "audio":
                # Handle voice messages
                print("Processing audio message")
                try:
                    detected_language = 'en'  # Will be detected from transcription
                    
                    if "audio" not in data or "id" not in data["audio"]:
                        send("Sorry boss! Can't access that voice message 😅", customer_phone)
                        return jsonify({"status": "ok"}), 200
                    
                    # Get audio URL
                    media_url_endpoint = f'https://graph.facebook.com/v18.0/{data["audio"]["id"]}/'
                    headers = {'Authorization': f'Bearer {wa_token}'}
                    media_response = requests.get(media_url_endpoint, headers=headers)
                    
                    if media_response.status_code != 200:
                        send("Sorry boss! Can't download your voice message 😅", customer_phone)
                        return jsonify({"status": "ok"}), 200
                    
                    media_url = media_response.json().get("url")
                    if not media_url:
                        send("Sorry boss! Can't get voice message URL 😅", customer_phone)
                        return jsonify({"status": "ok"}), 200
                    
                    # Download audio
                    media_download_response = requests.get(media_url, headers=headers)
                    filename = "/tmp/temp_audio.mp3"
                    
                    with open(filename, "wb") as temp_media:
                        temp_media.write(media_download_response.content)
                    
                    # Upload to Gemini for transcription
                    file = genai.upload_file(path=filename, display_name="customer_audio")
                    response = model.generate_content(["Transcribe this audio message accurately. If it's in Malay, keep it in Malay. If English, keep it in English.", file])
                    transcription = response._result.candidates[0].content.parts[0].text
                    
                    print(f"Audio transcription: {transcription}")
                    
                    # Detect language from transcription
                    detected_language = detect_language(transcription)
                    
                    # Update conversation
                    update_conversation(customer_phone, customer_name, transcription, detected_language, 'audio')
                    
                    # Get AI response for the transcription
                    response_text = get_ai_response(f"[Voice message]: {transcription}", customer_name, detected_language)
                    send(response_text, customer_phone)
                    
                    # Clean up
                    remove(filename)
                    cleanup_uploaded_files()
                    
                except Exception as e:
                    print(f"Error processing audio: {e}")
                    print(traceback.format_exc())
                    send("Sorry boss! Can't hear your voice message clearly. Can you type instead? 😅", customer_phone)

            elif data["type"] == "document":
                # Handle document messages (mainly PDFs)
                print("Processing document message")
                try:
                    detected_language = 'en'
                    
                    if "document" not in data or "id" not in data["document"]:
                        send("Sorry boss! Can't access that document 😅", customer_phone)
                        return jsonify({"status": "ok"}), 200
                    
                    # Get document URL
                    media_url_endpoint = f'https://graph.facebook.com/v18.0/{data["document"]["id"]}/'
                    headers = {'Authorization': f'Bearer {wa_token}'}
                    media_response = requests.get(media_url_endpoint, headers=headers)
                    
                    if media_response.status_code != 200:
                        send("Sorry boss! Can't download that document 😅", customer_phone)
                        return jsonify({"status": "ok"}), 200
                    
                    media_url = media_response.json().get("url")
                    if not media_url:
                        send("Sorry boss! Can't get document URL 😅", customer_phone)
                        return jsonify({"status": "ok"}), 200
                    
                    # Download document
                    media_download_response = requests.get(media_url, headers=headers)
                    
                    # Try to process as PDF
                    doc = fitz.open(stream=media_download_response.content, filetype="pdf")
                    
                    # Extract first page as image for analysis
                    page = doc[0]
                    destination = "/tmp/temp_doc_image.jpg"
                    pix = page.get_pixmap()
                    pix.save(destination)
                    
                    # Upload to Gemini for analysis
                    file = genai.upload_file(path=destination, display_name="document_page")
                    response = model.generate_content(["What type of document is this? Describe the content briefly.", file])
                    doc_description = response._result.candidates[0].content.parts[0].text
                    
                    print(f"Document analysis: {doc_description}")
                    
                    # Update conversation
                    update_conversation(customer_phone, customer_name, f"[Document: {doc_description}]", detected_language, 'document')
                    
                    # Generate response using separate conversation
                    conversation = model.start_chat(history=[])
                    conversation.send_message(system_prompt)
                    
                    context_prompt = f"""Customer "{customer_name}" sent a document. Here's what I found: {doc_description}

Respond as Marple from Al-Ikhsan Sports. If it's:
- A receipt/order: Acknowledge and offer help with returns/exchanges
- A size chart: Help them find the right size from our shoes
- Shoe catalog: Offer to help find similar items from our available stock
- Other: Respond politely and redirect to shoe shopping

Keep response short and helpful!"""

                    conversation.send_message(context_prompt)
                    response_text = conversation.last.text
                    
                    send(response_text, customer_phone)
                    
                    # Clean up
                    remove(destination)
                    cleanup_uploaded_files()
                    doc.close()
                    
                except Exception as e:
                    print(f"Error processing document: {e}")
                    print(traceback.format_exc())
                    send("Sorry boss! Can't read that document properly. Can you tell me what you need help with? 😅", customer_phone)

            else:
                # Handle unsupported message types
                print(f"Unsupported message type: {data['type']}")
                send("Sorry boss! I can handle text, images, voice messages, and documents only. What shoes can I help you find today? 👟", customer_phone)
                    
        except Exception as e:
            print(f"Critical error in webhook processing: {e}")
            print(traceback.format_exc())
            
            # Try to send error message if we can get the phone number
            try:
                webhook_data = request.get_json()
                customer_phone = webhook_data["entry"][0]["changes"][0]["value"]["messages"][0]["from"]
                send("Sorry boss! System tengah busy sikit. Can you try again in a moment? 😅", customer_phone)
            except:
                print("Could not send error message - unable to extract phone number")
            
        return jsonify({"status": "ok"}), 200

if __name__ == "__main__":
    app.run(debug=True, port=8000)
