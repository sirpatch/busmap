from flask import Flask, render_template_string, jsonify
import requests, re, json, time, threading

app = Flask(__name__)

BASE = "https://czynaczas.pl"
SOCKET = f"{BASE}/socket.io/?EIO=4&transport=polling"
STOPS_URL = f"{BASE}/api/zielonagora/transport"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
    "Origin": BASE,
    "Referer": BASE + "/zielonagora",
    "Accept": "*/*",
}

COOKIE = ""  # paste cookie here if needed
if COOKIE:
    HEADERS["Cookie"] = COOKIE

latest_buses = {}
latest_stops = {}
last_update = 0

def fetch_buses_once():
    try:
        r = requests.get(SOCKET, headers=HEADERS, timeout=6)
        sid_match = re.search(r'"sid":"([^"]+)"', r.text)
        if not sid_match:
            return {}
        sid = sid_match.group(1)
        url = f"{SOCKET}&sid={sid}"
        requests.post(url, headers=HEADERS, data='40/zielonagora,{}', timeout=6)
        time.sleep(1)
        r = requests.get(url, headers=HEADERS, timeout=6)
        if "42/zielonagora" not in r.text:
            return {}
        payload = r.text.split("42/zielonagora,")[1]
        data = json.loads(payload)
        return data[1].get("data", {})
    except Exception as e:
        print("bus fetch error:", e)
        return {}

def fetch_stops():
    try:
        r = requests.get(STOPS_URL, headers=HEADERS, timeout=6)
        r.raise_for_status()
        data = r.json()
        stops = data.get("stops", [])
        result = []
        for s in stops:
            if len(s) >= 4:
                result.append({
                    "id": s[0],
                    "name": s[1],
                    "lat": s[2],
                    "lon": s[3],
                    "stop_name": s[1],
                    "trip_headsign": s[4] if len(s) > 4 else ""
                })
        return result
    except Exception as e:
        print("stop fetch error:", e)
        return []

def updater():
    global latest_buses, latest_stops, last_update
    while True:
        buses = fetch_buses_once()
        stops = fetch_stops()
        if buses:
            latest_buses = buses
            last_update = time.time()
            print(f"✅ {len(buses)} buses")
        if stops:
            latest_stops = stops
        time.sleep(4)

@app.route("/")
def index():
    html = """
    <!DOCTYPE html>
    <html>
    <head>
      <meta charset="utf-8"/>
      <title>Zielona Góra — Real-Time Bus Tracker</title>
      <meta name="viewport" content="width=device-width, initial-scale=1.0">
      <link rel="stylesheet"
        href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
      <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
      <style>
        html,body,#map{height:100%;margin:0;background:#1e1e1e;}
        .leaflet-container { background: #1e1e1e; }
        .bus-label {
          font-size: 16px;
          font-weight: bold;
          text-align: center;
          display: inline-block;
        }
        .stop-label {
          font-size: 12px;
          color: #00ffff;
          text-align: center;
          font-weight: bold;
          text-shadow: 0 0 2px black;
        }
        #bus-info {
          position: fixed;
          bottom: 0;
          left: 0;
          width: 100%;
          background: rgba(0,0,0,0.85);
          color: #fff;
          font-size: 14px;
          padding: 6px 10px;
          z-index: 9999;
        }
        #stats {
          position: fixed;
          top: 10px;
          right: 10px;
          background: rgba(0,0,0,0.7);
          color: #fff;
          font-size: 14px;
          padding: 6px 10px;
          border-radius: 5px;
          z-index: 9999;
        }
      </style>
    </head>
    <body>
      <div id="map"></div>
      <div id="bus-info">Click a bus or stop to see info...</div>
      <div id="stats">Buses driving: 0</div>
      <script>
        const map = L.map('map').setView([51.94,15.50],13);

        L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_nolabels/{z}/{x}/{y}{r}.png', {
          maxZoom: 19,
          attribution: '&copy; OpenStreetMap & Carto'
        }).addTo(map);
        L.tileLayer('https://{s}.basemaps.cartocdn.com/light_only_labels/{z}/{x}/{y}{r}.png').addTo(map);

        let busMarkers = {}, stopMarkers = [];
        let trackedBusId = null;

        map.on('click', () => {
          trackedBusId = null;
          document.getElementById('bus-info').innerHTML = "Click a bus or stop to see info...";
        });

        async function update() {
          const [busRes, stopRes] = await Promise.all([
            fetch('/api/buses'), fetch('/api/stops')
          ]);
          const buses = await busRes.json();
          const stops = await stopRes.json();

          // Update stats panel
          document.getElementById('stats').innerHTML = "Buses driving: " + Object.keys(buses).length;

          // Draw stops
          if (stopMarkers.length === 0 && stops.length) {
            for (const s of stops) {
              const m = L.marker([s.lat, s.lon], {
                icon: L.divIcon({
                  className: 'stop-label',
                  html: `🚏<br>${s.stop_name}`,
                  iconSize: [60, 25],
                  iconAnchor: [30, 0]
                })
              }).addTo(map);

              m.on('click', () => {
                trackedBusId = null;
                document.getElementById('bus-info').innerHTML =
                  `Stop: ${s.stop_name} | Driving to: ${s.trip_headsign || 'n/a'}`;
              });

              stopMarkers.push(m);
            }
          }

          // Draw buses
          for (const [id, b] of Object.entries(buses)) {
            if (!b.lat || !b.lon) continue;

            const route = b.route_id || '?';
            const busNo = b.vehicleNo || '?';
            const angle = (b.angle || 0) - 90;

            let color = "green";
            if (b.delay !== undefined && !isNaN(Number(b.delay))) {
                const d = Number(b.delay);
                if (d > 60) color = "red";
                else if (d > 0) color = "yellow";
            }

            const speedText = (b.speed !== undefined) ? b.speed + " km/h" : "";

            const iconHtml = `
              <div style="text-align:center;">
                <div style="color:${color}; font-weight:bold; font-size:12px;">${route} / ${busNo}</div>
                <div class="bus-label" style="color:${color}; transform: rotate(${angle}deg);">➤</div>
              </div>
            `;

            const icon = L.divIcon({
              className: '',
              html: iconHtml,
              iconSize: [50, 50],
              iconAnchor: [25, 25]
            });

            if (!busMarkers[id]) {
              busMarkers[id] = L.marker([b.lat, b.lon], { icon }).addTo(map);

              busMarkers[id].on('click', () => {
                trackedBusId = id;
                document.getElementById('bus-info').innerHTML =
                  `Route / Bus: ${route} / ${busNo} | Delay: ${b.delay || 'n/a'} | Speed: ${speedText} | Stop: ${b.stop_name || 'n/a'} | Driving to: ${b.trip_headsign || 'n/a'}`;
              });

            } else {
              busMarkers[id].setLatLng([b.lat, b.lon]);
              busMarkers[id].setIcon(icon);
            }
          }

          // Auto-track selected bus
          if (trackedBusId && busMarkers[trackedBusId]) {
            const bus = buses[trackedBusId];
            if (bus) {
              map.setView([bus.lat, bus.lon], map.getZoom(), { animate: true });
              const speedText = (bus.speed !== undefined) ? bus.speed + " km/h" : "";
              document.getElementById('bus-info').innerHTML =
                `Route / Bus: ${bus.route_id || '?'} / ${bus.vehicleNo || '?'} | Delay: ${bus.delay || 'n/a'} | Speed: ${speedText} | Stop: ${bus.stop_name || 'n/a'} | Driving to: ${bus.trip_headsign || 'n/a'}`;
            }
          }
        }

        update();
        setInterval(update, 3500);
      </script>
    </body>
    </html>
    """
    return render_template_string(html)

@app.route("/api/buses")
def api_buses():
    return jsonify(latest_buses)

@app.route("/api/stops")
def api_stops():
    return jsonify(latest_stops)

if __name__ == "__main__":
    threading.Thread(target=updater, daemon=True).start()
    print("🌍 Running on http://localhost:5000")
    app.run(host="0.0.0.0", port=5000, threaded=True)