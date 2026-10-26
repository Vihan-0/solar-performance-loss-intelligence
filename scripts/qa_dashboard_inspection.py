"""
Quality Assurance and Automated Browser Inspection Script
Project: Adaptive Solar Performance & Loss Intelligence

Connects directly to the live Streamlit instance via Chrome DevTools Protocol (CDP),
interacts with every navigation section, validates controls, verifies canonical units,
and captures high-resolution screenshots.
"""

import asyncio
import base64
import json
import sys
import time
import urllib.request
from pathlib import Path
import websockets

sys.stdout.reconfigure(encoding="utf-8")

FIG_DIR = Path("reports/figures")
FIG_DIR.mkdir(parents=True, exist_ok=True)


async def send_cdp(ws, method, params=None):
    msg_id = int(time.time() * 1000) % 1000000
    payload = {"id": msg_id, "method": method}
    if params:
        payload["params"] = params
    await ws.send(json.dumps(payload))
    while True:
        resp = await ws.recv()
        data = json.loads(resp)
        if data.get("id") == msg_id:
            return data.get("result", {})


async def eval_js(ws, expr):
    res = await send_cdp(ws, "Runtime.evaluate", {"expression": expr, "returnByValue": True})
    if "result" in res and "value" in res["result"]:
        return res["result"]["value"]
    return res


async def take_screenshot(ws, output_path: Path):
    res = await send_cdp(ws, "Page.captureScreenshot", {"format": "png"})
    img_data = base64.b64decode(res["data"])
    with open(output_path, "wb") as f:
        f.write(img_data)
    print(f"Captured screenshot -> {output_path} ({len(img_data):,} bytes)")


async def navigate_to(ws, section_name: str):
    print(f"\n--- Navigating to: '{section_name}' ---")
    js = f"""
    (() => {{
        const labels = Array.from(document.querySelectorAll('label'));
        const target = labels.find(l => l.innerText.includes('{section_name}'));
        if (target) {{
            target.click();
            return 'Clicked: ' + target.innerText;
        }}
        return 'Not found';
    }})()
    """
    res = await eval_js(ws, js)
    print(f"Navigation result: {res}")
    # Wait for Streamlit re-run
    await asyncio.sleep(2.0)


import subprocess
import tempfile


async def run_qa():
    chrome_proc = None
    try:
        try:
            urllib.request.urlopen("http://127.0.0.1:9222/json", timeout=1)
        except Exception:
            print("Launching headless Chrome for QA inspection...")
            chrome_dir = tempfile.mkdtemp()
            cmd = [
                r"C:\Program Files\Google\Chrome\Application\chrome.exe",
                "--headless=new",
                "--remote-debugging-port=9222",
                "--remote-debugging-address=127.0.0.1",
                "--no-first-run",
                "--no-default-browser-check",
                f"--user-data-dir={chrome_dir}",
                "--window-size=1440,960",
                "http://localhost:8501",
            ]
            chrome_proc = subprocess.Popen(cmd)
            for _ in range(10):
                await asyncio.sleep(1)
                try:
                    urllib.request.urlopen("http://127.0.0.1:9222/json", timeout=1)
                    break
                except Exception:
                    pass

        info = json.loads(urllib.request.urlopen("http://127.0.0.1:9222/json").read().decode())
        page = next(p for p in info if p["type"] == "page" and "localhost:8501" in p["url"])
        ws_url = page["webSocketDebuggerUrl"]
        print(f"Connected to CDP page: {page['title']} at {ws_url}")

        async with websockets.connect(ws_url, max_size=20 * 1024 * 1024) as ws:
            # Enable Page domain
            await send_cdp(ws, "Page.enable")

            # Wait for Streamlit to render
            print("Waiting for Streamlit app to render...")
            for _ in range(15):
                ready = await eval_js(ws, "Boolean(document.querySelector('label') && document.body.innerText.length > 200)")
                if ready:
                    break
                await asyncio.sleep(1.0)

            # -------------------------------------------------------------
            # 1. VIEW 1: Overview & Loss Summary
            # -------------------------------------------------------------
            await navigate_to(ws, "Overview & Loss Summary")
            await asyncio.sleep(2.5)

            text_v1 = (await eval_js(ws, "document.body.innerText")).lower()
            assert (
                "adaptive solar performance & loss intelligence" in text_v1
                or "operational performance & loss intelligence" in text_v1
            )
            assert "historical held-out test evaluation" in text_v1
            assert "measured generation" in text_v1
            assert "model-predicted expected" in text_v1
            assert "persistent actionable shortfall" in text_v1
            assert "inverter alert-hours" in text_v1
            assert "total positive residual shortfall" in text_v1
            assert "transient noise filtered" in text_v1
            assert "facility energy balance" in text_v1
            assert "1,736.3" in text_v1
            assert "1,724.5" in text_v1
            assert "89.4" in text_v1
            print("✓ View 1: Text, canonical units, exact values, and accounting distinction verified.")

            await take_screenshot(ws, FIG_DIR / "milestone_5_dashboard_overview.png")

            # -------------------------------------------------------------
            # 2. VIEW 2: Plant & Inverter Explorer
            # -------------------------------------------------------------
            await navigate_to(ws, "Plant & Inverter Explorer")
            await asyncio.sleep(2.0)

            text_v2 = (await eval_js(ws, "document.body.innerText")).lower()
            assert "inverter telemetry & anomaly explorer" in text_v2
            assert "detection evidence" in text_v2
            assert "observed generation" in text_v2
            assert "expected generation" in text_v2
            assert "persistent shortfall" in text_v2
            assert "inverter alert-hours" in text_v2
            assert "active power (kw)" in text_v2 or "expected power (model)" in text_v2
            print("✓ View 2: Telemetry Explorer, Detection Evidence banner, and kW units verified.")

            await take_screenshot(ws, FIG_DIR / "milestone_5_dashboard_explorer.png")

            # -------------------------------------------------------------
            # 3. VIEW 3: Inverter Loss Prioritization
            # -------------------------------------------------------------
            await navigate_to(ws, "Inverter Loss Prioritization")
            await asyncio.sleep(2.0)

            text_v3 = (await eval_js(ws, "document.body.innerText")).lower()
            assert "inverter loss prioritization & investigation ranking" in text_v3
            assert "min persistent shortfall filter (kwh)" in text_v3
            assert "alert-hours" in text_v3
            assert "export investigation priorities (csv)" in text_v3
            print("✓ View 3: Inverter ranking table, alert-hours, and filter controls verified.")

            await take_screenshot(ws, FIG_DIR / "milestone_5_dashboard_prioritization.png")

            # -------------------------------------------------------------
            # 4. VIEW 4: Interactive Synthetic Demo
            # -------------------------------------------------------------
            await navigate_to(ws, "Interactive Synthetic Demo")
            await asyncio.sleep(2.0)

            text_v4 = (await eval_js(ws, "document.body.innerText")).lower()
            assert "interactive synthetic underperformance sandbox" in text_v4
            assert "synthetic testbench sandbox" in text_v4
            assert "run synthetic detection test" in text_v4

            # Click the button 'Run Synthetic Detection Test'
            click_btn_js = """
            (() => {
                const buttons = Array.from(document.querySelectorAll('button'));
                const btn = buttons.find(b => b.innerText.includes('Run Synthetic Detection Test'));
                if (btn) {
                    btn.click();
                    return 'Clicked button: ' + btn.innerText;
                }
                return 'Button not found';
            })()
            """
            btn_res = await eval_js(ws, click_btn_js)
            print(f"Simulation test button click: {btn_res}")
            await asyncio.sleep(3.0)

            text_v4_after = (await eval_js(ws, "document.body.innerText")).lower()
            assert "simulation decision analysis" in text_v4_after
            assert "injected duration" in text_v4_after
            assert "power reduction" in text_v4_after
            assert "persistent anomaly triggered" in text_v4_after or "suppressed as transient" in text_v4_after
            print("✓ View 4: Synthetic testbench simulation executed and verified.")

            await take_screenshot(ws, FIG_DIR / "milestone_5_dashboard_synthetic.png")

            # -------------------------------------------------------------
            # 5. VIEW 5: Model & Methodology
            # -------------------------------------------------------------
            await navigate_to(ws, "Model & Methodology")
            await asyncio.sleep(2.0)

            text_v5 = (await eval_js(ws, "document.body.innerText")).lower()
            assert "physical scale & unit discrepancy resolution" in text_v5
            assert "10.1093/ce/zkae050" in text_v5
            assert "growatt mic 1500tl-x" in text_v5
            assert "leakage-free feature engineering" in text_v5
            assert "chronological splitting strategy" in text_v5
            assert "measured model benchmark on out-of-time test set" in text_v5
            assert "external weather enrichment experiment" in text_v5
            assert "investigation & recalibration of plant 2 high-irradiance threshold" in text_v5
            assert "critical domain limitations" in text_v5
            print("✓ View 5: All 7 methodology sections, literature citations, and threshold explanations verified.")

            await take_screenshot(ws, FIG_DIR / "milestone_5_dashboard_methodology.png")

            # Return to Overview
            await navigate_to(ws, "Overview & Loss Summary")
            print("\nAll 5 navigation sections successfully inspected, verified, and photographed!")
    finally:
        if chrome_proc:
            try:
                chrome_proc.terminate()
            except Exception:
                pass


if __name__ == "__main__":
    asyncio.run(run_qa())
