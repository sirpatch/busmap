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
last_update = {}

def fetch_buses_once(city):
    headers = {"User-Agent":"Mozilla/5.0","Origin":BASE,"Referer":city["referer"],"Accept":"*/*"}
    if COOKIE: headers["Cookie"]=COOKIE
    try:
        r=requests.get(SOCKET, headers=headers, timeout=6)
        sid_match=re.search(r'"sid":"([^"]+)"',r.text)
        if not sid_match: return {}
        sid=sid_match.group(1)
        url=f"{SOCKET}&sid={sid}"
        requests.post(url, headers=headers, data=f'40/{city["socket_ns"]},{{}}', timeout=6)
        time.sleep(1)
        r=requests.get(url, headers=headers, timeout=6)
        if f"42/{city['socket_ns']}" not in r.text: return {}
        payload=r.text.split(f"42/{city['socket_ns']},")[1]
        data=json.loads(payload)
        return data[1].get("data",{})
    except Exception as e:
        print(f"[{city['name']}] bus fetch error:",e)
        return {}

def fetch_stops(city):
    headers={"User-Agent":"Mozilla/5.0","Origin":BASE,"Referer":city["referer"],"Accept":"*/*"}
    if COOKIE: headers["Cookie"]=COOKIE
    try:
        r=requests.get(city["stops_url"], headers=headers, timeout=6)
        r.raise_for_status()
        data=r.json()
        stops=data.get("stops",[])
        result=[]
        for s in stops:
            if len(s)>=4:
                result.append({
                    "id":s[0],
                    "name":s[1],
                    "lat":s[2],
                    "lon":s[3],
                    "stop_name":f"{s[1]} - {s[0]}",
                    "trip_headsign": s[4] if len(s) > 4 else ""
                })
        return result
    except Exception as e:
        print(f"[{city['name']}] stop fetch error:", e)
        return []

def updater():
    global latest_buses, latest_stops, last_update, active_city_name
    while True:
        city = next((c for c in cities if c["name"]==active_city_name), None)
        if city:
            buses = fetch_buses_once(city)
            stops = fetch_stops(city)
            if buses:
                latest_buses[city["name"]] = buses
                last_update[city["name"]] = time.time()
            if stops:
                latest_stops[city["name"]] = stops
        time.sleep(4)

@app.route("/")
def index():
    html = """
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8"/>
<title>Bus Tracker CRT Style</title>
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<style>
html,body,#map{height:100%;margin:0;background:#101010;color:#0f0;font-family:'Courier New',monospace;}
.leaflet-container { background:#101010; }
.bus-label { font-size:14px;color:#0f0;text-align:center;display:block;margin-top:2px; }
.stop-label { font-size:12px;color:#00ffff;text-align:center;font-weight:bold;text-shadow:0 0 2px black; }
#bus-info { position: fixed; bottom:0; left:0; width:100%; background: rgba(0,0,0,0.85); color:#0f0; font-size:14px; padding:6px 10px; z-index:9999; border-top:1px solid #0f0; }
#bus-marquee { position: fixed; top:0; left:0; width:100%; background: rgba(0,0,0,0.85); color:#0f0; font-size:14px; white-space: nowrap; overflow:hidden; z-index:9999; padding:5px 10px; border-bottom:1px solid #0f0; }
#bus-marquee span { display:inline-block; padding-right:50px; }
#stats { position: fixed; top:30px; right:10px; background: rgba(0,0,0,0.7); color:#0f0; font-size:14px; padding:6px 10px; border-radius:5px; z-index:9999; border:1px solid #0f0; }
#menu-container { position: fixed; top:70px; right:10px; z-index:9999; }
#menu-toggle { background: rgba(0,0,0,0.7); color:#0f0; border:1px solid #0f0; padding:5px 10px; border-radius:5px; cursor:pointer; font-weight:bold; }
#menu { margin-top:5px; background: rgba(0,0,0,0.85); color:#0f0; padding:10px; border-radius:5px; display:none; border:1px solid #0f0; }
#menu label { display:block; margin-bottom:5px; cursor:pointer; }
#toggle-stops { position: fixed; bottom: 20px; right: 20px; z-index: 9999; background: rgba(0,0,0,0.7); color:#0f0; border:1px solid #0f0; padding:5px 10px; border-radius:5px; cursor:pointer; font-weight:bold; }
@keyframes rgbGlow {
  0% { text-shadow:0 0 8px red,0 0 15px red; }
  25% { text-shadow:0 0 8px lime,0 0 15px yellow; }
  50% { text-shadow:0 0 8px cyan,0 0 15px lightblue; }
  75% { text-shadow:0 0 8px magenta,0 0 15px violet; }
  100% { text-shadow:0 0 8px red,0 0 15px orange; }
}
</style>
</head>
<body>
<div id="bus-marquee"><div id="marquee-inner" style="display:inline-block;white-space:nowrap;"></div></div>
<div id="map"></div>
<div id="bus-info">Click a bus or stop to see info...</div>
<div id="stats">Buses driving: 0</div>
<div id="menu-container">
  <button id="menu-toggle">Select city</button>
  <div id="menu">
    {% for c in cities %}
      <label><input type="radio" name="city" class="city-radio" value="{{c}}" {% if loop.first %}checked{% endif %}> {{c}}</label>
    {% endfor %}
  </div>
</div>
<button id="toggle-stops">Hide Stops</button>
<script>
const toggleBtn=document.getElementById("menu-toggle");
const menu=document.getElementById("menu");
toggleBtn.addEventListener("click",()=>{menu.style.display=(menu.style.display==="none")?"block":"none";});

let activeCity=document.querySelector('.city-radio:checked').value;
document.querySelectorAll('.city-radio').forEach(cb=>cb.addEventListener('change',()=>{if(cb.checked)setActiveCity(cb.value);}));

const map=L.map('map').setView([52,19],6);
L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_nolabels/{z}/{x}/{y}{r}.png',{maxZoom:19}).addTo(map);
L.tileLayer('https://{s}.basemaps.cartocdn.com/light_only_labels/{z}/{x}/{y}{r}.png').addTo(map);

let busMarkers={},stopMarkers=[],trackedBusId=null,stopsVisible=true;
const marqueeInner=document.getElementById("marquee-inner");
let marqueeX=window.innerWidth;
function animateMarquee(){marqueeX-=0.5;if(marqueeX<-marqueeInner.offsetWidth)marqueeX=window.innerWidth;marqueeInner.style.transform=`translateX(${marqueeX}px)`;requestAnimationFrame(animateMarquee);}
animateMarquee();

document.getElementById('toggle-stops').addEventListener('click',()=>{
    stopsVisible=!stopsVisible;
    stopMarkers.forEach(m=>stopsVisible?map.addLayer(m):map.removeLayer(m));
    document.getElementById('toggle-stops').innerText=stopsVisible?'Hide Stops':'Show Stops';
});

function setActiveCity(city){
    activeCity=city;
    fetch('/api/set_city?city='+city);
    for(let id in busMarkers)map.removeLayer(busMarkers[id]);
    busMarkers={};
    stopMarkers.forEach(m=>map.removeLayer(m));
    stopMarkers=[];
    trackedBusId=null;
    marqueeInner.textContent="";
    const cData={{cities|tojson}};
    const cityInfo=cData.find(c=>c.name===city);
    if(cityInfo)map.setView(cityInfo.center,cityInfo.zoom);
}

function delayColor(delay){
    if (delay < 0) return "pink";
    else if (delay < 30) return "green";
    else if(delay < 60) return "yellow";
    else if(delay < 90) return "orange";
    else if(delay < 240) return "red";
    else if(delay < 3600) return "black";
    return "white";
}

async function update(){
    const [busRes,stopRes]=await Promise.all([fetch('/api/buses'),fetch('/api/stops')]);
    const buses=(await busRes.json())[activeCity]||{};
    const stops=(await stopRes.json())[activeCity]||[];

    document.getElementById('stats').innerHTML="Buses driving: "+Object.keys(buses).length;

    const delayedBuses=Object.values(buses).filter(b=>b.delay>30);
    marqueeInner.textContent=delayedBuses.map(b=>`   ${b.route_id||'?'} / ${b.vehicleNo||'?'} | Delay: ${b.delay}s | Stop: ${b.stop_name||'n/a'} | Driving to: ${b.trip_headsign||'n/a'}   |||`).join("   ");

    if(stopMarkers.length===0){
        stops.forEach(s=>{
            const m=L.marker([s.lat,s.lon],{icon:L.divIcon({className:'stop-label',html:`🚏<br>${s.stop_name}`,iconSize:[60,25],iconAnchor:[30,0]})});
            m.addTo(map);
            m.on('click',()=>{trackedBusId=null;document.getElementById('bus-info').innerHTML=`Stop: ${s.stop_name} | Driving to: ${s.trip_headsign||'n/a'}`;});
            stopMarkers.push(m);
        });
    }

    for(const [id,b] of Object.entries(buses)){
        if(!b.lat||!b.lon)continue;
        const route=b.route_id||'?'; const busNo=b.vehicleNo||'?'; const angle=(b.angle||0)-90;
        const color=delayColor(b.delay||0);
        const iconHtml=`
<div style="text-align:center;">
  <div style="font-size:26px; transform: rotate(${angle}deg); color:${color}; animation: rgbGlow 4s infinite linear;">➤</div>
  <div class="bus-label" style="color:${color};">${route} / ${busNo}</div>
</div>`;
        const icon=L.divIcon({className:'',html:iconHtml,iconSize:[50,50],iconAnchor:[25,25]});
        if(!busMarkers[id]){
            busMarkers[id]=L.marker([b.lat,b.lon],{icon}).addTo(map);
            busMarkers[id].on('click',()=>{
                trackedBusId=id;
                document.getElementById('bus-info').innerHTML=`Route / Bus: ${route} / ${busNo} | Status: ${b.current_status||'n/a'} | Stop: ${b.stop_name||'n/a'} | Driving to: ${b.trip_headsign||'n/a'} | Delay: ${b.delay||'n/a'} | Speed: ${b.speed||'n/a'}`;
            });
        }else{
            busMarkers[id].setLatLng([b.lat,b.lon]);
            busMarkers[id].setIcon(icon);
        }
    }

    if(trackedBusId && buses[trackedBusId]){
        const b=buses[trackedBusId];
        document.getElementById('bus-info').innerHTML=`Route / Bus: ${route} / ${busNo} | Status: ${b.current_status||'n/a'} | Stop: ${b.stop_name||'n/a'} | Driving to: ${b.trip_headsign||'n/a'} | Delay: ${b.delay||'n/a'} | Speed: ${b.speed||'n/a'}`;
        map.setView([b.lat,b.lon],map.getZoom(),{animate:true});
    }
}

update();
setInterval(update,3500);
map.on('click',()=>{trackedBusId=null;document.getElementById('bus-info').innerHTML="Click a bus or stop to see info...";});
</script>
</body>
</html>
    """
    return render_template_string(html, cities=[c["name"] for c in cities])

@app.route("/api/buses")
def api_buses():
    return jsonify({active_city_name: latest_buses.get(active_city_name, {})})

@app.route("/api/stops")
def api_stops():
    return jsonify({active_city_name: latest_stops.get(active_city_name, [])})

@app.route("/api/set_city")
def set_city():
    global active_city_name
    city=request.args.get("city")
    if city in [c["name"] for c in cities]:
        active_city_name=city
    return jsonify({"active_city":active_city_name})

if __name__=="__main__":
    threading.Thread(target=updater,daemon=True).start()
    print("🌍 Running on http://localhost:5000")
    app.run(host="0.0.0.0",port=5000,threaded=True)
