"""Original articulated 2D cat short. No downloaded imagery/music or AI API.
Three shots: tactile bed test, running leap into packaging, peek/blink/sleep.
Reproducible with Pillow, NumPy and ffmpeg. All shapes and sound synthesized here.
"""
from PIL import Image, ImageDraw, ImageFont
from pathlib import Path
import math, subprocess, wave, json, hashlib
import numpy as np
ROOT=Path(__file__).resolve().parent
W,H,FPS,DUR=720,1280,24,12
INK='#47332d';ORANGE='#eb9b4b';LIGHT='#fff2d9';PINK='#eaa19b';GREEN='#6b8d73'
FONT='/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'
BOLD='/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'
def text(d,xy,s,size=30,fill=INK,center=True,bold=False):
 f=ImageFont.truetype(BOLD if bold else FONT,size)
 if center:
  box=d.textbbox((0,0),s,font=f);xy=(xy[0]-(box[2]-box[0])/2,xy[1])
 d.text(xy,s,font=f,fill=fill)
def rr(d,box,fill,r=20,width=0):d.rounded_rectangle(box,r,fill=fill,outline=INK if width else None,width=width)
def cat(x,y,scale,t,pose='sit',sleep=False):
 # Render all body parts separately; joints/paws/tail/eyes change over time.
 layer=Image.new('RGBA',(520,520));d=ImageDraw.Draw(layer)
 sway=math.sin(t*3.5)
 if pose=='jump':
  d.line([(96,298),(40,247+12*sway),(30,184+20*sway)],fill=INK,width=39)
  d.line([(96,298),(40,247+12*sway),(30,184+20*sway)],fill=ORANGE,width=29)
  d.ellipse((70,235,338,365),fill=ORANGE,outline=INK,width=5)
  for px,py in [(100,340),(160,346),(290,318),(332,302)]:
   d.line([(px,py),(px+45,py+25+7*math.sin(t*9+px))],fill=INK,width=35)
   d.line([(px,py),(px+45,py+25+7*math.sin(t*9+px))],fill=LIGHT,width=25)
  hx,hy=332,211
 else:
  d.line([(334,390),(430,359),(445,289+16*sway),(415,266+10*sway)],fill=INK,width=43)
  d.line([(334,390),(430,359),(445,289+16*sway),(415,266+10*sway)],fill=ORANGE,width=33)
  d.ellipse((120,233,365,449),fill=ORANGE,outline=INK,width=5)
  d.ellipse((165,277,315,437),fill=LIGHT)
  for px in [154,308]:d.ellipse((px-40,397,px+40,452),fill=LIGHT,outline=INK,width=5)
  hx,hy=247,201
  if pose=='tap':
   py=318-42*max(0,math.sin(t*6))
   d.line([(323,304),(376,py)],fill=INK,width=43);d.line([(323,304),(376,py)],fill=LIGHT,width=33)
 # Distinct feline ear silhouette.
 d.polygon([(hx-118,hy-58),(hx-110,hy-155),(hx-37,hy-103)],fill=ORANGE,outline=INK,width=5)
 d.polygon([(hx+118,hy-58),(hx+110,hy-155),(hx+37,hy-103)],fill=ORANGE,outline=INK,width=5)
 d.polygon([(hx-101,hy-72),(hx-96,hy-126),(hx-57,hy-97)],fill=PINK)
 d.polygon([(hx+101,hy-72),(hx+96,hy-126),(hx+57,hy-97)],fill=PINK)
 d.ellipse((hx-130,hy-107,hx+130,hy+110),fill=ORANGE,outline=INK,width=5)
 # Three tabby stripes, cream muzzle, cheek blush.
 for off in [-38,0,38]:d.polygon([(hx+off-8,hy-99),(hx+off+10,hy-99),(hx+off+3,hy-57)],fill='#bd7038')
 d.ellipse((hx-88,hy+19,hx+88,hy+103),fill=LIGHT)
 blink=sleep or (t%3.4>3.23)
 for off in [-54,54]:
  if blink:d.arc((hx+off-27,hy-22,hx+off+27,hy+24),0,170,fill=INK,width=7)
  else:
   d.ellipse((hx+off-25,hy-28,hx+off+25,hy+26),fill=INK)
   d.ellipse((hx+off-12,hy-20,hx+off+1,hy-7),fill='white')
 d.ellipse((hx-105,hy+17,hx-68,hy+35),fill=PINK);d.ellipse((hx+68,hy+17,hx+105,hy+35),fill=PINK)
 d.polygon([(hx-14,hy+35),(hx+14,hy+35),(hx,hy+49)],fill=PINK)
 d.line([(hx,hy+47),(hx,hy+62)],fill=INK,width=4)
 d.arc((hx-26,hy+44,hx,hy+75),0,100,fill=INK,width=3)
 d.arc((hx,hy+44,hx+26,hy+75),80,180,fill=INK,width=3)
 for side in [-1,1]:
  for dy in [-10,10]:d.line([(hx+side*85,hy+49+dy),(hx+side*145,hy+42+dy*2)],fill=INK,width=3)
 # Original red neckerchief for Ah-Ju.
 d.polygon([(hx-72,hy+96),(hx+61,hy+99),(hx+5,hy+147)],fill='#b9534c',outline=INK,width=4)
 size=int(520*scale);layer=layer.resize((size,size),Image.Resampling.LANCZOS)
 return layer,(int(x-size/2),int(y-size/2))
def plant(d,x,y):
 rr(d,(x-35,y,x+35,y+82),'#c68670',12)
 for side,dy in [(-1,0),(1,30),(-1,60)]:
  d.line([(x,y),(x+side*20,y-130+dy)],fill=GREEN,width=6)
  d.ellipse((x+side*25-25,y-157+dy,x+side*25+25,y-114+dy),fill=GREEN)
def box(d,x,y,w=300,front=False):
 if front:
  rr(d,(x-w/2,y,x+w/2,y+185),'#ce9862',14,4)
  d.polygon([(x-w/2,y),(x,y+16),(x+w/2,y),(x,y-22)],fill='#e5ba84',outline=INK,width=4)
  # little heart, packaging mark rather than third-party brand.
  d.ellipse((x-24,y+65,x,y+91),fill='#9b6849');d.ellipse((x,y+65,x+24,y+91),fill='#9b6849')
  d.polygon([(x-24,y+80),(x+24,y+80),(x,y+113)],fill='#9b6849')
 else:
  rr(d,(x-w/2,y,x+w/2,y+180),'#c58c55',12,4)
  d.polygon([(x-w/2,y),(x-w/2-58,y-72),(x-40,y-61),(x,y)],fill='#e5ba84',outline=INK,width=4)
  d.polygon([(x,y),(x+50,y-65),(x+w/2+50,y-56),(x+w/2,y)],fill='#e5ba84',outline=INK,width=4)
def frame(t):
 shot=min(int(t/4),2);u=t-shot*4
 im=Image.new('RGB',(W,H),'#fff7e9');d=ImageDraw.Draw(im)
 # Layered home setting; fixed camera inside each shot, not still-photo zooms.
 d.ellipse((-100,-100,450,410),fill='#f8e9c8')
 d.rectangle((0,925,W,H),fill='#e5ceac');d.line((0,925,W,925),fill='#c5ac8d',width=4)
 for y in [1040,1170]:d.line((0,y,W,y),fill='#d4b995',width=2)
 plant(d,75,850)
 rr(d,(570,345,680,575),'#c0a48a',20);rr(d,(580,355,670,565),'#dce8d6',12)
 d.line((625,355,625,565),fill='#fff8eb',width=8);d.line((580,455,670,455),fill='#fff8eb',width=8)
 text(d,(W/2,86),'DAILY PURR',22,fill='#8c6f60',bold=True)
 text(d,(W/2,140),'THE BOX TEST',48,bold=True)
 for i in range(3):d.ellipse((W/2-34+i*28,220,W/2-22+i*28,232),fill='#b9534c' if i==shot else '#d9c5aa')
 if shot==0:
  text(d,(W/2,300),'I bought the fancy bed.',32,bold=True)
  # Plush bed, actual animated paw tests its rim.
  rr(d,(405,850,675,961),'#bdcfc0',48,4);rr(d,(432,864,650,929),'#edf0db',35)
  sprite,xy=cat(272,782,.85,u,'tap');im.paste(sprite,xy,sprite)
  d=ImageDraw.Draw(im)
  if math.sin(u*6)>0.4:text(d,(553,777),'tap',26,fill='#6a8773')
  text(d,(W/2,1115),'The quality inspector arrived.',23)
 elif shot==1:
  text(d,(W/2,300),'He tested the packaging.',32,bold=True)
  # Run -> leap -> land behind box, with changing paw positions and arc.
  p=max(0,min(1,(u-.5)/2.25));x=90+430*p;y=835-180*math.sin(math.pi*p)
  sprite,xy=cat(x,y,.76,u,'jump');im.paste(sprite,xy,sprite)
  d=ImageDraw.Draw(im);box(d,515,840,230)
  for j in range(3):d.line((55,735+j*24,110+12*math.sin(u*6),735+j*24),fill='#bca185',width=4)
  if u>2.8:
   for dx,dy in [(-110,-100),(120,-115),(0,-148)]:text(d,(515+dx,850+dy),'!',34,fill='#b9534c',bold=True)
  text(d,(W/2,1115),'One very important field test.',23)
 else:
  text(d,(W/2,300),'Five stars. For the box.',32,bold=True)
  # New closer shot: head rises, blinks, paws grip, settles to sleep.
  sleep=u>2.5;y=720+32*max(0,u-2.5)
  sprite,xy=cat(360,y,1.03,u,'sit',sleep=sleep);im.paste(sprite,xy,sprite)
  d=ImageDraw.Draw(im);box(d,360,865,360,True)
  for px in [270,450]:d.ellipse((px-35,846,px+35,883),fill=LIGHT,outline=INK,width=4)
  for j in range(5):text(d,(234+j*63,1030),'*',55,fill='#b9793e',bold=True)
  if sleep:text(d,(555,520-12*math.sin(u*2)),'z z z',28,fill=GREEN)
  text(d,(W/2,1130),'The bed was just the delivery fee.',23)
 text(d,(W/2,1217),'An original little cat story',19,fill='#7f695d')
 return im
# Original synthesized marimba phrase and paper-rustle effect; no sampled music.
sr=44100;signal=np.zeros(DUR*sr,dtype=np.float64)
notes=[(0,523.25),(.5,659.25),(1,783.99),(2,659.25),(3,587.33),(4,523.25),(4.35,659.25),(4.7,783.99),(5.05,1046.5),(6,783.99),(7,659.25),(8,523.25),(8.5,659.25),(9,783.99),(10,659.25),(11,523.25)]
for start,f in notes:
 n=int(.7*sr);v=np.arange(n)/sr;tone=(np.sin(2*math.pi*f*v)+.25*np.sin(2*math.pi*2*f*v))*np.exp(-v*7)*.12;i=int(start*sr);signal[i:i+n]+=tone[:min(n,len(signal)-i)]
rng=np.random.default_rng(3);start=int(6.8*sr);n=int(.35*sr);signal[start:start+n]+=.035*rng.standard_normal(n)*np.linspace(1,0,n)
with wave.open(str(ROOT/'original-sound.wav'),'wb') as w:w.setnchannels(1);w.setsampwidth(2);w.setframerate(sr);w.writeframes((np.clip(signal,-1,1)*32767).astype('<i2').tobytes())
cmd=['ffmpeg','-y','-f','rawvideo','-vcodec','rawvideo','-pix_fmt','rgb24','-s',f'{W}x{H}','-r',str(FPS),'-i','-','-i',str(ROOT/'original-sound.wav'),'-c:v','libx264','-preset','medium','-crf','22','-pix_fmt','yuv420p','-c:a','aac','-b:a','96k','-movflags','+faststart','-shortest',str(ROOT/'daily-purr-box-test.mp4')]
proc=subprocess.Popen(cmd,stdin=subprocess.PIPE,stderr=subprocess.DEVNULL)
for i in range(FPS*DUR):proc.stdin.write(frame(i/FPS).tobytes())
proc.stdin.close();code=proc.wait();assert code==0
samples=[frame(t).resize((270,480)) for t in [1.2,5.6,9.6]]
sheet=Image.new('RGB',(810,480));
for i,s in enumerate(samples):sheet.paste(s,(270*i,0))
sheet.save(ROOT/'three-shot-preview.jpg',quality=92)
manifest={'title':'The Box Test','duration_seconds':DUR,'fps':FPS,'size':[W,H],'shots':[{'seconds':[0,4],'action':'Cat taps expensive bed; moving paw, tail, blink'},{'seconds':[4,8],'action':'Cat runs/leaps into cardboard packaging; moving limbs and impact'},{'seconds':[8,12],'action':'Cat peeks, grips rim, blinks and settles to sleep'}],'not_static_zoom':True,'art':'All original vector-like shapes authored in this script; no stock or generated still image','sound':'Original synthesized marimba and paper rustle; no external samples','cost_ntd':0,'sha256':hashlib.sha256((ROOT/'daily-purr-box-test.mp4').read_bytes()).hexdigest(),'qa':'pending visual and motion inspection; do not publish on render success alone'}
(ROOT/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'video_bytes':(ROOT/'daily-purr-box-test.mp4').stat().st_size,'sha256':manifest['sha256']}))
