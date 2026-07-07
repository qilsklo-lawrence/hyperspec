# Hyperspec

Welcome to Hyperspec! Since this application is not currently hosted online, you will need to download and run it on your own computer. Don't worry—we've provided automated scripts to make this as easy as running a single file.

## Prerequisites

Before you begin, ensure you have the following installed on your computer:
1. **Python** (version 3.7 or higher): [Download Python](https://www.python.org/downloads/)
2. **Node.js** (which includes `npm`): [Download Node.js](https://nodejs.org/)

## 1. Download the Code

1. On the GitHub page, click the green **Code** button near the top right.
2. Select **Download ZIP** from the dropdown menu.
3. Once downloaded, extract the ZIP file to a folder on your computer.

## 2. Run the Application!

Navigate into the extracted folder and run the provided startup script for your operating system. This script will automatically build the frontend, create a virtual environment, install all dependencies, and start the server for you!

**Windows:**
Double-click on the `run.bat` file in the folder (or run it from Command Prompt).

**Mac / Linux:**
Open a terminal, navigate to the folder, and run:
```bash
chmod +x run.sh
./run.sh
```

Once the terminal says it's ready, open your web browser and go to:
**[http://localhost:8080](http://localhost:8080)**

---

<details>
<summary><b>Having trouble? Click here for manual setup instructions</b></summary>

If the automated scripts don't work for you, open a terminal in the project folder and run these steps manually:

**1. Build the frontend**
```bash
cd frontend
npm install
npm run build
cd ..
```

**2. Setup the backend and run**
```bash
# Create and activate a virtual environment
python -m venv venv
source venv/bin/activate  # Windows users run: venv\Scripts\activate

# Install dependencies and start the app
pip install -r requirements.txt
python app.py
```
</details>
