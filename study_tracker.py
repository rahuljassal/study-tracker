#!/usr/bin/env python3
"""Local study tracker. Run: python3 study_tracker.py
Needs only Python 3 (no installs). Data lives in tracker.db next to this file."""
import json, os, re, sqlite3, datetime, webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(HERE, "tracker.db")
PORT = 8765

# First-run sample playlist, in "title|duration|youtube_id" form.
SEED = """Ultimate LLD & HLD Roadmap|11:04|rliSgjoOFTs
What is LLD|17:18|mQM3V8E13yc
SOLID Principles|19:03|XI7zep97c-Y
Liskov Substitution Principle (LSP)|8:56|129QkkXUHeQ
Strategy Pattern|17:26|u8DttUrXtEw
Observer Pattern|34:34|Ep9_Zcgst3U
Decorator Pattern|23:00|w6a9MXUwcfY
Factory vs Abstract Factory|12:19|7g9S371qzwM
Parking Lot|56:05|MtjZf7291zc
Tic Tac Toe|19:51|x8N3fINNdTE
Elevator System|40:11|9ORcPv_Tbz8
Car Rental System|36:56|J4GO6hmR6TA
Logging System (Chain of Responsibility)|15:08|gvIn5QBdGDk
Snake and Ladder|31:35|88bcV-XV0wo
HashMap Internals in Java|30:09|AsAymWn7D40
Proxy Pattern|11:49|9MxHKlVc6ZM
BookMyShow|35:57|wCyzvDn3Pp8
Concurrency Control in Distributed Systems|1:04:45|D3XhDu--uoI
Null Object Pattern|12:04|iDPhxhamuTo
Vending Machine (State Pattern)|45:31|wOXs5Z_z0Ew
ATM|44:32|JH7gcXeR3ds
Chess Game (Mock Interview)|1:07:24|kk6QkWxz5jM
File System (Composite Pattern)|21:30|FLkCkUY7Wu0
Adapter Pattern|16:45|8wrg7IsILhQ
Splitwise|50:04|I4xf4STXgmU
Splitwise Simplify Debt Algorithm|32:07|6UeDb7ORVPI
Builder Pattern|26:34|qOLRxN5eVC0
Cricbuzz / CricInfo|38:32|P0TJIONZi8E
Facade Pattern|23:23|GYaBXK54eLo
Bridge Pattern|19:11|SOw1_W0taBg
All Creational Patterns|28:49|OuNOyFg942M
Double-Checked Locking Bug in Singleton|19:59|upfrQvOgC24
Inventory Management System|39:24|DDKdMTFNvxc
Word Processor (Flyweight Pattern)|31:03|Mwm6tB3x1do
Undo/Redo (Command Pattern)|25:00|E1lce5CWhE0
All Structural Patterns|51:14|WxGtmIBZszk
Iterator Pattern|18:28|X7shKHOaYtU
Online Auction (Mediator Pattern)|20:00|bKM2lFPPmmY
Coupons on Shopping Cart|18:50|EfQesfKZ3Jw
Visitor Pattern|33:16|pDsz-AuFO0g
MVC Pattern|14:47|lJBbvb7p__o
Memento Pattern|14:46|nTo7e2lpGZ4
Template Method Pattern|13:29|kwy-G1DEm0M
Interpreter Pattern|16:35|fFlPm0pzQYI
All Behavioral Patterns|47:07|DBDnUkTobaE
Payment Gateway|47:09|Qcr3FhS2vDQ
Object Pool Pattern|19:33|obmc24IHqew
Meeting Scheduler (Mock Interview)|37:23|MRx40JVmmF4"""


def today():
    return datetime.date.today().isoformat()


def db():
    c = sqlite3.connect(DB)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA foreign_keys=ON")
    return c


def secs(d):
    if d.upper() == "NA":
        return 0
    return sum(int(x) * 60 ** i for i, x in enumerate(reversed(d.split(":"))))


def parse(text):
    """Lines like: 01 | Title | 11:04 | https://...  (yt-dlp output). Index optional."""
    out = []
    for line in text.splitlines():
        p = [x.strip() for x in line.split(" | ")]
        if len(p) < 3 or not re.fullmatch(r"[\d:]+|NA", p[-2], re.I):
            continue
        rest = p[:-2]
        if len(rest) > 1 and rest[0].isdigit():
            rest = rest[1:]
        out.append((rest[0], secs(p[-2]), p[-1]))
    return out


def add_playlist(c, name, start, per_day, items):
    if not items:
        raise ValueError("No videos found. Each line needs: title | duration | url")
    cur = c.execute("insert into playlists(name,start_date,per_day) values(?,?,?)",
                    (name, start, max(1, per_day)))
    c.executemany("insert into videos(playlist_id,pos,title,dur,url) values(?,?,?,?,?)",
                  [(cur.lastrowid, i, t, d, u) for i, (t, d, u) in enumerate(items)])


def init():
    fresh = not os.path.exists(DB)
    c = db()
    c.executescript("""
      create table if not exists playlists(id integer primary key, name text,
        start_date text, per_day integer default 1);
      create table if not exists videos(id integer primary key,
        playlist_id integer references playlists(id) on delete cascade,
        pos integer, title text, dur integer, url text, done_at text);""")
    if fresh:
        items = [(t, secs(d), "https://www.youtube.com/watch?v=" + i)
                 for t, d, i in (l.split("|") for l in SEED.splitlines())]
        add_playlist(c, "LLD: Concept && Coding", today(), 1, items)
    c.commit()
    c.close()


def data():
    c = db()
    out = []
    for p in c.execute("select * from playlists order by id"):
        v = [dict(r) for r in c.execute(
            "select id,title,dur,url,done_at from videos where playlist_id=? order by pos", (p["id"],))]
        out.append({**dict(p), "videos": v})
    c.close()
    return out


class H(BaseHTTPRequestHandler):
    def reply(self, body, ctype="application/json", code=200):
        b = body.encode() if isinstance(body, str) else body
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def do_GET(self):
        if self.path == "/api/data":
            self.reply(json.dumps(data()))
        else:
            self.reply(PAGE, "text/html; charset=utf-8")

    def do_POST(self):
        # JSON content-type forces a CORS preflight, so other websites can't write here.
        if not self.headers.get("Content-Type", "").startswith("application/json"):
            return self.reply('{"error":"bad request"}', code=415)
        j = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
        c = db()
        try:
            p = self.path
            if p == "/api/add":
                add_playlist(c, j.get("name") or "Untitled", j.get("start") or today(),
                             int(j.get("per_day") or 1), parse(j.get("text", "")))
            elif p == "/api/toggle":
                c.execute("update videos set done_at = case when done_at is null then ? else null end where id=?",
                          (today(), j["id"]))
            elif p == "/api/update":
                c.execute("update playlists set start_date=?, per_day=? where id=?",
                          (j["start"], max(1, int(j["per_day"])), j["id"]))
            elif p == "/api/delete":
                c.execute("delete from playlists where id=?", (j["id"],))
            c.commit()
            self.reply('{"ok":true}')
        except Exception as e:
            self.reply(json.dumps({"error": str(e)}), code=400)
        finally:
            c.close()

    def log_message(self, *a):
        pass


PAGE = r'''<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Study Tracker</title>
<style>
:root{--bg:#f2f5f7;--card:#fff;--ink:#14202b;--mute:#5d6b78;--line:#dbe3e9;--acc:#0b7a86;--accbg:#d8eef0;--warn:#b4531a}
@media(prefers-color-scheme:dark){:root{--bg:#10161c;--card:#18212a;--ink:#e6edf2;--mute:#8fa0ae;--line:#2a3743;--acc:#3cc2cf;--accbg:#143d43;--warn:#f0a066}}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.5 system-ui,-apple-system,"Segoe UI",sans-serif}
main{max-width:780px;margin:0 auto;padding:20px 16px 48px}
h1{font-size:20px;margin:0}.mute{color:var(--mute);font-size:13px}
.card{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:16px;margin-top:12px}
.big{font:600 52px/1 ui-monospace,Menlo,monospace;letter-spacing:-2px}.big small{font-size:22px;color:var(--mute);letter-spacing:0}
.bar{height:12px;background:var(--accbg);border-radius:6px;overflow:hidden;margin:12px 0 6px}.bar i{display:block;height:100%;background:var(--acc)}
.stats{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:10px;margin-top:12px}
.stat{background:var(--card);border:1px solid var(--line);border-radius:6px;padding:8px 12px}.stat span{display:block;color:var(--mute);font-size:12px}.stat b{font-size:16px}
.row{display:flex;flex-wrap:wrap;gap:8px;align-items:center;margin-top:12px}.sp{flex:1}
input,button,textarea{font:inherit;font-size:13px;color:var(--ink);background:var(--card);border:1px solid var(--line);border-radius:6px;padding:6px 10px}
button{cursor:pointer}button.on{background:var(--acc);border-color:var(--acc);color:var(--bg);font-weight:600}
button:focus-visible,input:focus-visible,textarea:focus-visible,a:focus-visible,summary:focus-visible{outline:2px solid var(--acc);outline-offset:2px}
input[type=number]{width:60px}textarea{width:100%;height:120px;font-family:ui-monospace,Menlo,monospace;font-size:12px}
ul{list-style:none;margin:12px 0 0;padding:0;background:var(--card);border:1px solid var(--line);border-radius:10px;overflow:hidden}
li{display:flex;gap:12px;align-items:center;padding:9px 14px;border-bottom:1px solid var(--line)}li:last-child{border:0}
li.done a{color:var(--mute);text-decoration:line-through}li.nx{background:var(--accbg)}
li input{width:20px;height:20px;accent-color:var(--acc);padding:0}
.d{font:600 12px ui-monospace,Menlo,monospace;color:var(--mute);width:62px;flex:none}.m{flex:1;min-width:0}
a{color:var(--ink);text-decoration:none;overflow-wrap:anywhere}a:hover{color:var(--acc);text-decoration:underline}
.meta{display:block;font-size:12px;color:var(--mute)}.warn{color:var(--warn)}.ok{color:var(--acc)}
summary{cursor:pointer;font-weight:600}label{display:block;font-size:12px;color:var(--mute);margin-top:10px}
code{font-size:12px;background:var(--bg);padding:2px 4px;border-radius:4px;overflow-wrap:anywhere}
</style></head><body><main>
<h1>Study Tracker</h1>
<div class="mute" id="all"></div>
<div class="row" id="tabs"></div>

<div id="view">
 <section class="card">
  <div class="big"><span id="n">0</span><small id="of"></small></div>
  <div class="bar"><i id="fill"></i></div>
  <div class="mute" id="pct"></div>
  <div id="next" style="margin-top:10px"></div>
 </section>
 <div class="stats" id="stats"></div>
 <div class="row">
  <label style="margin:0">Start <input type="date" id="start"></label>
  <label style="margin:0">Videos/day <input type="number" id="per" min="1"></label>
  <span class="sp"></span>
  <button data-f="all" class="on">All</button><button data-f="todo">To do</button><button data-f="done">Done</button>
  <button id="del">Delete playlist</button>
 </div>
 <ul id="list"></ul>
</div>

<details class="card" id="addbox">
 <summary>Add a playlist</summary>
 <label>Name</label><input id="an" style="width:100%" placeholder="e.g. System Design HLD">
 <div class="row"><label style="margin:0">Start <input type="date" id="as"></label>
 <label style="margin:0">Videos/day <input type="number" id="ap" min="1" value="1"></label></div>
 <label>Paste videos, one per line: <code>index | title | duration | url</code> (index optional)</label>
 <textarea id="at" spellcheck="false"></textarea>
 <p class="mute">Get these lines with:<br><code>yt-dlp --flat-playlist --print "%(playlist_index)s | %(title)s | %(duration_string)s | %(url)s" "PLAYLIST_URL"</code></p>
 <button class="on" id="addbtn">Add playlist</button>
</details>
</main>
<script>
let D=[],sel=null,flt="all";
const $=s=>document.querySelector(s);
const esc=s=>s.replace(/[&<>"]/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));
const iso=d=>d.getFullYear()+"-"+String(d.getMonth()+1).padStart(2,"0")+"-"+String(d.getDate()).padStart(2,"0");
const pd=s=>{const a=s.split("-");return new Date(+a[0],+a[1]-1,+a[2])};
const add=(d,n)=>{const x=new Date(d);x.setDate(x.getDate()+n);return x};
const fmt=(d,y)=>d.toLocaleDateString("en-IN",y?{day:"numeric",month:"short",year:"numeric"}:{day:"numeric",month:"short"});
const hm=s=>{const h=Math.floor(s/3600),m=Math.round(s%3600/60);return h?h+"h "+m+"m":m+"m"};
const api=async(p,b)=>{const r=await fetch("/api/"+p,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(b||{})});const j=await r.json();if(!r.ok)alert(j.error||"Request failed");return r.ok};
const stat=(l,v)=>`<div class="stat"><span>${l}</span><b>${v}</b></div>`;
async function load(){D=await(await fetch("/api/data")).json();if(!D.find(p=>p.id==sel))sel=D.length?D[0].id:null;draw()}

function draw(){
 const T=new Date();T.setHours(0,0,0,0);
 const cnt=p=>p.videos.filter(v=>v.done_at).length;
 const tot=D.reduce((a,p)=>a+p.videos.length,0),dn=D.reduce((a,p)=>a+cnt(p),0);
 $("#all").textContent=D.length?`${D.length} playlist${D.length>1?"s":""} · ${dn}/${tot} videos done overall`:"No playlists yet. Add one below.";
 $("#tabs").innerHTML=D.map(p=>`<button data-p="${p.id}" class="${p.id==sel?"on":""}">${esc(p.name)} · ${cnt(p)}/${p.videos.length}</button>`).join("");
 const p=D.find(x=>x.id==sel);
 $("#view").style.display=p?"":"none";
 if(!p)return;
 const V=p.videos,N=V.length,n=cnt(p),left=N-n,per=p.per_day,st=pd(p.start_date);
 $("#n").textContent=n;$("#of").textContent=" / "+N+" videos";
 $("#fill").style.width=(N?n/N*100:0)+"%";
 $("#pct").textContent=Math.round(N?n/N*100:0)+"% complete · "+left+" left";
 const nx=V.find(v=>!v.done_at);
 $("#next").innerHTML=nx?`Up next: <b>${esc(nx.title)}</b>`:"<b>Playlist complete.</b>";
 const idx=Math.round((T-st)/864e5)+1,sched=Math.max(0,Math.min(N,idx*per)),diff=n-sched;
 const dl=Math.ceil(left/per),base=T>st?T:st,fin=left?add(base,dl-1):null;
 const sA=V.reduce((a,v)=>a+v.dur,0),sD=V.reduce((a,v)=>a+(v.done_at?v.dur:0),0);
 const msg=idx<1?"Starts "+fmt(st):diff>=0?(diff?diff+" ahead":"On track"):-diff+" behind";
 $("#stats").innerHTML=stat("Days to finish",left?dl+" day"+(dl>1?"s":""):"Done")+stat("Finish date",fin?fmt(fin,1):"—")+
  stat("Schedule",`<span class="${idx<1||diff>=0?"ok":"warn"}">${msg}</span>`)+stat("Watch time left",hm(sA-sD)+" of "+hm(sA));
 $("#start").value=p.start_date;$("#per").value=per;
 $("#list").innerHTML=V.map((v,i)=>{
  const d=!!v.done_at;if(flt=="todo"&&d||flt=="done"&&!d)return"";
  const due=add(st,Math.floor(i/per)),late=!d&&due<T;
  return `<li class="${d?"done ":""}${nx&&nx.id==v.id?"nx":""}"><input type="checkbox" data-v="${v.id}" ${d?"checked":""} aria-label="Mark ${i+1} done">
   <span class="d">#${i+1}</span><div class="m"><a href="${esc(v.url)}" target="_blank" rel="noopener">${esc(v.title)}</a>
   <span class="meta">${v.dur?hm(v.dur)+" · ":""}due ${fmt(due)}${late?' <span class="warn">(overdue)</span>':""}${d?" · done "+fmt(pd(v.done_at)):""}</span></div></li>`}).join("")||'<li class="mute">Nothing here.</li>';
}

$("#tabs").onclick=e=>{const b=e.target.closest("[data-p]");if(b){sel=+b.dataset.p;draw()}};
$("#list").onchange=async e=>{if(e.target.dataset.v){await api("toggle",{id:+e.target.dataset.v});load()}};
document.querySelectorAll("[data-f]").forEach(b=>b.onclick=()=>{flt=b.dataset.f;document.querySelectorAll("[data-f]").forEach(x=>x.classList.toggle("on",x==b));draw()});
const upd=async()=>{if($("#start").value&&+$("#per").value>0){await api("update",{id:sel,start:$("#start").value,per_day:+$("#per").value});load()}};
$("#start").onchange=upd;$("#per").onchange=upd;
$("#del").onclick=async()=>{if(confirm("Delete this playlist and its progress?")){await api("delete",{id:sel});load()}};
$("#addbtn").onclick=async()=>{
 const ok=await api("add",{name:$("#an").value.trim(),start:$("#as").value,per_day:+$("#ap").value||1,text:$("#at").value});
 if(ok){$("#an").value=$("#at").value="";$("#addbox").open=false;sel=null;await load();sel=D[D.length-1].id;draw()}};
$("#as").value=iso(new Date());
load();
</script></body></html>'''


if __name__ == "__main__":
    init()
    srv = ThreadingHTTPServer(("127.0.0.1", PORT), H)
    url = "http://127.0.0.1:%d" % PORT
    print("Study Tracker running at", url, "(Ctrl+C to stop)\nData file:", DB)
    webbrowser.open(url)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")