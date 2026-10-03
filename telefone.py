from flask import Flask, request, jsonify
import threading
import time

app = Flask(__name__)

@app.after_request
def after_request(response):
    response.headers.add('Access-Control-Allow-Origin', '*')
    response.headers.add('Access-Control-Allow-Headers', '*')
    response.headers.add('Access-Control-Allow-Methods', '*')
    return response

HTML_CALL = """
<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1">
<title>ZION</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{background:#0a0a0a;color:white;font-family:-apple-system,BlinkMacSystemFont,Segoe UI; height:100dvh; display:flex; flex-direction:column; align-items:center; justify-content:space-between; padding:20px 0 40px; overflow:hidden}
.top{width:100%; display:flex; justify-content:space-between; padding:0 30px; font-size:15px; opacity:0.8}
.center{display:flex; flex-direction:column; align-items:center; margin-top:40px}
h1{font-size:52px; font-weight:800; letter-spacing:6px}
.sub{margin-top:8px; color:#9ca3af; font-size:15px}
#wave{width:320px; height:320px; margin:50px 0; border-radius:50%; background:radial-gradient(circle at center, rgba(34,197,94,0.15) 0%, transparent 70%); display:flex; align-items:center; justify-content:center; position:relative}
#wave canvas{width:100%; height:100%; border-radius:50%}
#wave.pulsing{box-shadow:0 0 80px rgba(34,197,94,0.6)}
.timer{font-size:24px; color:#d1d5db; letter-spacing:1px; margin-top:20px}
.controls{width:100%; display:flex; justify-content:space-around; align-items:center; padding:0 30px; max-width:400px}
.btn{width:72px; height:72px; border-radius:50%; border:none; display:flex; align-items:center; justify-content:center; font-size:28px; cursor:pointer}
.btn-mute{background:#2a2a2a; color:white}
.btn-end{background:#ef4444; color:white; width:82px; height:82px; font-size:32px}
.btn-spk{background:#2a2a2a; color:white}
.label{font-size:12px; color:#9ca3af; margin-top:8px; text-align:center}
.col{display:flex; flex-direction:column; align-items:center}
.status{margin-top:15px; font-size:14px; color:#22c55e; height:20px; text-align:center; padding:0 20px}
</style>
</head>
<body>
<div class="top"><span>9:41</span><span>📶 🔋 82%</span></div>
<div class="center">
<h1>ZION</h1>
<div class="sub">ligação segura • criptografada</div>
<div id="wave"><canvas id="c"></canvas></div>
<div class="timer" id="timer">00:00</div>
<div class="status" id="status">toque no microfone para falar</div>
</div>
<div class="controls">
<div class="col"><button class="btn btn-mute" id="mute">🎤</button><div class="label">falar</div></div>
<div class="col"><button class="btn btn-end" id="end">📞</button><div class="label" style="color:#ef4444">encerrar</div></div>
<div class="col"><button class="btn btn-spk" id="spk">🔊</button><div class="label">testar voz</div></div>
</div>
<script>
let rec, listening=false, sec=0, timerInt;
const wave = document.getElementById('wave');
const statusEl = document.getElementById('status');
const timerEl = document.getElementById('timer');
const canvas = document.getElementById('c');
const ctx = canvas.getContext('2d');
canvas.width=320; canvas.height=320;
function startTimer(){ if(timerInt) return; timerInt=setInterval(()=>{sec++; let m=String(Math.floor(sec/60)).padStart(2,'0'); let s=String(sec%60).padStart(2,'0'); timerEl.textContent=`${m}:${s}`;},1000) }
function drawWave(level){
  ctx.clearRect(0,0,320,320);
  let cx=160, cy=160;
  for(let i=0;i<3;i++){
    ctx.beginPath(); ctx.strokeStyle=`rgba(34,197,94,${0.3 - i*0.1})`; ctx.lineWidth=2;
    let r=60 + i*20 + Math.sin(Date.now()/200 + i)*level*40; ctx.arc(cx,cy,r,0,Math.PI*2); ctx.stroke();
  }
  for(let a=0;a<60;a++){
    let ang=(a/60)*Math.PI*2; let len=10 + Math.random()*level*50;
    let x1=cx+Math.cos(ang)*70; let y1=cy+Math.sin(ang)*70;
    let x2=cx+Math.cos(ang)*(70+len); let y2=cy+Math.sin(ang)*(70+len);
    ctx.beginPath(); ctx.moveTo(x1,y1); ctx.lineTo(x2,y2); ctx.strokeStyle='#22c55e'; ctx.lineWidth=2; ctx.stroke();
  }
  requestAnimationFrame(()=>drawWave(listening?1.2:0.2));
}
drawWave(0.2);
function falar(texto){
  const utter = new SpeechSynthesisUtterance(texto);
  utter.lang='pt-BR'; utter.rate=1.05;
  utter.onstart=()=>{statusEl.textContent='ZION falando...'; wave.classList.add('pulsing')};
  utter.onend=()=>{statusEl.textContent='toque no microfone para falar'; wave.classList.remove('pulsing')};
  speechSynthesis.speak(utter);
}
async function enviarParaZion(texto){
  statusEl.textContent='pensando...';
  try{
    let r = await fetch('/api/zion', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({texto:texto})});
    let j = await r.json();
    falar(j.resposta || "Não entendi, repete?");
  }catch(e){
    falar("ZION está offline no PC. Verifica se o main.py tá aberto.");
  }
}
document.getElementById('mute').onclick = ()=>{
  if(!('webkitSpeechRecognition' in window || 'SpeechRecognition' in window)){ alert('Abre no Chrome do celular'); return; }
  if(listening){ rec.stop(); return; }
  const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
  rec = new SR(); rec.lang='pt-BR'; rec.interimResults=false;
  rec.onstart=()=>{listening=true; statusEl.textContent='ouvindo...'; wave.classList.add('pulsing'); startTimer()};
  rec.onend=()=>{listening=false; wave.classList.remove('pulsing'); statusEl.textContent='toque no microfone para falar'};
  rec.onresult=(e)=>{ let txt=e.results[0][0].transcript; statusEl.textContent=`voce: ${txt}`; enviarParaZion(txt); };
  rec.start();
};
document.getElementById('end').onclick=()=>{ if(timerInt) clearInterval(timerInt); sec=0; timerEl.textContent='00:00'; speechSynthesis.cancel(); statusEl.textContent='ligação encerrada'; setTimeout(()=>statusEl.textContent='toque no microfone para falar',1500); };
document.getElementById('spk').onclick=()=>{ falar("ZION online. Pode falar comigo."); startTimer(); };
</script>
</body>
</html>
"""

zion_callback = None
def set_zion_callback(fn):
    global zion_callback
    zion_callback = fn

@app.route('/')
def index():
    return HTML_CALL

@app.route('/api/zion', methods=['POST'])
def api_zion():
    data = request.json or {}
    texto = data.get('texto','')
    print(f"[TELEFONE] Usuario disse: {texto}")
    if zion_callback:
        try:
            resposta = zion_callback(texto)
        except Exception as e:
            resposta = f"Entendi: {texto}. ZION te ouviu!"
    else:
        resposta = f"Voce disse: {texto}. ZION te ouviu!"
    return jsonify({"resposta": resposta})

def run_server():
    app.run(host='0.0.0.0', port=5001, debug=False)

def iniciar_em_thread():
    t = threading.Thread(target=run_server, daemon=True)
    t.start()
    print("[TELEFONE] Servidor iniciado em http://192.168.15.3:5001")
    return t

if __name__ == '__main__':
    run_server()