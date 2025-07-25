# Marple - Your Friendly Al-Ikhsan Sports WhatsApp Assistant

Marple is an AI-powered WhatsApp chatbot designed to assist Al-Ikhsan Sports customers with their shoe inquiries. Built with Flask and integrated with the Google Gemini AI model, Marple offers a conversational, humorous, and empathetic experience, mimicking a real friend rather than a rigid bot.

---

## Features

* **Multilingual Support**: Automatically detects and responds in either English or Malay, including Malaysian slang for a localized touch.
* **Product Knowledge**: Provides information on available men's, women's, and kids' shoes, including features, prices, and direct links to the Al-Ikhsan website.
* **Intelligent Recommendations**: If a requested product isn't available, Marple honestly states so and suggests similar alternatives from the current stock.
* **Size Guide**: Offers a comprehensive shoe size conversion chart to help customers find their perfect fit.
* **Current Promotions**: Informs customers about ongoing discounts, free delivery, student discounts, and bundle deals.
* **Media Handling**: Processes and responds to text, image, audio (voice messages), and document inputs.
* **Conversation Tracking**: Utilizes an SQLite database to remember customer interactions and provide timely follow-ups.
* **Automated Follow-ups**: Proactively checks for silent customers and sends contextual follow-up messages to re-engage them.
* **Human-like Interaction**: Engineered to respond in a short, friendly, witty, and emotional manner, matching the customer's energy and mood.

---

## Getting Started

These instructions will get you a copy of the project up and running on your local machine for development and testing purposes.

### Prerequisites

Before you begin, ensure you have the following installed:

* **Python 3.8+**
* **pip** (Python package installer)

### Environment Variables

You'll need to set up the following environment variables:

* `WA_TOKEN`: Your WhatsApp Business API token.
* `GEN_API`: Your Google Gemini API key.
* `PHONE_ID`: Your WhatsApp Business Phone Number ID.
* `PHONE_NUMBER`: Your WhatsApp Business Phone Number.
