import json, re, time
from datetime import datetime
from zoneinfo import ZoneInfo
import requests
from bs4 import BeautifulSoup

ROOT = "https://www.keiba.go.jp/KeibaWeb/TodayRaceInfo/"
BASE = {"k_babaCode": "27", "k_raceDate": "2026/10/09"}
s = requests.Session()
s.headers.update({"User-Agent": "Sonoda personal forecast; official public race data", "Cache-Control": "no-cache"})
def get(path, params):
    r=s.get(ROOT+path,params=params,timeout=30); r.raise_for_status(); r.encoding=r.apparent_encoding or "utf-8"
    return BeautifulSoup(r.text,"html.parser")
def tx(node): return re.sub(r"\s+"," ",node.get_text(" ",strip=True)) if node else ""
def main():
    menu=get("RaceList",BASE); races={}; scratched={}
    for tr in menu.select("table tr"):
        cells=tr.find_all(["td","th"],recursive=False); line=" ".join(tx(c) for c in cells)
        a=tr.find("a",href=re.compile("DebaTable"))
        if a:
            m=re.search(r"k_raceNo=(\d+)",a.get("href",""))
            if m:
                n=int(m.group(1)); tm=re.search(r"\b(\d{1,2}:\d{2})\b",line); dm=re.search(r"(\d{3,4})m",line)
                races[n]={"title":tx(a),"time":tm.group(1) if tm else "","distance":int(dm.group(1)) if dm else 0,"horses":[],"scratched":[]}
        if "出走取消" in line or "競走除外" in line:
            nums=[int(x) for x in re.findall(r"(?<!\d)\d{1,2}(?!\d)",line)]
            if len(nums)>=2 and 1<=nums[0]<=12 and 1<=nums[1]<=20: scratched.setdefault(nums[0],[]).append(nums[1])
    if len(races)<12: raise RuntimeError("公式レース一覧が12R分そろいません")
    for n,race in races.items():
        card=get("DebaTable",{**BASE,"k_raceNo":str(n)})
        summary=tx(card.find("main"))[:2000]
        for label,key,pattern in [("天候","weather","(晴|曇|雨|雪)"),("馬場","going","(不良|稍重|良|重)")]:
            m=re.search(label+r"[:：]\s*"+pattern,summary)
            if m: race[key]=m.group(1)
        for tr in card.select("table tr"):
            horse=tr.find("a",href=re.compile("HorseMark"))
            if not horse: continue
            td=tr.find_all(["td","th"],recursive=False)
            if len(td)<5: continue
            num=re.search(r"\d+",tx(td[1]))
            if not num: continue
            jockey=tr.find("a",href=re.compile("RiderMark")); details=tx(td[4])
            bw=re.search(r"(\d{3,4})\s*[（(]\s*([+＋\-−]?\d+)",details)
            odds=re.search(r"(\d+(?:\.\d+)?)\s*倍",details)
            item={"no":int(num.group()),"name":tx(horse),"jockey":tx(jockey),"odds":float(odds.group(1)) if odds else 0,"bodyWeight":int(bw.group(1)) if bw else 0,"bodyDelta":int(bw.group(2).replace("＋","+").replace("−","-")) if bw else 0}
            if not any(x["no"]==item["no"] for x in race["horses"]): race["horses"].append(item)
        race["scratched"]=sorted(set(scratched.get(n,[])))
        race["horses"]=[{**h,"scratched":h["no"] in race["scratched"]} for h in race["horses"]]
        # Official win odds page; card data remains available when odds have not opened yet.
        try:
            odds_page=get("OddsTanFukuList",{**BASE,"k_raceNo":str(n)})
            for tr in odds_page.select("table tr"):
                cells=tr.find_all(["td","th"],recursive=False)
                if len(cells)<2: continue
                nm=re.match(r"\s*(\d{1,2})\b",tx(cells[0])); om=re.search(r"\b(\d+(?:\.\d+)?)\b", " ".join(tx(c) for c in cells[1:]))
                if nm and om:
                    h=next((x for x in race["horses"] if x["no"]==int(nm.group(1))),None)
                    if h: h["odds"]=float(om.group(1))
        except requests.RequestException: pass
        if not race["horses"]: raise RuntimeError(f"{n}R出馬表から馬が取得できません")
        time.sleep(.1)
    data={"date":"2026-10-09","track":"園田","source":"地方競馬情報サイト（NAR）","sourceUrl":"https://www.keiba.go.jp/KeibaWeb/TodayRaceInfo/RaceList?k_babaCode=27&k_raceDate=2026%2F10%2F09","updatedAt":datetime.now(ZoneInfo("Asia/Tokyo")).isoformat(timespec="seconds"),"races":races}
    import os; os.makedirs("data",exist_ok=True)
    with open("data/official.json","w",encoding="utf-8") as f: json.dump(data,f,ensure_ascii=False,separators=(",",":"))
    print(f"NAR official snapshot: {len(races)} races / {sum(len(x['horses']) for x in races.values())} horses / {data['updatedAt']}")
if __name__=="__main__": main()
