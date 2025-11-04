There are 2 files.
One is for hosting bus data (json_host.py)
Second one is for hosting simple map website on localhost with all neccessary data to show bus and stops locations. (bus_map.py)

both files will work as long as czynaczas.pl don't change anything related to this data...

To start files You need flask and requests.
that's all

I also provide this data world-wide on my website.

Data updates as fast as possible (every 2 - 15 seconds)
If You make request every 2 seconds nothing will change untill czynaczas.pl data will be updated.

# IMPORTANT NOTE ABOUT PUBLIC API

Im working on hosting it...
Not YET available...

# Zielona Gora API - SELF HOST
1. bus data: http://127.0.0.1:5000/busproject/zielonagora_bus_data.json
2. stops: http://127.0.0.1:5000/busproject/zielonagora_stop.json

# Other cities
1. bus data: https://api.patched.cc/busproject/CITY_bus_data.json
2. stops: https://api.patched.cc/busproject/CITY_stop.json

Just insert Your city in CITY and it should work.

# Supported cities:
1. Zielona Gora
2. Wroclaw
3. Warsaw
4. Poznan
5. Kielce
6. Krakow
7. Leszno
8. Lodz
9. Katowice GZM
10. Rzeszow
11. Slupsk
12. Swinoujscie
13. Szczecin
14. Trojmiasto

Have fun and Thanks :)
