from flask import Flask, render_template_string, jsonify, request
import requests, re, json, time, threading

app = Flask(__name__)

BASE = "https://czynaczas.pl"
SOCKET = f"{BASE}/socket.io/?EIO=4&transport=polling"

cities = [
    {"name": "zielonagora", "stops_url": f"{BASE}/api/zielonagora/transport", "socket_ns": "zielonagora", "referer": f"{BASE}/zielonagora", "center": [51.94,15.50], "zoom": 13},
    {"name": "wroclaw", "stops_url": f"{BASE}/api/wroclaw/transport", "socket_ns": "wroclaw", "referer": f"{BASE}/wroclaw", "center": [51.11,17.03], "zoom": 13},
    {"name": "warsaw", "stops_url": f"{BASE}/api/warsaw/transport", "socket_ns": "warsaw", "referer": f"{BASE}/warsaw", "center": [52.23,21.01], "zoom": 12},
    {"name": "poznan", "stops_url": f"{BASE}/api/poznan/transport", "socket_ns": "poznan", "referer": f"{BASE}/poznan", "center": [52.41,16.93], "zoom": 13},
    {"name": "kielce", "stops_url": f"{BASE}/api/kielce/transport", "socket_ns": "kielce", "referer": f"{BASE}/kielce", "center": [50.87,20.63], "zoom": 13},
    {"name": "krakow", "stops_url": f"{BASE}/api/krakow/transport", "socket_ns": "krakow", "referer": f"{BASE}/krakow", "center": [50.06,19.94], "zoom": 13},
    {"name": "leszno", "stops_url": f"{BASE}/api/leszno/transport", "socket_ns": "leszno", "referer": f"{BASE}/leszno", "center": [51.84,16.57], "zoom": 13},
    {"name": "lodz", "stops_url": f"{BASE}/api/lodz/transport", "socket_ns": "lodz", "referer": f"{BASE}/lodz", "center": [51.76,19.46], "zoom": 13},
    {"name": "gzm", "stops_url": f"{BASE}/api/gzm/transport", "socket_ns": "gzm", "referer": f"{BASE}/gzm", "center": [50.3,18.67], "zoom": 12},
    {"name": "rzeszow", "stops_url": f"{BASE}/api/rzeszow/transport", "socket_ns": "rzeszow", "referer": f"{BASE}/rzeszow", "center": [50.04,22.00], "zoom": 13},
    {"name": "slupsk", "stops_url": f"{BASE}/api/slupsk/transport", "socket_ns": "slupsk", "referer": f"{BASE}/slupsk", "center": [54.46,17.03], "zoom": 13},
    {"name": "swinoujscie", "stops_url": f"{BASE}/api/swinoujscie/transport", "socket_ns": "swinoujscie", "referer": f"{BASE}/swinoujscie", "center": [53.91,14.25], "zoom": 13},
    {"name": "szczecin", "stops_url": f"{BASE}/api/szczecin/transport", "socket_ns": "szczecin", "referer": f"{BASE}/szczecin", "center": [53.43,14.55], "zoom": 12},
    {"name": "trojmiasto", "stops_url": f"{BASE}/api/trojmiasto/transport", "socket_ns": "trojmiasto", "referer": f"{BASE}/trojmiasto", "center": [54.35,18.65], "zoom": 12},
]

COOKIE = ""
active_city_name = "zielonagora"
latest_buses = {}
latest_stops = {}
lock = threading.Lock()

# --- Fetch buses/stops functions ---
def fetch_buses_once(city):
    headers = {"User-Agent": "Mozilla/5.0", "Origin": BASE, "Referer": city["referer"], "Accept": "*/*"}
    if COOKIE: headers["Cookie"] = COOKIE
    try:
        r = requests.get(SOCKET, headers=headers, timeout=6)
        sid_match = re.search(r'"sid":"([^"]+)"', r.text)
        if not sid_match: return {}
        sid = sid_match.group(1)
        url = f"{SOCKET}&sid={sid}"
        requests.post(url, headers=headers, data=f'40/{city["socket_ns"]},{{}}', timeout=6)
        time.sleep(1)
        r = requests.get(url, headers=headers, timeout=6)
        if f"42/{city['socket_ns']}" not in r.text: return {}
        payload = r.text.split(f"42/{city['socket_ns']},")[1]
        data = json.loads(payload)
        return data[1].get("data", {})
    except Exception as e:
        print(f"[{city['name']}] bus fetch error:", e)
        return {}

def fetch_stops(city):
    headers = {"User-Agent": "Mozilla/5.0", "Origin": BASE, "Referer": city["referer"], "Accept": "*/*"}
    if COOKIE: headers["Cookie"] = COOKIE
    try:
        r = requests.get(city["stops_url"], headers=headers, timeout=6)
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
                    "stop_name": f"{s[1]} - {s[0]}",
                    "trip_headsign": s[4] if len(s) > 4 else ""
                })
        return result
    except Exception as e:
        print(f"[{city['name']}] stop fetch error:", e)
        return []

# --- Background updater ---
def updater():
    global latest_buses, latest_stops, active_city_name
    while True:
        with lock:
            city = next((c for c in cities if c["name"] == active_city_name), None)
        if city:
            buses = fetch_buses_once(city)
            stops = fetch_stops(city)
            if buses: latest_buses[city["name"]] = buses
            if stops: latest_stops[city["name"]] = stops
        time.sleep(4)

# --- Flask routes ---
@app.route("/")
def index():
    html = """
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8"/>
<title>Bus Tracker RGB Glow</title>
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<style>
html,body,#map{height:100%;margin:0;background:#101010;color:#0f0;font-family:'Courier New',monospace;}
.leaflet-container { background:#101010; }
.bus-label { font-size:14px; text-align:center; margin-top:5px; font-weight:bold; }
.stop-label { font-size:12px;color:#00ffff;text-align:center;font-weight:bold;text-shadow:0 0 2px black; }
#bus-info { position: fixed; bottom:0; left:0; width:100%; background: rgba(0,0,0,0.85); color:#0f0; font-size:14px; padding:6px 10px; z-index:9999; border-top:1px solid #0f0; }
#toggle-stops { position: fixed; bottom: 20px; right: 20px; z-index: 9999; background: rgba(0,0,0,0.7); color:#0f0; border:1px solid #0f0; padding:5px 10px; border-radius:5px; cursor:pointer; font-weight:bold; }
#city-menu { position: fixed; top: 30px; right: 20px; z-index: 9999; background: rgba(0,0,0,0.8); color:#0f0; border:1px solid #0f0; border-radius:5px; padding:10px; font-size:14px; }
.city-btn { display:block; margin:4px 0; cursor:pointer; color:#0f0; text-align:center; }
.city-btn:hover { background:#0f0; color:black; }
#marquee {
    position: fixed;
    top: 0;
    left: 0;
    width: 100%;
    overflow: hidden;
    background: rgba(0,0,0,0.8);
    color: #0f0;
    white-space: nowrap;
    border-bottom: 1px solid #0f0;
    z-index: 9999;
}

#marquee span {
    display: inline-block;
    white-space: nowrap;
    padding-right: 50px; /* spacing between repeats */
}

@keyframes scroll-left { 0% { transform: translateX(100%); } 100% { transform: translateX(-100%); } }
@keyframes rgbGlow { 0% { filter: drop-shadow(0 0 3px red); } 25% { filter: drop-shadow(0 0 3px lime); } 50% { filter: drop-shadow(0 0 3px cyan); } 75% { filter: drop-shadow(0 0 3px magenta); } 100% { filter: drop-shadow(0 0 3px red); } }
</style>
</head>
<body>
<div id="marquee"><span>Loading delayed buses...</span></div>
<div id="map"></div>
<div id="bus-info">Click a bus or stop to see info...</div>
<button id="toggle-stops">Hide Stops</button>
<div id="city-menu">
  <div class="city-btn" onclick="switchCity('zielonagora')">Zielona Góra</div>
  <div class="city-btn" onclick="switchCity('wroclaw')">Wrocław</div>
  <div class="city-btn" onclick="switchCity('warsaw')">Warszawa</div>
  <div class="city-btn" onclick="switchCity('poznan')">Poznań</div>
  <div class="city-btn" onclick="switchCity('kielce')">Kielce</div>
  <div class="city-btn" onclick="switchCity('leszno')">Leszno</div>
  <div class="city-btn" onclick="switchCity('lodz')">Lodz</div>
  <div class="city-btn" onclick="switchCity('gzm')">Katowice GZM</div>
  <div class="city-btn" onclick="switchCity('rzeszow')">Rzeszow</div>
  <div class="city-btn" onclick="switchCity('slupsk')">Slupsk</div>
  <div class="city-btn" onclick="switchCity('swinoujscie')">Swinoujscie</div>
  <div class="city-btn" onclick="switchCity('szczecin')">szczecin</div>
  <div class="city-btn" onclick="switchCity('trojmoasto')">Trojmiasto</div>
</div>

<script>
const map=L.map('map').setView([51.94,15.50],13);
L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_nolabels/{z}/{x}/{y}{r}.png',{maxZoom:19}).addTo(map);

let busMarkers={},stopMarkers=[],trackedBusId=null,stopsVisible=true,currentCity='zielonagora',userMarker=null;

let marqueeSpan = document.querySelector("#marquee span");

function updateMarquee(text){
    if(!marqueeSpan){
        marqueeSpan = document.createElement("span");
        document.getElementById("marquee").appendChild(marqueeSpan);
    }

    if(!text || text.trim()==="") text = "No buses delayed over 30s.";

    marqueeSpan.innerText = text;

    // stop previous animation
    marqueeSpan.style.transition = "none";
    marqueeSpan.style.transform = "translateX(100%)";

    // force reflow
    void marqueeSpan.offsetWidth;

    const totalWidth = marqueeSpan.offsetWidth + document.getElementById("marquee").offsetWidth;
    const duration = Math.max(totalWidth / 50, 5); // speed in seconds

    // apply animation
    marqueeSpan.style.transition = `transform ${duration}s linear`;
    marqueeSpan.style.transform = `translateX(-${marqueeSpan.offsetWidth}px)`;
}

function delayColor(delay){
  if (delay < 0) return "blue";
  else if (delay === 0) return "white";
  else if (delay < 30) return "green";
  else if (delay < 60) return "yellow";
  else if (delay < 90) return "orange";
  else if (delay < 240) return "red";
  else return "darkred";
}

document.getElementById('toggle-stops').addEventListener('click',()=>{
  stopsVisible=!stopsVisible;
  stopMarkers.forEach(m=>stopsVisible?map.addLayer(m):map.removeLayer(m));
  document.getElementById('toggle-stops').innerText=stopsVisible?'Hide Stops':'Show Stops';
});

function clearMap(){
  Object.values(busMarkers).forEach(m=>map.removeLayer(m));
  stopMarkers.forEach(m=>map.removeLayer(m));
  busMarkers={}; stopMarkers=[]; trackedBusId=null;
}

async function switchCity(name){
  if(name===currentCity)return;
  clearMap();
  currentCity=name;
  document.getElementById('bus-info').innerText='Loading '+name+'...';
  await fetch('/set_city',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({name})});
  const cityData={'zielonagora':[51.94,15.50,13],'wroclaw':[51.11,17.03,13],'warsaw':[52.23,21.01,12],'poznan':[52.41,16.93,13],'krakow':[50.06,19.94,13]};
  const c=cityData[name];
  map.setView([c[0],c[1]],c[2]);
  setTimeout(update,1000);
}

// User GPS
if (navigator.geolocation){
    navigator.geolocation.watchPosition(pos=>{
        const lat=pos.coords.latitude, lon=pos.coords.longitude;
        if(!userMarker){
            userMarker = L.circleMarker([lat,lon],{radius:8,color:'cyan',fillColor:'cyan',fillOpacity:0.8}).addTo(map);
        } else {
            userMarker.setLatLng([lat,lon]);
        }
    }, err=>console.warn(err));
}

async function update(){
  const [busRes,stopRes]=await Promise.all([
    fetch('/api/buses?city='+currentCity),
    fetch('/api/stops?city='+currentCity)
  ]);
  const buses=(await busRes.json())[currentCity]||{};
  const stops=(await stopRes.json())[currentCity]||[];

  if(stopMarkers.length===0){
    stops.forEach(s=>{
      const m=L.marker([s.lat,s.lon],{icon:L.divIcon({className:'stop-label',html:`🚏<br>${s.stop_name}`,iconSize:[60,25],iconAnchor:[30,0]})});
      m.addTo(map);
      m.on('click',()=>{trackedBusId=null;document.getElementById('bus-info').innerHTML=`Stop: ${s.stop_name}`;});
      stopMarkers.push(m);
    });
  }

  let delayedBuses=[];
  Object.entries(buses).forEach(([id,b])=>{
    if(!b.lat||!b.lon)return;
    const route=b.route_id||'?', busNo=b.vehicleNo||'?', angle=(b.angle||0)-90;
    const color=delayColor(b.delay||0);
    if(b.delay>30) delayedBuses.push(`${route}/${busNo} | Delay: ${b.delay}s | Stop: ${b.stop_name||'n/a'} | Driving to: ${b.trip_headsign||'n/a'}`);

    const iconHtml=`<div style="text-align:center;">
      <div style="font-size:30px; transform: rotate(${angle}deg); color:${color}; animation: rgbGlow 2s infinite linear;">➤</div>
      <div class="bus-label" style="color:${color};">${route} / ${busNo}</div>
    </div>`;
    const icon=L.divIcon({className:'',html:iconHtml,iconSize:[60,60],iconAnchor:[30,20]});

    if(!busMarkers[id]){
      busMarkers[id]=L.marker([b.lat,b.lon],{icon}).addTo(map);
      busMarkers[id].on('click',()=>{
        trackedBusId=id;
        document.getElementById('bus-info').innerHTML=`Bus: ${route} / ${busNo} | Status: ${b.current_status||'n/a'} | Driving to: ${b.trip_headsign||'n/a'} | Stop: ${b.stop_name||'n/a'} | Delay: ${b.delay}s | Speed: ${b.speed||'n/a'}km/h`;
      });
    } else {
      busMarkers[id].setLatLng([b.lat,b.lon]);
      busMarkers[id].setIcon(icon);
    }

    if(trackedBusId===id){
      document.getElementById('bus-info').innerHTML=`Bus: ${route} / ${busNo} | Status: ${b.current_status||'n/a'} | Driving to: ${b.trip_headsign||'n/a'} | Stop: ${b.stop_name||'n/a'} | Delay: ${b.delay}s | Speed: ${b.speed||'n/a'}km/h`;
    }
  });

  if(trackedBusId && buses[trackedBusId]){
    const b=buses[trackedBusId];
    map.setView([b.lat,b.lon],map.getZoom(),{animate:true});
  }

  updateMarquee(delayedBuses.length>0 ? delayedBuses.join("   •   ") : "No buses delayed over 30s.");
}

update();
setInterval(update,4000);
map.on('click',()=>{trackedBusId=null;document.getElementById('bus-info').innerHTML="Click a bus or stop to see info...";});
</script>
</body>
</html>
    """
    return render_template_string(html)

@app.route("/api/buses")
def api_buses():
    city = request.args.get("city", active_city_name)
    with lock:
        return jsonify({city: latest_buses.get(city, {})})

@app.route("/api/stops")
def api_stops():
    city = request.args.get("city", active_city_name)
    with lock:
        return jsonify({city: latest_stops.get(city, [])})

@app.route("/set_city", methods=["POST"])
def set_city():
    global active_city_name
    data = request.get_json()
    name = data.get("name")
    if name not in [c["name"] for c in cities]:
        return jsonify({"error": "unknown city"}), 400
    with lock:
        active_city_name = name
    print(f"🟢 City changed to: {active_city_name}")
    return jsonify({"ok": True})

if __name__ == "__main__":
    threading.Thread(target=updater, daemon=True).start()
    print("🌍 Running on http://localhost:5000")
    app.run(host="0.0.0.0", port=5000, threaded=True)
