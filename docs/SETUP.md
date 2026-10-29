# GrabResult Setup Guide (beginner-friendly)

You do **not** need to know programming. Follow the steps for your computer.

## What you need

- **Python 3.10 or newer.** Check: open a terminal/command prompt and type
  `python3 --version` (Mac/Linux) or `py --version` (Windows).
  - Don't have it? Download free from https://www.python.org/downloads/
    (Windows: tick **"Add python.exe to PATH"** during install).
- An internet connection (for installing libraries once, and for research).

That's everything. No accounts, no API keys, no payments.

## Option A — the easy way

**Windows:** unzip `grabresult.zip`, double-click **`start-windows.bat`**.
**Mac/Linux:** unzip, open a terminal in the folder, run **`./start.sh`**
(first run may ask for your password — that's just installing Python tools).

Your browser opens at **http://127.0.0.1:5000**. Done.

## Option B — manual steps (if the easy way fails)

1. Unzip `grabresult.zip` and open a terminal/command prompt **in that folder**.
2. Create the environment:
   - Mac/Linux: `python3 -m venv .venv`
   - Windows: `py -3 -m venv .venv`
3. Install libraries (one-time, ~1 minute):
   - Mac/Linux: `.venv/bin/pip install -r requirements.txt`
   - Windows: `.venv\Scripts\pip install -r requirements.txt`
4. Start the app:
   - Mac/Linux: `.venv/bin/python run.py`
   - Windows: `.venv\Scripts\python run.py`
5. Open **http://127.0.0.1:5000** in your browser.

To stop: press `Ctrl+C` in the terminal.

## Your first research run (2 minutes)

1. Click **New Research**.
2. Type what you want, e.g.:
   `Find 20 bakeries in Lahore, Pakistan. Collect names, addresses and phone numbers.`
3. Set **City = Lahore**, **Country = Pakistan** (optional but helps).
4. Click **Start Research**. Watch real progress messages.
5. When it finishes, click the job → review results → **Export XLSX**.

## Where is my data?

Everything lives in the `instance/` folder next to the app:

- `instance/grabresult.db` — your database (jobs, leads, history). **Back this
  file up** to keep your research.
- `instance/exports/` — generated Excel/CSV files.
- `instance/uploads/` — files you imported.

## Common problems

| Problem | Fix |
|---|---|
| `python3: command not found` | Install Python (see above); on Mac try `python` instead |
| Browser shows "can't connect" | The terminal running `run.py` must stay open |
| Research returns few results | Public map data varies by city; try a bigger city or fewer filters |
| Port 5000 busy | Run `PORT=5057 .venv/bin/python run.py` (Mac/Linux) |
| Antivirus blocks the .bat | Allow it — it only starts a local Python program |

## Updating

Replace the folder with the new zip, then copy your old
`instance/grabresult.db` into the new folder to keep your history.
