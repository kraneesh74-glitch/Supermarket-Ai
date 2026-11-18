# Publishing & Deployment Guide: SuperMart AI Enquiry Agent

This guide covers how to run, publish, and deploy the AI Enquiry Agent across **Local Testing**, **WhatsApp Business Cloud API**, **Web Chat Widget Embedding**, and **Production Cloud Hosting**.

---

## 1. Quick Local Launch

Run the FastAPI server locally:

```powershell
# Using the installed Python 3.12 environment
& "C:\Users\user\AppData\Local\Programs\Python\Python312\python.exe" -m uvicorn apps.api.main:app --host 127.0.0.1 --port 8000 --reload
```

Once running:
- **Interactive Web Chat Widget:** Open [http://localhost:8000](http://localhost:8000) in your browser.
- **API Documentation (Swagger UI):** Open [http://localhost:8000/docs](http://localhost:8000/docs).
- **Health Check:** [http://localhost:8000/health](http://localhost:8000/health).

---

## 2. Publishing to WhatsApp Business Cloud API

To connect the agent to a live WhatsApp Business number:

### Step 2.1: Expose Your Local Server (for Development/Testing)
If testing locally before cloud deployment, expose port `8000` to the internet using **ngrok** or **Cloudflare Tunnel**:

```bash
ngrok http 8000
```
Copy the secure forwarding URL (e.g., `https://abc1234.ngrok-free.app`).

### Step 2.2: Configure the Webhook in Meta Developer Portal
1. Go to [developers.facebook.com](https://developers.facebook.com) $\rightarrow$ Your App $\rightarrow$ **WhatsApp** $\rightarrow$ **Configuration**.
2. Click **Edit Webhook**:
   - **Callback URL:** `https://<YOUR_DOMAIN_OR_NGROK>/webhook/whatsapp`
   - **Verify Token:** `SUPERMART_WA_VERIFY_TOKEN_2026` *(defined in `apps/api/routes/whatsapp.py`)*
3. Click **Verify and Save**. Meta will send a challenge verification handshake to your endpoint.
4. Under **Webhook fields**, click **Manage** and subscribe to **`messages`**.
5. Send a WhatsApp message to your test number:
   - *"Are avocados in stock?"*
   - The agent responds instantly with stock, price, aisle location, and interactive quick-reply buttons!

---

## 3. Embedding Web Chat Widget on the Supermarket Website

To embed the conversational assistant into your website, paste this iframe snippet before the closing `</body>` tag on any HTML page:

```html
<!-- SuperMart AI Enquiry Widget -->
<iframe 
  src="https://<YOUR_DEPLOYED_DOMAIN>/" 
  style="position: fixed; bottom: 20px; right: 20px; width: 420px; height: 640px; border: none; border-radius: 16px; box-shadow: 0 10px 30px rgba(0,0,0,0.15); z-index: 99999;"
  title="SuperMart AI Assistant">
</iframe>
```

---

## 4. Production Cloud Deployment

### Option A: Deploy via Docker (Recommended)
Build and run the containerized service anywhere Docker is supported:

```bash
docker compose up --build -d
```
The application will start with automated healthchecks on port `8000`.

### Option B: Deploy to Google Cloud Run (Serverless)
```bash
gcloud builds submit --tag gcr.io/<PROJECT_ID>/supermart-agent
gcloud run deploy supermart-agent \
  --image gcr.io/<PROJECT_ID>/supermart-agent \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated \
  --port 8000
```

### Option C: Deploy to Railway or Render
1. Push this project folder to a GitHub repository:
   ```bash
   git init
   git add .
   git commit -m "Initial SuperMart AI Agent release"
   git remote add origin https://github.com/<YOUR_USER>/supermart-agent.git
   git push -u origin main
   ```
2. Log in to [Railway](https://railway.app) or [Render](https://render.com).
3. Select **New Project $\rightarrow$ Deploy from GitHub repo**.
4. Set the Start Command: `uvicorn apps.api.main:app --host 0.0.0.0 --port $PORT`.
5. Deploy! Railway/Render will provide an automatic SSL HTTPS domain.

---

## 5. Environment Variables Reference

| Variable | Default Value | Description |
| :--- | :--- | :--- |
| `PORT` | `8000` | Port for the FastAPI server |
| `WHATSAPP_VERIFY_TOKEN` | `SUPERMART_WA_VERIFY_TOKEN_2026` | Token used by Meta to verify webhook |
| `WHATSAPP_APP_SECRET` | `supermart_secret_key` | Secret key for HMAC signature validation |
| `MAX_STEPS` | `5` | Safety step limit per conversation turn |

