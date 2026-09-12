from __future__ import annotations
import json, queue, threading, time
from pathlib import Path
import tkinter as tk
from tkinter import messagebox, ttk
import cv2, mss, numpy as np, pyautogui
from pynput import keyboard
from PIL import Image, ImageTk

APP_DIR=Path(__file__).resolve().parent
PROFILE_PATH=APP_DIR/'profile.json'
TEMPLATE_DIR=APP_DIR/'templates'/'user'; TEMPLATE_DIR.mkdir(parents=True,exist_ok=True)
ITEMS=[('tela_invasao','Tela / aba Invasao Zumbi','position'),('buscar','Buscar','image'),('popup_invasao','Popup / alvo encontrado','image'),('botao_atacar','Atacar','image'),('botao_marchar','Marchar','image'),('sem_vigor','Sem vigor','image')]
EXAMPLES={'buscar':'templates/buscar.png','popup_invasao':'templates/popup_invasao_zumbis.png','botao_atacar':'templates/botao_atacar.png','botao_marchar':'templates/botao_marchar.png'}
DEFAULT={'threshold':.72,'click_delay':.3,'after_search':.5,'after_attack':.7,'after_march':.7,'timeout':5.0,'actions':{}}
def load_profile():
 d=json.loads(json.dumps(DEFAULT))
 if PROFILE_PATH.exists():
  try:d.update(json.loads(PROFILE_PATH.read_text(encoding='utf-8')));d.setdefault('actions',{})
  except:pass
 return d
def save_profile(p):PROFILE_PATH.write_text(json.dumps(p,indent=2,ensure_ascii=False),encoding='utf-8')
def shot():
 with mss.mss() as s:m=s.monitors[1];im=np.array(s.grab(m))
 return cv2.cvtColor(im,cv2.COLOR_BGRA2BGR),m
def match(path,threshold):
 p=Path(path);p=p if p.is_absolute() else APP_DIR/p;t=cv2.imread(str(p))
 if t is None:return None
 s,m=shot();th,tw=t.shape[:2]
 if tw>s.shape[1] or th>s.shape[0]:return None
 r=cv2.matchTemplate(s,t,cv2.TM_CCOEFF_NORMED);_,score,_,loc=cv2.minMaxLoc(r)
 if score<threshold:return None
 return {'x':int(m['left']+loc[0]+tw//2),'y':int(m['top']+loc[1]+th//2),'score':float(score)}
def find(a,t):
 best=None
 for p in a.get('templates',[]):
  f=match(p,t)
  if f and (best is None or f['score']>best['score']):best=f
 return best
class Pointer(tk.Toplevel):
 def __init__(self,parent,label,cb):
  super().__init__(parent);self.cb=cb;self.attributes('-fullscreen',True);self.attributes('-topmost',True);self.attributes('-alpha',.28);self.configure(bg='black',cursor='crosshair');self.focus_force();tk.Label(self,text='CLIQUE NO LOCAL DESEJADO',bg='black',fg='white',font=('Segoe UI',28,'bold')).pack(pady=(35,5));tk.Label(self,text=f'{label}\nESC cancela',bg='black',fg='white',font=('Segoe UI',16,'bold')).pack();self.bind('<Escape>',lambda e:self.destroy());self.bind('<Button-1>',self.go)
 def go(self,e):
  x,y=self.winfo_pointerxy();self.destroy();self.cb(x,y)
class Crop(tk.Toplevel):
 def __init__(self,parent,name,cb):
  super().__init__(parent);self.name=name;self.cb=cb;self.im,self.mon=shot();self.attributes('-fullscreen',True);self.attributes('-topmost',True);self.configure(cursor='crosshair');self.c=tk.Canvas(self,highlightthickness=0);self.c.pack(fill='both',expand=True);self.photo=ImageTk.PhotoImage(Image.fromarray(cv2.cvtColor(self.im,cv2.COLOR_BGR2RGB)));self.c.create_image(0,0,anchor='nw',image=self.photo);self.c.create_rectangle(0,0,self.winfo_screenwidth(),120,fill='black',outline='black');self.c.create_text(self.winfo_screenwidth()//2,38,text='1. ARRASTE PARA MARCAR O OBJETO',fill='white',font=('Segoe UI',26,'bold'));self.c.create_text(self.winfo_screenwidth()//2,82,text='2. PRESSIONE ENTER PARA SALVAR     |     ESC = CANCELAR',fill='white',font=('Segoe UI',20,'bold'));self.a=self.b=self.rect=None;self.bind('<Escape>',lambda e:self.destroy());self.bind('<Return>',self.save);self.c.bind('<ButtonPress-1>',self.start);self.c.bind('<B1-Motion>',self.drag);self.c.bind('<ButtonRelease-1>',self.end);self.focus_force()
 def start(self,e):
  self.a=(e.x,e.y)
  if self.rect:self.c.delete(self.rect)
  self.rect=self.c.create_rectangle(e.x,e.y,e.x,e.y,outline='red',width=4)
 def drag(self,e):
  if self.a:self.c.coords(self.rect,self.a[0],self.a[1],e.x,e.y)
 def end(self,e):self.b=(e.x,e.y)
 def save(self,e=None):
  if not self.a or not self.b:return
  x1,x2=sorted((self.a[0],self.b[0]));y1,y2=sorted((self.a[1],self.b[1]))
  if x2-x1<8 or y2-y1<8:return
  p=TEMPLATE_DIR/f'{self.name}_{len(list(TEMPLATE_DIR.glob(self.name+"_*.png")))+1:03d}.png';cv2.imwrite(str(p),self.im[y1:y2,x1:x2]);self.destroy();self.cb(str(p.relative_to(APP_DIR)).replace('\\','/'))
class Calibration(tk.Toplevel):
 def __init__(self,app):
  super().__init__(app);self.app=app;self.title('Zumbi - Calibracao livre');self.geometry('930x570');self.attributes('-topmost',True);self.protocol('WM_DELETE_WINDOW',self.close);self.photos=[];self.root=ttk.Frame(self,padding=18);self.root.pack(fill='both',expand=True);ttk.Label(self.root,text='CALIBRACAO LIVRE',font=('Segoe UI',20,'bold')).pack(anchor='w');ttk.Label(self.root,text='Deixe o jogo na tela desejada. Para imagens, use o exemplo como guia do que deve entrar no recorte.').pack(anchor='w',pady=(2,14));self.rows=ttk.Frame(self.root);self.rows.pack(fill='x');self.refresh();ttk.Separator(self.root).pack(fill='x',pady=14);ttk.Label(self.root,text='Os exemplos sao os templates reais do bot original. Sem vigor ainda nao possui exemplo original e deve ser capturado quando aparecer.',wraplength=870).pack(anchor='w');ttk.Button(self.root,text='Fechar e salvar',command=self.close).pack(anchor='e',pady=16)
 def thumb(self,n):
  rel=EXAMPLES.get(n)
  if not rel:return None
  p=APP_DIR/rel
  if not p.exists():return None
  im=Image.open(p);im.thumbnail((105,48));ph=ImageTk.PhotoImage(im);self.photos.append(ph);return ph
 def refresh(self):
  for w in self.rows.winfo_children():w.destroy()
  self.photos=[]
  for n,l,k in ITEMS:
   a=self.app.p['actions'].get(n,{});pos=a.get('position');num=len(a.get('templates',[]));ok=bool(pos) if k=='position' else bool(num);st='Nao configurado'
   if k=='position' and pos:st=f"X {pos['x']} Y {pos['y']}"
   elif k=='image' and num:st=f'{num} imagem(ns)'
   r=ttk.Frame(self.rows);r.pack(fill='x',pady=5);ttk.Label(r,text=l,width=25).pack(side='left');ph=self.thumb(n)
   if ph:ttk.Label(r,image=ph).pack(side='left',padx=(3,10))
   else:ttk.Label(r,text='(sem exemplo)',width=16).pack(side='left',padx=(3,10))
   ttk.Label(r,text=('OK | ' if ok else '')+st,width=22).pack(side='left');ttk.Button(r,text='Capturar',command=lambda n=n,l=l,k=k:self.app.capture(n,l,k,self)).pack(side='right',padx=3);ttk.Button(r,text='Testar',command=lambda n=n,l=l,k=k:self.app.test(n,l,k)).pack(side='right',padx=3)
 def close(self):save_profile(self.app.p);self.app.summary();self.destroy()
class App(tk.Tk):
 def __init__(self):
  super().__init__();self.title('Zumbi Product V1.3');self.geometry('820x620');self.p=load_profile();self.running=False;self.paused=False;self.logs=queue.Queue();self.protocol('WM_DELETE_WINDOW',self.close);self.build();self.after(100,self.flush);self.listener=keyboard.Listener(on_press=self.hotkey);self.listener.start()
 def build(self):
  r=ttk.Frame(self,padding=18);r.pack(fill='both',expand=True);ttk.Label(r,text='ZUMBI',font=('Segoe UI',24,'bold')).pack(anchor='w');self.status=ttk.Label(r,text='Parado');self.status.pack(anchor='w',pady=(0,14));b=ttk.Frame(r);b.pack(fill='x');ttk.Button(b,text='Iniciar',command=self.start_bot).pack(side='left',padx=3);ttk.Button(b,text='Pausar / Retomar',command=self.pause).pack(side='left',padx=3);ttk.Button(b,text='Parar',command=self.stop).pack(side='left',padx=3);ttk.Button(b,text='Calibrar',command=self.calibrate).pack(side='right');ttk.Separator(r).pack(fill='x',pady=12);self.sum=ttk.Frame(r);self.sum.pack(fill='x');self.summary();ttk.Label(r,text='Log',font=('Segoe UI',14,'bold')).pack(anchor='w',pady=(18,6));self.logbox=tk.Text(r,height=15,state='disabled',font=('Consolas',9));self.logbox.pack(fill='both',expand=True);ttk.Label(r,text='F8 pausa/retoma | F12 para').pack(anchor='e')
 def configured(self,n,k):
  a=self.p['actions'].get(n,{});return bool(a.get('position')) if k=='position' else bool(a.get('templates'))
 def summary(self):
  for w in self.sum.winfo_children():w.destroy()
  ttk.Label(self.sum,text='Estado da calibracao',font=('Segoe UI',14,'bold')).pack(anchor='w')
  for n,l,k in ITEMS:ttk.Label(self.sum,text=('OK  ' if self.configured(n,k) else '--  ')+l+'  ['+('coordenada' if k=='position' else 'imagem')+']').pack(anchor='w')
 def calibrate(self):
  if self.running:messagebox.showwarning('Zumbi','Pare o bot antes de calibrar.');return
  Calibration(self)
 def restore(self,w):self.deiconify();self.lift();w.deiconify();w.lift();w.attributes('-topmost',True);w.focus_force()
 def capture(self,n,l,k,w):
  w.withdraw();self.withdraw();self.update_idletasks()
  if k=='position':
   def done(x,y):
    a=self.p['actions'].setdefault(n,{});a.clear();a['mode']='position';a['position']={'x':x,'y':y};save_profile(self.p);self.restore(w);w.refresh();self.summary()
   Pointer(self,'Capturar: '+l,done)
  else:
   def done(path):
    a=self.p['actions'].setdefault(n,{});a['mode']='image';a.pop('position',None);a['templates']=a.get('templates',[])+[path];save_profile(self.p);self.restore(w);w.refresh();self.summary();f=match(path,float(self.p['threshold']));messagebox.showinfo('Teste',f"Imagem salva. Match: {f['score']:.1%}" if f else 'Imagem salva. Nao foi reconhecida na tela atual.',parent=w)
   self.after(180,lambda:Crop(self,n,done))
 def test(self,n,l,k):
  a=self.p['actions'].get(n,{})
  if k=='position':
   pos=a.get('position');messagebox.showinfo('Teste',f"{l}: X {pos['x']} / Y {pos['y']}" if pos else 'Capture a coordenada primeiro.');return
  if not a.get('templates'):messagebox.showwarning('Teste','Capture uma imagem primeiro.');return
  f=find(a,float(self.p['threshold']));messagebox.showinfo('Teste',f"{l}: {f['score']:.1%} em X {f['x']} Y {f['y']}" if f else f'{l} nao encontrado na tela atual.')
 def log(self,s):self.logs.put(s)
 def flush(self):
  while not self.logs.empty():
   s=self.logs.get();self.logbox.config(state='normal');self.logbox.insert('end',s+'\n');self.logbox.see('end');self.logbox.config(state='disabled')
  self.after(100,self.flush)
 def hotkey(self,k):
  if k==keyboard.Key.f8:self.after(0,self.pause)
  elif k==keyboard.Key.f12:self.after(0,self.stop)
 def pause(self):
  if self.running:self.paused=not self.paused;self.status.config(text='Pausado' if self.paused else 'Rodando')
 def stop(self):self.running=False;self.paused=False;self.status.config(text='Parando...')
 def sleep(self,s):
  end=time.time()+s
  while self.running and time.time()<end:
   while self.paused and self.running:time.sleep(.1)
   time.sleep(.05)
 def click(self,f,l):self.log(f"CLICK {l}: {f['x']},{f['y']}");pyautogui.click(f['x'],f['y']);self.sleep(float(self.p['click_delay']))
 def wait(self,n):
  end=time.time()+float(self.p['timeout']);a=self.p['actions'][n]
  while self.running and time.time()<end:
   f=find(a,float(self.p['threshold']))
   if f:return f
   time.sleep(.25)
  return None
 def start_bot(self):
  req=[('tela_invasao','position'),('buscar','image'),('botao_atacar','image'),('botao_marchar','image')];missing=[n for n,k in req if not self.configured(n,k)]
  if missing:messagebox.showwarning('Zumbi','Falta calibrar: '+', '.join(missing));return
  if self.running:return
  self.running=True;self.paused=False;self.status.config(text='Rodando');threading.Thread(target=self.loop,daemon=True).start()
 def loop(self):
  marches=0
  try:
   while self.running:
    nv=self.p['actions'].get('sem_vigor',{})
    if nv.get('templates') and find(nv,float(self.p['threshold'])):self.log('Sem vigor detectado. Encerrando.');break
    f=self.wait('buscar')
    if not f:self.log('Buscar nao encontrado. Confirme que o jogo esta na aba Invasao Zumbi.');break
    self.click(f,'Buscar');self.sleep(float(self.p['after_search']))
    pop=self.p['actions'].get('popup_invasao',{})
    if pop.get('templates') and not self.wait('popup_invasao'):self.log('Popup/alvo nao confirmado.');break
    f=self.wait('botao_atacar')
    if not f:self.log('Atacar nao encontrado. Possivel falta de vigor.');break
    self.click(f,'Atacar');self.sleep(float(self.p['after_attack']));f=self.wait('botao_marchar')
    if not f:self.log('Marchar nao encontrado.');break
    self.click(f,'Marchar');marches+=1;self.log(f'Marcha {marches} concluida');self.sleep(float(self.p['after_march']))
  except pyautogui.FailSafeException:self.log('FAILSAFE acionado.')
  except Exception as e:self.log('ERRO: '+str(e))
  finally:self.running=False;self.paused=False;self.after(0,lambda:self.status.config(text='Parado'));self.log(f'Finalizado. Marchas: {marches}')
 def close(self):
  self.running=False
  try:self.listener.stop()
  except:pass
  self.destroy()
if __name__=='__main__':pyautogui.FAILSAFE=True;App().mainloop()
