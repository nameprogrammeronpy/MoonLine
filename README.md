# 🌙 MoonLine - Mental Health Platform

<div align="center">
  <img src="static/images/backgrounddarktheme.jpg" alt="MoonLine" width="600">
  
  **Your Mental Savior**
  
  A digital platform for mental health support designed for students and young adults
</div>

---

## ✨ Features

### 🤖 Luna AI
- Empathetic AI companion available 24/7
- Context-aware conversations
- Powered by Google Gemini AI
- Anonymous and secure

### 📔 Emotion Journal
- Track your daily moods
- Record thoughts and feelings
- Visualize emotional patterns
- Tag-based organization

### 🧘 Self-Care Toolkit
- 4-7-8 Breathing exercises
- 5-4-3-2-1 Grounding technique
- Progressive muscle relaxation
- Ambient sounds for relaxation
- Gratitude prompts

### 📊 Progress Tracking
- Weekly mood calendar
- Statistics and insights
- Streak tracking
- Personal growth metrics

---

## 🚀 Quick Start

### Local Development

```bash
# Clone the repository
git clone https://github.com/nameprogrammeronpy/MoonLine.git
cd MoonLine

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Set up environment variables
cp .env.example .env
# Edit .env with your API keys

# Run the application
python app.py
```

Visit `http://localhost:5000` in your browser.

### Environment Variables

Create a `.env` file with:

```env
GEMINI_API_KEY_1=your_google_ai_api_key
GEMINI_API_KEY_2=your_backup_api_key
SECRET_KEY=your_secret_key
```

---

## 🌐 Deployment on Koyeb

### Option 1: Deploy via GitHub

1. Fork this repository
2. Go to [Koyeb Dashboard](https://app.koyeb.com/)
3. Click **Create App** → **GitHub**
4. Select your forked repository
5. Configure:
   - **Build command**: `pip install -r requirements.txt`
   - **Run command**: `gunicorn app:app`
   - **Port**: `8000`
6. Add environment variables:
   - `GEMINI_API_KEY_1`
   - `GEMINI_API_KEY_2`
   - `SECRET_KEY`
7. Deploy!

### Option 2: Deploy via Docker

```bash
# Build image
docker build -t moonline .

# Run container
docker run -p 8000:8000 moonline
```

---

## 📁 Project Structure

```
MoonLine/
├── app.py              # Main Flask application
├── database.py         # SQLite database operations
├── requirements.txt    # Python dependencies
├── Procfile           # Koyeb/Heroku process file
├── runtime.txt        # Python version
├── static/
│   ├── css/
│   │   └── style.css
│   ├── js/
│   │   └── app.js
│   └── images/
│       ├── backgrounddarktheme.jpg
│       └── backgroundbrighttheme.jpg
└── templates/
    ├── index.html      # Landing page
    ├── dashboard.html  # User dashboard
    ├── luna_ai.html    # AI chat page
    ├── journal.html    # Emotion journal
    ├── toolkit.html    # Self-care tools
    └── pricing.html    # Pricing page
```

---

## 🛠 Tech Stack

- **Backend**: Python, Flask
- **Database**: SQLite
- **AI**: Google Gemini API
- **Frontend**: HTML5, CSS3, JavaScript
- **3D Graphics**: Three.js (3D Moon)
- **Deployment**: Koyeb, Gunicorn

---

## 🎨 Design Philosophy

- **Dark Theme**: Midnight sky inspired, calming
- **Accent Colors**: Warm orange (#ff8c42) with soft pastels
- **Typography**: Cormorant Garamond + Poppins
- **UI**: Glassmorphism, smooth animations
- **3D Elements**: Interactive moon visualization

---

## 📝 License

MIT License - feel free to use this project for your own purposes.

---

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

---

<div align="center">
  Made with 💜 for mental wellness
  
  **MoonLine** - Your path to emotional wellness starts here
</div>

